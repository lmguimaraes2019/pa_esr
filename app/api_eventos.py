"""Participação em eventos 2027: inscrição, viagem (calculada pelas tarifas da aba Viagens), pessoas e justificativa."""
from __future__ import annotations

import json
import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from . import viagens as vg
from .api import _arred, _conn, exige_acesso, permitidos, usuario_liberado
from .db import NOMES_MESES, audit, tx

router = APIRouter(prefix="/api/eventos")


class EventoIn(BaseModel):
    orcamento: str = Field(min_length=1, max_length=20)
    nome: str = Field(default="", max_length=200)
    local: str = Field(default="", max_length=200)
    tipo: str = Field(default="nac", pattern="^(nac|int)$")
    mes: int = Field(default=1, ge=1, le=12)
    n_pessoas: int = Field(default=1, ge=1, le=200)
    dias: int = Field(default=1, ge=1, le=60)
    pernoites: int | None = Field(default=None, ge=0, le=60)
    inscricao: float | None = Field(default=None, ge=0, le=1e9)
    moeda: str = Field(default="BRL", pattern="^(BRL|USD)$")
    origem: str = Field(default="", max_length=80)
    destino: str = Field(default="", max_length=80)
    pessoas: list[str] = Field(default_factory=list, max_length=200)
    justificativa: str = Field(default="", max_length=2000)

    @field_validator("pessoas")
    @classmethod
    def _p(cls, v):
        return [x.strip()[:120] for x in v if x and x.strip()]


def _dolar(c: sqlite3.Connection) -> float:
    r = c.execute("SELECT valor FROM premissas WHERE chave='dolar'").fetchone()
    return float(r[0]) if r else 5.5


def _calc(r: sqlite3.Row, tarifas: dict, bv: float, dolar: float) -> dict:
    pessoas = json.loads(r["pessoas"] or "[]")
    t = tarifas.get((r["tipo"], r["origem"], r["destino"]))
    viagem = vg.calcular(r["tipo"], t, r["n_pessoas"], r["dias"], r["pernoites"], bv)
    insc_un = (r["inscricao"] or 0.0) * (dolar if r["moeda"] == "USD" else 1.0)
    insc = round(insc_un * r["n_pessoas"], 2)
    falta = []
    if not r["nome"].strip(): falta.append("nome do evento")
    if not r["local"].strip(): falta.append("local")
    if r["inscricao"] is None: falta.append("custo de inscrição")
    if t is None: falta.append("trecho da viagem (origem e destino)")
    if len(pessoas) < r["n_pessoas"]: falta.append(f"nome das pessoas ({len(pessoas)} de {r['n_pessoas']})")
    if not r["justificativa"].strip(): falta.append("justificativa")
    return {"id": r["id"], "orcamento": r["orcamento"], "nome": r["nome"], "local": r["local"], "tipo": r["tipo"], "mes": r["mes"],
            "n_pessoas": r["n_pessoas"], "dias": r["dias"], "pernoites": r["pernoites"], "inscricao": r["inscricao"], "moeda": r["moeda"],
            "origem": r["origem"], "destino": r["destino"], "pessoas": pessoas, "justificativa": r["justificativa"],
            "atualizado_por": r["atualizado_por"], "viagem": viagem, "inscricao_unitaria_brl": round(insc_un, 2),
            "inscricao_total": insc, "total": _arred(insc + viagem["total"]), "faltando": falta, "completo": not falta}


