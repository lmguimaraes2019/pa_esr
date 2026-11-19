"""Execução de 2026 em detalhe: um lançamento por linha da base do Protheus, para o gestor conferir os valores."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends

from .api import _arred, _chave_nome, _conn, _gerencia_do, permitidos, usuario_liberado

router = APIRouter(prefix="/api/execucao-detalhe", tags=["execucao"])


@router.get("")
def detalhe(u: dict = Depends(usuario_liberado), c: sqlite3.Connection = Depends(_conn)):
    ids = permitidos(c, u, extintos=True)
    ger_de = {_chave_nome(x["nome"]): x["gerencia"] for x in c.execute("SELECT nome, gerencia FROM users WHERE COALESCE(gerencia,'')<>''")}
    proj = {r["orcamento"]: r for r in c.execute("SELECT orcamento, n_projeto, descricao, origem, gerente, extinto FROM projetos")}
    itens = []
    for r in c.execute("SELECT * FROM lancamentos ORDER BY digitacao, id"):
        if r["orcamento"] not in ids or r["orcamento"] not in proj:
            continue
        p = proj[r["orcamento"]]
        itens.append({
            "id": r["id"], "tipo": r["tipo"], "orcamento": r["orcamento"], "projeto": p["descricao"], "extinto": bool(p["extinto"]),
            "gerencia": _gerencia_do(p["gerente"], ger_de), "gerente": p["gerente"], "origem": p["origem"],
            "centro_custo": r["centro_custo"], "diretoria": r["diretoria"], "edt": r["edt"], "tarefa": r["tarefa"],
            "emissao": r["emissao"], "digitacao": r["digitacao"], "vencimento": r["vencimento"], "baixa": r["baixa"],
            "sc": r["sc"], "nota_fiscal": r["nota_fiscal"], "fornecedor": r["fornecedor"], "valor": r["valor"],
            "grupo": r["grupo"], "conta": (r["conta_codigo"] + " " + r["conta_desc"]).strip(), "produto": r["produto"],
            "solicitante": r["solicitante"], "contrato": r["contrato"], "obs": r["obs"],
        })
    marks = ",".join("?" for _ in ids) or "''"
    ref = c.execute(f"SELECT COALESCE(SUM(realizado),0), COALESCE(SUM(empenhado),0) FROM execucao WHERE orcamento IN ({marks})", sorted(ids)).fetchone()
    return {"itens": itens, "carregado": bool(c.execute("SELECT 1 FROM lancamentos LIMIT 1").fetchone()),
            "conferencia": {"realizado_execucao": _arred(ref[0]), "empenhado_execucao": _arred(ref[1]),
                            "realizado_lancamentos": _arred(sum(x["valor"] for x in itens if x["tipo"] == "Realizado")),
                            "empenhado_lancamentos": _arred(sum(x["valor"] for x in itens if x["tipo"] == "Empenhado"))}}
