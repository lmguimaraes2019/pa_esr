"""Headcount 2027: novas contratações por projeto, com custo anualizado calculado pelas faixas salariais e pelas fórmulas da planilha de custo de pessoal."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from . import pessoal, sync
from .api_eventos import tarefas_dos_projetos
from .api import _arred, _conn, exige_acesso, exige_admin, permitidos, usuario_liberado
from .db import audit, tx

router = APIRouter(prefix="/api/headcount")


class HcIn(BaseModel):
    orcamento: str = Field(min_length=1, max_length=20)
    funcao: str = Field(default="", max_length=120)
    cargo: str = Field(default="", max_length=120)
    trajetoria: str = Field(min_length=1, max_length=40)
    nivel: str = Field(min_length=1, max_length=40)
    grupo: str = Field(min_length=1, max_length=20)
    posicao: float = Field(default=50, ge=0, le=100)
    mes_inicio: int = Field(default=1, ge=1, le=12)
    quantidade: int = Field(default=1, ge=1, le=100)
    justificativa: str = Field(default="", max_length=1000)
    edt: str = Field(default="", max_length=200)
    tarefa: str = Field(default="", max_length=200)


class ParamIn(BaseModel):
    valores: dict[str, float]


def _reajuste(c: sqlite3.Connection) -> float:
    r = c.execute("SELECT valor FROM premissas WHERE chave='reajuste_pessoal'").fetchone()
    return float(r[0]) if r else 0.0


def _calc(r: sqlite3.Row, par: dict, reaj: float) -> dict:
    f = pessoal.faixa(r["trajetoria"], r["nivel"], r["grupo"])
    base = pessoal.salario_na_faixa(f, r["posicao"]) if f else 0.0
    salario = round(base * (1 + reaj / 100), 2)
    cm = pessoal.custo_mensal(salario, par)
    q, meses = r["quantidade"], 13 - r["mes_inicio"]
    return {"id": r["id"], "orcamento": r["orcamento"], "funcao": r["funcao"], "cargo": r["cargo"], "trajetoria": r["trajetoria"],
            "nivel": r["nivel"], "grupo": r["grupo"], "posicao": r["posicao"], "mes_inicio": r["mes_inicio"], "quantidade": q,
            "justificativa": r["justificativa"], "edt": r["edt"], "tarefa": r["tarefa"], "atualizado_por": r["atualizado_por"],
            "faixa": f, "salario_tabela": base, "custo": cm, "meses_2027": meses,
            "anualizado": _arred(cm["anual"] * q), "custo_2027": _arred(cm["mensal"] * meses * q),
            "faltando": [n for n, ok in (("função", r["funcao"].strip()), ("cargo", r["cargo"].strip()),
                                         ("justificativa", r["justificativa"].strip()),
                                         ("tarefa do orçamento que recebe o valor", r["edt"] and r["tarefa"])) if not ok]}


@router.get("")
def listar(u: dict = Depends(usuario_liberado), c: sqlite3.Connection = Depends(_conn)):
    ids = sorted(permitidos(c, u))
    marks = ",".join("?" for _ in ids) or "''"
    par, reaj = pessoal.parametros(c), _reajuste(c)
    projetos = {r["orcamento"]: r for r in c.execute(
        f"SELECT orcamento, descricao, origem, gerente FROM projetos WHERE orcamento IN ({marks}) ORDER BY orcamento", ids)}
    itens = []
    for r in c.execute(f"SELECT * FROM headcount WHERE orcamento IN ({marks}) ORDER BY orcamento, id", ids):
        d = _calc(r, par, reaj)
        d["projeto"] = projetos[r["orcamento"]]["descricao"]
        itens.append(d)
    por_proj: dict[str, dict] = {}
    for d in itens:
        x = por_proj.setdefault(d["orcamento"], {"orcamento": d["orcamento"], "projeto": d["projeto"], "posicoes": 0,
                                                 "anualizado": 0.0, "custo_2027": 0.0})
        x["posicoes"] += d["quantidade"]; x["anualizado"] += d["anualizado"]; x["custo_2027"] += d["custo_2027"]
    for x in por_proj.values():
        x["anualizado"], x["custo_2027"] = _arred(x["anualizado"]), _arred(x["custo_2027"])
    return {
        "itens": itens, "por_projeto": list(por_proj.values()),
        "totais": {"posicoes": sum(d["quantidade"] for d in itens), "anualizado": _arred(sum(d["anualizado"] for d in itens)),
                   "custo_2027": _arred(sum(d["custo_2027"] for d in itens)), "incompletos": sum(1 for d in itens if d["faltando"])},
        "tabela": pessoal.tabela_salarial(), "reajuste": reaj,
        "parametros": [{"chave": k, "valor": par[k], "descricao": v[1], "padrao": v[0]} for k, v in pessoal.PARAMETROS.items()],
        "projetos": [{"orcamento": o, "descricao": p["descricao"], "origem": p["origem"], "gerente": p["gerente"]} for o, p in projetos.items()],
        "tarefas": tarefas_dos_projetos(c, "headcount", list(projetos)),
    }


def _valida(d: HcIn, c: sqlite3.Connection | None = None) -> None:
    if not pessoal.faixa(d.trajetoria, d.nivel, d.grupo):
        raise HTTPException(422, "Trajetória, nível e grupo não existem na Tabela Salarial.")
    if c is not None and (d.edt or d.tarefa) and not c.execute(
            "SELECT 1 FROM linhas WHERE ciclo=2027 AND orcamento=? AND edt=? AND tarefa=? LIMIT 1", (d.orcamento, d.edt, d.tarefa)).fetchone():
        raise HTTPException(422, "A tarefa escolhida não existe nesse projeto.")


def _uma(c: sqlite3.Connection, hid: int) -> dict:
    return _calc(c.execute("SELECT * FROM headcount WHERE id=?", (hid,)).fetchone(), pessoal.parametros(c), _reajuste(c))


@router.post("", status_code=201)
def criar(d: HcIn, u: dict = Depends(usuario_liberado)):
    _valida(d)
    with tx() as c:
        exige_acesso(c, u, d.orcamento)
        _valida(d, c)
        cur = c.execute("INSERT INTO headcount (orcamento, funcao, cargo, trajetoria, nivel, grupo, posicao, mes_inicio, quantidade, "
                        "justificativa, edt, tarefa, atualizado_por) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (d.orcamento, d.funcao.strip(), d.cargo.strip(), d.trajetoria, d.nivel, d.grupo, d.posicao, d.mes_inicio,
                         d.quantidade, d.justificativa.strip(), d.edt, d.tarefa, u["login"]))
        audit(c, u["login"], "incluiu headcount", d.orcamento, detalhe=f"{d.funcao or d.cargo} {d.trajetoria}/{d.nivel}/{d.grupo} x{d.quantidade}")
        sync.sincronizar(c, d.orcamento, u["login"])
        return _uma(c, cur.lastrowid)


@router.put("/{hid}")
def editar(hid: int, d: HcIn, u: dict = Depends(usuario_liberado)):
    _valida(d)
    with tx() as c:
        atual = c.execute("SELECT * FROM headcount WHERE id=?", (hid,)).fetchone()
        if not atual:
            raise HTTPException(404, "Posição não encontrada.")
        exige_acesso(c, u, atual["orcamento"]); exige_acesso(c, u, d.orcamento)
        _valida(d, c)
        c.execute("UPDATE headcount SET orcamento=?, funcao=?, cargo=?, trajetoria=?, nivel=?, grupo=?, posicao=?, mes_inicio=?, quantidade=?, "
                  "justificativa=?, edt=?, tarefa=?, atualizado_por=?, atualizado_em=datetime('now') WHERE id=?",
                  (d.orcamento, d.funcao.strip(), d.cargo.strip(), d.trajetoria, d.nivel, d.grupo, d.posicao, d.mes_inicio, d.quantidade,
                   d.justificativa.strip(), d.edt, d.tarefa, u["login"], hid))
        audit(c, u["login"], "editou headcount", d.orcamento, detalhe=f"id {hid}")
        for o in {atual["orcamento"], d.orcamento}:
            sync.sincronizar(c, o, u["login"])
        return _uma(c, hid)


@router.delete("/{hid}")
def excluir(hid: int, u: dict = Depends(usuario_liberado)):
    with tx() as c:
        atual = c.execute("SELECT * FROM headcount WHERE id=?", (hid,)).fetchone()
        if not atual:
            raise HTTPException(404, "Posição não encontrada.")
        exige_acesso(c, u, atual["orcamento"])
        c.execute("DELETE FROM headcount WHERE id=?", (hid,))
        audit(c, u["login"], "excluiu headcount", atual["orcamento"], detalhe=f"id {hid}: {atual['funcao'] or atual['cargo']}")
        sync.sincronizar(c, atual["orcamento"], u["login"])
    return {"ok": True}


@router.put("/parametros/valores")
def gravar_parametros(d: ParamIn, u: dict = Depends(exige_admin)):
    for k, v in d.valores.items():
        if k not in pessoal.PARAMETROS or v < 0 or v > 100000:
            raise HTTPException(422, f"Parâmetro inválido: {k}.")
    with tx() as c:
        for k, v in d.valores.items():
            c.execute("INSERT INTO hc_parametros (chave, valor) VALUES (?,?) ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor", (k, v))
        audit(c, u["login"], "alterou parâmetros de headcount", detalhe=str(d.valores))
        sync.sincronizar_todos(c, u["login"])
    return {"ok": True}
