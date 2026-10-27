"""Headcount 2027: novas contratações por projeto, com custo anualizado calculado pelas faixas salariais e pelas fórmulas da planilha de custo de pessoal."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from . import equipamentos, pessoal, sync
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
    computador: str = Field(default="", max_length=10)
    monitor: str = Field(default="", max_length=10)
    periferico: str = Field(default="", max_length=10)


class ParamIn(BaseModel):
    valores: dict[str, float]


def _pode(c: sqlite3.Connection, u: dict, r: sqlite3.Row) -> bool:
    """Quem lançou a posição ou quem acompanha o projeto que a custeia."""
    return u["perfil"] == "admin" or r["criado_por"] == u["login"] or r["orcamento"] in permitidos(c, u)


def _projeto_custeio(c: sqlite3.Connection, orcamento: str) -> None:
    """Qualquer projeto de despesa da casa pode custear o headcount, mesmo o de outro gestor."""
    p = c.execute("SELECT tipo FROM projetos WHERE orcamento=?", (orcamento,)).fetchone()
    if not p or p["tipo"] != "despesa":
        raise HTTPException(404, "Projeto não encontrado.")


def _reajuste(c: sqlite3.Connection) -> float:
    r = c.execute("SELECT valor FROM premissas WHERE chave='reajuste_pessoal'").fetchone()
    return float(r[0]) if r else 0.0


def _calc(r: sqlite3.Row, par: dict, reaj: float) -> dict:
    f = pessoal.faixa(r["trajetoria"], r["nivel"], r["grupo"])
    base = pessoal.salario_na_faixa(f, r["posicao"]) if f else 0.0
    salario = round(base * (1 + reaj / 100), 2)
    cm = pessoal.custo_mensal(salario, par)
    q, meses = r["quantidade"], 13 - r["mes_inicio"]
    eq = equipamentos.custo(r["computador"], r["monitor"], r["periferico"])
    return {"id": r["id"], "orcamento": r["orcamento"], "funcao": r["funcao"], "cargo": r["cargo"], "trajetoria": r["trajetoria"],
            "nivel": r["nivel"], "grupo": r["grupo"], "posicao": r["posicao"], "mes_inicio": r["mes_inicio"], "quantidade": q,
            "justificativa": r["justificativa"], "edt": r["edt"], "tarefa": r["tarefa"], "atualizado_por": r["atualizado_por"],
            "faixa": f, "salario_tabela": base, "custo": cm, "meses_2027": meses,
            "computador": r["computador"], "monitor": r["monitor"], "periferico": r["periferico"],
            "equipamentos": {**eq["por_tipo"], "unitario": eq["total"], "total": _arred(eq["total"] * q),
                             "nomes": {t: (i["nome"] if i else "") for t, i in eq["itens"].items()}},
            "anualizado": _arred(cm["anual"] * q), "custo_2027": _arred(cm["mensal"] * meses * q + eq["total"] * q),
            "faltando": [n for n, ok in (("função", r["funcao"].strip()), ("cargo", r["cargo"].strip()),
                                         ("justificativa", r["justificativa"].strip()),
                                         ("tarefa do orçamento que recebe o valor", r["edt"] and r["tarefa"])) if not ok]}


@router.get("")
def listar(u: dict = Depends(usuario_liberado), c: sqlite3.Connection = Depends(_conn)):
    meus = permitidos(c, u)
    par, reaj = pessoal.parametros(c), _reajuste(c)
    projetos = {r["orcamento"]: r for r in c.execute(
        "SELECT orcamento, descricao, origem, gerente, tipo FROM projetos ORDER BY orcamento")}
    itens = []
    for r in c.execute("SELECT * FROM headcount ORDER BY orcamento, id"):
        if not (u["perfil"] == "admin" or r["orcamento"] in meus or r["criado_por"] == u["login"]):
            continue
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
        "tabela": pessoal.tabela_salarial(), "tabela_nome": pessoal.tabela_info()["nome"], "reajuste": reaj,
        "catalogo": {"itens": equipamentos.catalogo(), "atualizado_em": equipamentos.carregar()["atualizado_em"]},
        "parametros": [{"chave": k, "valor": par[k], "descricao": v[1], "padrao": v[0]} for k, v in pessoal.PARAMETROS.items()],
        "projetos": [{"orcamento": o, "descricao": p["descricao"], "origem": p["origem"], "gerente": p["gerente"], "meu": o in meus}
                     for o, p in projetos.items() if p["tipo"] == "despesa"],
        "tarefas": tarefas_dos_projetos(c, "headcount", [o for o, p in projetos.items() if p["tipo"] == "despesa"]),
    }


def _valida(d: HcIn, c: sqlite3.Connection | None = None) -> None:
    if not pessoal.faixa(d.trajetoria, d.nivel, d.grupo):
        raise HTTPException(422, "Trajetória, nível e grupo não existem na Tabela Salarial.")
    for tipo in ("computador", "monitor", "periferico"):
        cod = getattr(d, tipo)
        if cod and not equipamentos.item(cod, tipo):
            raise HTTPException(422, f"Equipamento '{cod}' não existe no catálogo de {tipo}.")
    if c is not None and (d.edt or d.tarefa) and not c.execute(
            "SELECT 1 FROM linhas WHERE ciclo=2027 AND orcamento=? AND edt=? AND tarefa=? LIMIT 1", (d.orcamento, d.edt, d.tarefa)).fetchone():
        raise HTTPException(422, "A tarefa escolhida não existe nesse projeto.")


def _uma(c: sqlite3.Connection, hid: int) -> dict:
    return _calc(c.execute("SELECT * FROM headcount WHERE id=?", (hid,)).fetchone(), pessoal.parametros(c), _reajuste(c))


@router.post("", status_code=201)
def criar(d: HcIn, u: dict = Depends(usuario_liberado)):
    _valida(d)
    with tx() as c:
        _projeto_custeio(c, d.orcamento)
        _valida(d, c)
        cur = c.execute("INSERT INTO headcount (orcamento, funcao, cargo, trajetoria, nivel, grupo, posicao, mes_inicio, quantidade, "
                        "justificativa, edt, tarefa, computador, monitor, periferico, criado_por, atualizado_por) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (d.orcamento, d.funcao.strip(), d.cargo.strip(), d.trajetoria, d.nivel, d.grupo, d.posicao, d.mes_inicio,
                         d.quantidade, d.justificativa.strip(), d.edt, d.tarefa, d.computador, d.monitor, d.periferico, u["login"], u["login"]))
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
        if not _pode(c, u, atual):
            raise HTTPException(404, "Posição não encontrada.")
        _projeto_custeio(c, d.orcamento)
        _valida(d, c)
        c.execute("UPDATE headcount SET orcamento=?, funcao=?, cargo=?, trajetoria=?, nivel=?, grupo=?, posicao=?, mes_inicio=?, quantidade=?, "
                  "justificativa=?, edt=?, tarefa=?, computador=?, monitor=?, periferico=?, atualizado_por=?, atualizado_em=datetime('now') WHERE id=?",
                  (d.orcamento, d.funcao.strip(), d.cargo.strip(), d.trajetoria, d.nivel, d.grupo, d.posicao, d.mes_inicio, d.quantidade,
                   d.justificativa.strip(), d.edt, d.tarefa, d.computador, d.monitor, d.periferico, u["login"], hid))
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
        if not _pode(c, u, atual):
            raise HTTPException(404, "Posição não encontrada.")
        c.execute("DELETE FROM headcount WHERE id=?", (hid,))
        audit(c, u["login"], "excluiu headcount", atual["orcamento"], detalhe=f"id {hid}: {atual['funcao'] or atual['cargo']}")
        sync.sincronizar(c, atual["orcamento"], u["login"])
    return {"ok": True}


@router.get("/parametros")
def ler_parametros(_: dict = Depends(exige_admin), c: sqlite3.Connection = Depends(_conn)):
    par = pessoal.parametros(c)
    return {"reajuste": _reajuste(c), "parametros": [{"chave": k, "valor": par[k], "descricao": v[1], "padrao": v[0]} for k, v in pessoal.PARAMETROS.items()]}


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
