"""Outros projetos: os da Diretoria (Adjunta ou Executiva) onde o gestor lançou viagens, eventos ou headcount.

Ficam fora dos quadros de orçamento do gestor (resumo executivo, projetos, plano 2027, execução) e aparecem aqui, à parte."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends

from . import api_eventos, api_headcount, api_viagens
from .api import _arred, _chave_nome, _conn, _gerencia_do, permitidos, proprios, usuario_liberado

router = APIRouter(prefix="/api/outros-projetos", tags=["outros"])


@router.get("")
def listar(u: dict = Depends(usuario_liberado), c: sqlite3.Connection = Depends(_conn)):
    if u["perfil"] == "admin":
        return {"projetos": [], "total": 0.0}
    vg = {x["orcamento"]: x for x in api_viagens.listar(u, c)["outros"]}
    ev = {x["orcamento"]: x for x in api_eventos.listar(u, c)["outros"]}
    hc = {x["orcamento"]: x for x in api_headcount.listar(u, c)["outros"]}
    ids = set(vg) | set(ev) | set(hc) | (permitidos(c, u) - proprios(c, u))
    ger_de = {_chave_nome(x["nome"]): x["gerencia"] for x in c.execute("SELECT nome, gerencia FROM users WHERE COALESCE(gerencia,'')<>''")}
    out = []
    for o in sorted(ids):
        p = c.execute("SELECT orcamento, descricao, gerente FROM projetos WHERE orcamento=?", (o,)).fetchone()
        if not p:
            continue
        v, e, h = vg.get(o), ev.get(o), hc.get(o)
        valores = {"viagens": v["plano_2027"] if v else 0.0, "eventos": e["total"] if e else 0.0, "headcount": h["custo_2027"] if h else 0.0}
        out.append({"orcamento": o, "projeto": p["descricao"], "gerente": p["gerente"], "gerencia": _gerencia_do(p["gerente"], ger_de),
                    "viagens_n": v["viagens"] if v else 0, "eventos_n": e["eventos"] if e else 0, "posicoes_n": h["posicoes"] if h else 0,
                    **valores, "total": _arred(sum(valores.values())),
                    "realizado_2026": _arred(c.execute("SELECT COALESCE(SUM(realizado),0) FROM execucao WHERE orcamento=?", (o,)).fetchone()[0])})
    return {"projetos": out, "total": _arred(sum(x["total"] for x in out))}
