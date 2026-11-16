"""Estratégia de financiamento dos projetos: de onde vem o recurso que paga cada despesa de 2027.

Projetos de fomento (origem Fomento ou FNDCT) já têm a fonte definida. Os demais indicam a fonte: transferência intercompany,
receita própria (externa) ou TBD, quando ainda não há fonte. Enquanto o gestor não indicar nada, o projeto fica com pendência."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends

from . import config
from .api import _arred, _conn, permitidos, usuario_liberado
from .db import MESES
from .fontes import FONTES, ORDEM, efetivo

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
    grupos = {k: {"fonte": k, "nome": FONTES[k], "n": 0, "valor": 0.0, "projetos": []} for k in ORDEM}
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
    return {"grupos": [grupos[k] for k in ORDEM], "total": total, "intercompany_receita": _arred(inter),
            "intercompany_custeado": custeado, "intercompany_saldo": _arred(inter - custeado),
            "pendentes": grupos[""]["n"]}


@router.get("")
def listar(u: dict = Depends(usuario_liberado), c: sqlite3.Connection = Depends(_conn)):
    return quadro(c, list(permitidos(c, u)))
