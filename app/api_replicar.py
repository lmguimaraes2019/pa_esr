"""Replicar para 2027: leva o plano 2027 de um projeto existente para um orçamento novo, com outro nome e outra origem de recurso.

O projeto de origem fica sem linhas de 2027 e marcado como migrado (para qual projeto, com que nome e origem).
Viagens, eventos, headcount, receitas, entregas e vínculos estratégicos acompanham o plano, para nada ficar para trás.
"""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from . import config, export_xlsx, sync
from .api import _arred, _conn, exige_acesso, usuario_liberado
from .db import MESES, audit, tx

router = APIRouter(prefix="/api")
SOMA = "+".join(MESES)


class ReplicarIn(BaseModel):
    descricao: str = Field(min_length=3, max_length=200)
    origem: str = Field(min_length=1, max_length=100)
    gerente: str | None = Field(default=None, max_length=100)


def _motivo(p: sqlite3.Row) -> str:
    if p["novo"]:
        return "Este orçamento foi criado para 2027 e não tem um 2026 para migrar."
    if p["replicado_para"]:
        return f"Este projeto já foi migrado para 2027 como {p['replicado_para']}."
    return ""


def _contagem(c: sqlite3.Connection, o: str) -> dict:
    q = lambda sql, *a: c.execute(sql, a).fetchone()[0]
    return {"linhas": q("SELECT COUNT(*) FROM linhas WHERE ciclo=? AND orcamento=?", config.CICLO_PLANO, o),
            "valor": _arred(q(f"SELECT COALESCE(SUM({SOMA}),0) FROM linhas WHERE ciclo=? AND orcamento=?", config.CICLO_PLANO, o)),
            "viagens": q("SELECT COUNT(*) FROM viagens WHERE ciclo=? AND orcamento=?", config.CICLO_PLANO, o),
            "eventos": q("SELECT COUNT(*) FROM eventos WHERE orcamento=?", o),
            "headcount": q("SELECT COUNT(*) FROM headcount WHERE orcamento=?", o),
            "receitas": q("SELECT COUNT(*) FROM receitas WHERE ciclo=? AND orcamento=?", config.CICLO_PLANO, o),
            "entregas": q("SELECT COUNT(*) FROM entregas WHERE orcamento=?", o),
            "vinculos": q("SELECT COUNT(*) FROM projeto_estrategia WHERE orcamento=?", o)}


@router.get("/projetos/{orcamento}/replicar")
def previa(orcamento: str, u: dict = Depends(usuario_liberado), c: sqlite3.Connection = Depends(_conn)):
    p = exige_acesso(c, u, orcamento)
    m = _motivo(p)
    return {"elegivel": not m, "motivo": m, "contagem": _contagem(c, orcamento)}


@router.post("/projetos/{orcamento}/replicar", status_code=201)
def replicar(orcamento: str, d: ReplicarIn, u: dict = Depends(usuario_liberado)):
    ld = export_xlsx._listas_template()
    if d.origem not in ld["origens"]:
        raise HTTPException(422, "Origem de recurso fora da lista do template.")
    with tx() as c:
        p = exige_acesso(c, u, orcamento)
        if _motivo(p):
            raise HTTPException(409, _motivo(p))
        gerente = d.gerente or p["gerente"]
        if gerente not in ld["gerentes"] and gerente != p["gerente"]:
            raise HTTPException(422, "Gerente fora da lista do template.")
        n = 1 + max([int(r[0][4:]) for r in c.execute("SELECT orcamento FROM projetos WHERE orcamento LIKE 'N27-%'") if r[0][4:].isdigit()] or [0])
        chave = f"N27-{n:03d}"
        nome = d.descricao.strip()
        cont = _contagem(c, orcamento)
        c.execute("""INSERT INTO projetos (orcamento, n_projeto, descricao, origem, origem_2027, gerente, diretoria, novo, tipo, detalhe, replicado_de)
                     VALUES (?,?,?,?,?,?,?,1,?,?,?)""", (chave, "", nome, d.origem, d.origem, gerente, p["diretoria"], p["tipo"], p["detalhe"], orcamento))
        c.execute("UPDATE linhas SET orcamento=?, base_id=NULL, atualizado_por=?, atualizado_em=datetime('now') WHERE ciclo=? AND orcamento=?", (chave, u["login"], config.CICLO_PLANO, orcamento))
        c.execute("UPDATE receitas SET orcamento=?, base_id=NULL WHERE ciclo=? AND orcamento=?", (chave, config.CICLO_PLANO, orcamento))
        c.execute("UPDATE viagens SET orcamento=? WHERE ciclo=? AND orcamento=?", (chave, config.CICLO_PLANO, orcamento))
        for t in ("eventos", "headcount", "entregas", "projeto_estrategia"):
            c.execute(f"UPDATE {t} SET orcamento=? WHERE orcamento=?", (chave, orcamento))
        c.execute("INSERT OR IGNORE INTO user_projetos (user_id, orcamento) SELECT user_id, ? FROM user_projetos WHERE orcamento=?", (chave, orcamento))
        c.execute("INSERT OR IGNORE INTO user_projetos (user_id, orcamento) VALUES (?,?)", (u["id"], chave))
        c.execute("""UPDATE projetos SET replicado_para=?, replicado_nome=?, replicado_origem=?, replicado_em=datetime('now'), replicado_por=? WHERE orcamento=?""",
                  (chave, nome, d.origem, u["login"], orcamento))
        sync.sincronizar_todos(c, u["login"])
        audit(c, u["login"], "replicou projeto para 2027", orcamento, detalhe=f"para {chave} | {nome} | {d.origem} | {cont}")
        audit(c, u["login"], "projeto criado por replicação", chave, detalhe=f"de {orcamento} | {p['descricao']}")
    return {"orcamento": chave, "movido": cont}
