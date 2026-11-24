"""Fluxo do dinheiro em 2027: receitas -> origem dos recursos -> custos (por gerência), só dos projetos do gestor."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends

from . import config, fontes
from .api import _arred, _chave_nome, _conn, _gerencia_do, gerencia_dos_projetos, proprios, usuario_liberado
from .db import MESES

router = APIRouter(prefix="/api/fluxo", tags=["fluxo"])
SOMA = "+".join(MESES)


def fluxo(c: sqlite3.Connection, ids: list[str]) -> dict:
    marks = ",".join("?" for _ in ids) or "''"
    proj = {r["orcamento"]: r for r in c.execute(
        f"SELECT orcamento, descricao, tipo, gerente, extinto, contingenciado, COALESCE(NULLIF(origem_2027,''), origem) AS origem "
        f"FROM projetos WHERE orcamento IN ({marks})", ids)}
    ger_de = {_chave_nome(x["nome"]): x["gerencia"] for x in c.execute("SELECT nome, gerencia FROM users WHERE COALESCE(gerencia,'')<>''")}
    rec: dict[tuple[str, str], float] = {}        # (fonte da receita, origem) -> valor
    custo: dict[tuple[str, str], float] = {}      # (origem, gerência) -> valor
    for r in c.execute(f"SELECT orcamento, fonte, tipo, {SOMA} AS t FROM receitas WHERE ciclo=? AND orcamento IN ({marks})", (config.CICLO_PLANO, *ids)):
        p = proj.get(r["orcamento"])
        if p and not p["extinto"] and r["t"]:
            f = "Transferência intercompany" if r["tipo"] == "intercompany" else (r["fonte"] or "Receita")
            rec[(f, p["origem"] or "Sem origem")] = rec.get((f, p["origem"] or "Sem origem"), 0.0) + r["t"]
    for r in c.execute(f"SELECT orcamento, SUM({SOMA}) AS t FROM linhas WHERE ciclo=? AND orcamento IN ({marks}) GROUP BY orcamento", (config.CICLO_PLANO, *ids)):
        p = proj.get(r["orcamento"])
        if not p or p["extinto"] or not r["t"]:
            continue
        o = p["origem"] or "Sem origem"
        if p["tipo"] == "receita":                # orçamento de receita: o resultado das linhas é receita
            k = ("Centros de receita", o); rec[k] = rec.get(k, 0.0) + r["t"]
        elif not p["contingenciado"]:
            g = _gerencia_do(p["gerente"], ger_de) or "Sem gerência"
            custo[(o, g)] = custo.get((o, g), 0.0) + r["t"]
    base: dict[str, float] = {}                  # aprovado 2026 por gerência (comparação)
    for r in c.execute(f"SELECT orcamento, SUM({SOMA}) AS t FROM linhas WHERE ciclo=? AND orcamento IN ({marks}) GROUP BY orcamento", (config.CICLO_BASE, *ids)):
        p = proj.get(r["orcamento"])
        if p and p["tipo"] != "receita" and r["t"]:
            g = _gerencia_do(p["gerente"], ger_de) or "Sem gerência"
            base[g] = base.get(g, 0.0) + r["t"]
    por_ger: dict[str, float] = {}
    for (o, g), v in custo.items():
        por_ger[g] = por_ger.get(g, 0.0) + v
    gerencias = sorted(({"gerencia": g, "custo": _arred(por_ger.get(g, 0.0)), "base": _arred(base.get(g, 0.0))} for g in set(por_ger) | set(base)),
                       key=lambda x: -max(x["custo"], x["base"]))
    origens = sorted({o for _, o in rec} | {o for o, _ in custo})
    entra = {o: sum(v for (f, oo), v in rec.items() if oo == o) for o in origens}
    sai = {o: sum(v for (oo, g), v in custo.items() if oo == o) for o in origens}
    links_in = [{"de": f, "para": o, "valor": _arred(v)} for (f, o), v in rec.items() if v > 0.004]
    links_out = [{"de": o, "para": g, "valor": _arred(v)} for (o, g), v in custo.items() if v > 0.004]
    for o in origens:       # custo sem receita lançada: vem de recurso próprio da origem (fomento) ou ainda não tem receita
        falta = sai[o] - entra[o]
        if falta > 0.004:
            links_in.append({"de": "Fomento RNP (conta única)" if fontes.eh_fomento(o) else "Sem receita lançada", "para": o, "valor": _arred(falta)})
        elif falta < -0.004:
            links_out.append({"de": o, "para": "Receita acima do custo", "valor": _arred(-falta)})
    quadro = [{"origem": o, "receita": _arred(entra[o]), "custo": _arred(sai[o]), "saldo": _arred(entra[o] - sai[o])} for o in origens]
    return {"gerencias": gerencias, "entra": links_in, "sai": links_out, "origens": quadro,
            "total_receita": _arred(sum(entra.values())), "total_custo": _arred(sum(sai.values()))}


@router.get("")
def listar(u: dict = Depends(usuario_liberado), c: sqlite3.Connection = Depends(_conn), gerencia: str | None = None):
    ids = sorted(proprios(c, u))
    if gerencia:
        por_ger = gerencia_dos_projetos(c)
        ids = [o for o in ids if por_ger.get(o, "Sem gerência definida") == gerencia]
    return fluxo(c, ids)
