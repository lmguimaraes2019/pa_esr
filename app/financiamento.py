"""Estratégia de financiamento dos projetos: de onde vem o recurso que paga cada despesa de 2027.

Projetos de fomento (origem Fomento ou FNDCT) já têm a fonte definida. Os demais indicam a fonte: transferência intercompany,
receita própria (externa) ou TBD, quando ainda não há fonte. Enquanto o gestor não indicar nada, o projeto fica com pendência."""
from __future__ import annotations

import sqlite3

import re
import unicodedata

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from . import config
from .api import _arred, _conn, exige_admin, permitidos, usuario_liberado
from .db import MESES, audit, tx
from .fontes import efetivo, lista_fontes

router = APIRouter(prefix="/api/financiamento")

def quadro(c: sqlite3.Connection, ids: list[str]) -> dict:
    """Despesa de 2027 dos projetos visíveis agrupada pela fonte de financiamento."""
    ids = sorted(ids)
    marks = ",".join("?" for _ in ids) or "''"
    soma = "+".join(f"l.{m}" for m in MESES)
    rows = c.execute(
        f"""SELECT p.orcamento, p.descricao, p.gerente, p.finalidade, p.financiamento, p.financiamento_obs,
                   COALESCE(NULLIF(p.origem_2027, ''), p.origem) AS origem,
                   COALESCE((SELECT SUM({soma}) FROM linhas l WHERE l.orcamento=p.orcamento AND l.ciclo=?), 0) AS valor
            FROM projetos p WHERE p.orcamento IN ({marks}) AND p.tipo='despesa' AND p.extinto=0 AND p.contingenciado=0""",
        (config.CICLO_PLANO, *ids)).fetchall()
    ordem = [f["codigo"] for f in lista_fontes(c)] + [""]
    nomes = {f["codigo"]: f["nome"] for f in lista_fontes(c)} | {"": "Fonte não informada"}
    grupos = {k: {"fonte": k, "nome": nomes[k], "n": 0, "valor": 0.0, "projetos": []} for k in ordem}
    for r in rows:
        if r["valor"] <= 0.004:
            continue
        g = grupos[efetivo(r["origem"], r["financiamento"])]
        g["n"] += 1
        g["valor"] += r["valor"]
        g["projetos"].append({"orcamento": r["orcamento"], "projeto": r["descricao"], "gerente": r["gerente"], "valor": _arred(r["valor"]),
                              "obs": r["financiamento_obs"], "origem": r["origem"]})
    for g in grupos.values():
        g["valor"] = _arred(g["valor"])
        g["projetos"].sort(key=lambda x: -x["valor"])
    total = _arred(sum(g["valor"] for g in grupos.values()))
    # receita de transferência intercompany prevista nos orçamentos visíveis, para comparar com o que ela custeia
    inter = c.execute(
        f"SELECT COALESCE(SUM({'+'.join(MESES)}), 0) FROM receitas WHERE ciclo=? AND tipo='intercompany' AND orcamento IN ({marks})",
        (config.CICLO_PLANO, *ids)).fetchone()[0]
    custeado = grupos["intercompany"]["valor"]
    return {"grupos": [grupos[k] for k in ordem], "total": total, "intercompany_receita": _arred(inter),
            "intercompany_custeado": custeado, "intercompany_saldo": _arred(inter - custeado),
            "pendentes": grupos[""]["n"]}


@router.get("")
def listar(u: dict = Depends(usuario_liberado), c: sqlite3.Connection = Depends(_conn)):
    return quadro(c, list(permitidos(c, u)))


# ---------------------------------------------------------------- cadastro das fontes (Administração, Tabelas de referência)

class FonteIn(BaseModel):
    nome: str = Field(min_length=2, max_length=60)


def _codigo(c: sqlite3.Connection, nome: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode().lower()).strip("_")[:30] or "fonte"
    cod, n = base, 2
    while c.execute("SELECT 1 FROM fontes_financiamento WHERE codigo=?", (cod,)).fetchone():
        cod, n = f"{base}_{n}", n + 1
    return cod


def _fontes_com_uso(c: sqlite3.Connection) -> list[dict]:
    uso = {r[0]: r[1] for r in c.execute("SELECT financiamento, COUNT(*) FROM projetos WHERE financiamento<>'' GROUP BY financiamento")}
    return [f | {"projetos": uso.get(f["codigo"], 0)} for f in lista_fontes(c)]


@router.get("/fontes")
def fontes_listar(_: dict = Depends(usuario_liberado), c: sqlite3.Connection = Depends(_conn)):
    return _fontes_com_uso(c)


@router.post("/fontes", status_code=201)
def fontes_criar(d: FonteIn, u: dict = Depends(exige_admin)):
    with tx() as c:
        nome = d.nome.strip()
        if any(f["nome"].lower() == nome.lower() for f in lista_fontes(c)):
            raise HTTPException(409, "Já existe uma fonte com esse nome.")
        cod = _codigo(c, nome)
        c.execute("INSERT INTO fontes_financiamento (codigo, nome, ordem, sistema) VALUES (?,?,(SELECT COALESCE(MAX(ordem),0)+1 FROM fontes_financiamento),0)", (cod, nome))
        audit(c, u["login"], "criou fonte de financiamento", detalhe=f"{cod}: {nome}")
        return _fontes_com_uso(c)


@router.put("/fontes/{codigo}")
def fontes_editar(codigo: str, d: FonteIn, u: dict = Depends(exige_admin)):
    with tx() as c:
        if not c.execute("SELECT 1 FROM fontes_financiamento WHERE codigo=?", (codigo,)).fetchone():
            raise HTTPException(404, "Fonte não encontrada.")
        nome = d.nome.strip()
        if any(f["nome"].lower() == nome.lower() and f["codigo"] != codigo for f in lista_fontes(c)):
            raise HTTPException(409, "Já existe uma fonte com esse nome.")
        c.execute("UPDATE fontes_financiamento SET nome=? WHERE codigo=?", (nome, codigo))
        audit(c, u["login"], "renomeou fonte de financiamento", detalhe=f"{codigo}: {nome}")
        return _fontes_com_uso(c)


@router.delete("/fontes/{codigo}")
def fontes_excluir(codigo: str, u: dict = Depends(exige_admin)):
    with tx() as c:
        f = c.execute("SELECT sistema FROM fontes_financiamento WHERE codigo=?", (codigo,)).fetchone()
        if not f:
            raise HTTPException(404, "Fonte não encontrada.")
        if f["sistema"]:
            raise HTTPException(409, "As quatro fontes de base não podem ser excluídas; só renomeadas.")
        n = c.execute("SELECT COUNT(*) FROM projetos WHERE financiamento=?", (codigo,)).fetchone()[0]
        if n:
            raise HTTPException(409, f"{n} projeto(s) usam esta fonte. Troque a fonte deles antes de excluir.")
        c.execute("DELETE FROM fontes_financiamento WHERE codigo=?", (codigo,))
        audit(c, u["login"], "excluiu fonte de financiamento", detalhe=codigo)
        return _fontes_com_uso(c)