@router.get("")
def listar(u: dict = Depends(usuario_liberado), c: sqlite3.Connection = Depends(_conn)):
    ids = sorted(permitidos(c, u))
    marks = ",".join("?" for _ in ids) or "''"
    tarifas, bv, dolar = vg.tarifas_map(c), vg.bagagem_vezes(c), _dolar(c)
    projetos = {r["orcamento"]: r for r in c.execute(
        f"SELECT orcamento, descricao, origem, gerente FROM projetos WHERE orcamento IN ({marks}) ORDER BY orcamento", ids)}
    itens = []
    for r in c.execute(f"SELECT * FROM eventos WHERE orcamento IN ({marks}) ORDER BY mes, id", ids):
        d = _calc(r, tarifas, bv, dolar); d["projeto"] = projetos[r["orcamento"]]["descricao"]; itens.append(d)
    por_proj: dict[str, dict] = {}
    for d in itens:
        x = por_proj.setdefault(d["orcamento"], {"orcamento": d["orcamento"], "projeto": d["projeto"], "eventos": 0, "pessoas": 0,
                                                 "inscricao": 0.0, "viagem": 0.0, "total": 0.0})
        x["eventos"] += 1; x["pessoas"] += d["n_pessoas"]; x["inscricao"] += d["inscricao_total"]
        x["viagem"] += d["viagem"]["total"]; x["total"] += d["total"]
    for x in por_proj.values():
        for k in ("inscricao", "viagem", "total"): x[k] = _arred(x[k])
    mensal = [{"mes": NOMES_MESES[i], "valor": _arred(sum(d["total"] for d in itens if d["mes"] == i + 1))} for i in range(12)]
    return {
        "itens": itens, "por_projeto": list(por_proj.values()), "mensal": mensal, "dolar": dolar, "bagagem_vezes": bv,
        "totais": {"eventos": len(itens), "pessoas": sum(d["n_pessoas"] for d in itens), "inscricao": _arred(sum(d["inscricao_total"] for d in itens)),
                   "viagem": _arred(sum(d["viagem"]["total"] for d in itens)), "total": _arred(sum(d["total"] for d in itens)),
                   "incompletos": sum(1 for d in itens if not d["completo"])},
        "tarifas": [{"tipo": k[0], "origem": k[1], "destino": k[2],
                    **{f: float(tarifas[k][f]) for f in ("passagem", "hospedagem", "bagagem", "aux_transporte", "ajuda_custo", "seguro")}}
                   for k in sorted(tarifas)],
        "projetos": [{"orcamento": o, "descricao": p["descricao"], "origem": p["origem"], "gerente": p["gerente"]} for o, p in projetos.items()],
    }


def _uma(c: sqlite3.Connection, eid: int) -> dict:
    return _calc(c.execute("SELECT * FROM eventos WHERE id=?", (eid,)).fetchone(), vg.tarifas_map(c), vg.bagagem_vezes(c), _dolar(c))


def _valores(d: EventoIn, u: dict):
    return (d.orcamento, d.nome.strip(), d.local.strip(), d.tipo, d.mes, d.n_pessoas, d.dias, d.pernoites, d.inscricao, d.moeda,
            d.origem, d.destino, json.dumps(d.pessoas, ensure_ascii=False), d.justificativa.strip(), u["login"])


@router.post("", status_code=201)
def criar(d: EventoIn, u: dict = Depends(usuario_liberado)):
    with tx() as c:
        exige_acesso(c, u, d.orcamento)
        cur = c.execute("INSERT INTO eventos (orcamento, nome, local, tipo, mes, n_pessoas, dias, pernoites, inscricao, moeda, origem, destino, "
                        "pessoas, justificativa, atualizado_por) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", _valores(d, u))
        audit(c, u["login"], "incluiu evento", d.orcamento, detalhe=d.nome)
        return _uma(c, cur.lastrowid)


@router.put("/{eid}")
def editar(eid: int, d: EventoIn, u: dict = Depends(usuario_liberado)):
    with tx() as c:
        atual = c.execute("SELECT * FROM eventos WHERE id=?", (eid,)).fetchone()
        if not atual:
            raise HTTPException(404, "Evento não encontrado.")
        exige_acesso(c, u, atual["orcamento"]); exige_acesso(c, u, d.orcamento)
        c.execute("UPDATE eventos SET orcamento=?, nome=?, local=?, tipo=?, mes=?, n_pessoas=?, dias=?, pernoites=?, inscricao=?, moeda=?, "
                  "origem=?, destino=?, pessoas=?, justificativa=?, atualizado_por=?, atualizado_em=datetime('now') WHERE id=?",
                  (*_valores(d, u), eid))
        audit(c, u["login"], "editou evento", d.orcamento, detalhe=f"id {eid}: {d.nome}")
        return _uma(c, eid)


@router.delete("/{eid}")
def excluir(eid: int, u: dict = Depends(usuario_liberado)):
    with tx() as c:
        atual = c.execute("SELECT * FROM eventos WHERE id=?", (eid,)).fetchone()
        if not atual:
            raise HTTPException(404, "Evento não encontrado.")
        exige_acesso(c, u, atual["orcamento"])
        c.execute("DELETE FROM eventos WHERE id=?", (eid,))
        audit(c, u["login"], "excluiu evento", atual["orcamento"], detalhe=f"id {eid}: {atual['nome']}")
    return {"ok": True}
