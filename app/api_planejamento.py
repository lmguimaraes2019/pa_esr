"""Visão do planejamento 2027: o que falta em cada etapa, por projeto, e a conclusão de cada usuário."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from . import config, viagens as vg
from .api import _arred, _conn, exige_acesso, exige_admin, permitidos, usuario_liberado
from .api_eventos import _calc as _calc_evento, _dolar
from .api_headcount import _calc as _calc_hc, _reajuste
from . import pessoal
from .db import MESES, audit, tx

router = APIRouter(prefix="/api/planejamento")


class ConcluirIn(BaseModel):
    concluido: bool = True
    obs: str = Field(default="", max_length=500)


def resumir(c: sqlite3.Connection, ids: list[str]) -> dict[str, dict]:
    """Situação de cada projeto nas cinco etapas do plano 2027."""
    ids = sorted(ids)
    marks = ",".join("?" for _ in ids) or "''"
    nomes = {r["orcamento"]: r for r in c.execute(f"SELECT orcamento, descricao, gerente, novo FROM projetos WHERE orcamento IN ({marks})", ids)}
    out = {o: {"orcamento": o, "projeto": nomes[o]["descricao"], "gerente": nomes[o]["gerente"], "novo": bool(nomes[o]["novo"]),
               "despesas": {"aprovado": 0.0, "plano": 0.0, "linhas": 0, "ajustadas": 0, "novas": 0, "excluidas": 0, "bloqueadas": 0},
               "receitas": {"n": 0, "total": 0.0},
               "viagens": {"n": 0, "total": 0.0, "pendentes": 0},
               "eventos": {"n": 0, "total": 0.0, "pendentes": 0},
               "headcount": {"n": 0, "total": 0.0, "pendentes": 0}} for o in ids if o in nomes}

    # despesas: compara cada linha de 2027 com a de 2026
    usadas: set[int] = set()
    sql = (f"SELECT l.orcamento, l.fonte, l.base_id, {', '.join('l.' + m for m in MESES)}, "
           f"{', '.join('b.' + m + ' AS b_' + m for m in MESES)} FROM linhas l LEFT JOIN linhas b ON b.id=l.base_id "
           f"WHERE l.ciclo=? AND l.orcamento IN ({marks})")
    for r in c.execute(sql, (config.CICLO_PLANO, *ids)):
        d = out[r["orcamento"]]["despesas"]
        d["linhas"] += 1
        d["plano"] += sum(r[m] for m in MESES)
        if r["base_id"] is not None:
            usadas.add(r["base_id"])
        if r["fonte"] != "manual":
            d["bloqueadas"] += 1
        elif r["base_id"] is None:
            d["novas"] += 1
        elif any(abs(r[m] - r["b_" + m]) >= 0.005 for m in MESES):
            d["ajustadas"] += 1
    for r in c.execute(f"SELECT id, orcamento, {'+'.join(MESES)} AS t FROM linhas WHERE ciclo=? AND orcamento IN ({marks})", (config.CICLO_BASE, *ids)):
        d = out[r["orcamento"]]["despesas"]
        d["aprovado"] += r["t"]
        if r["id"] not in usadas:
            d["excluidas"] += 1

    for r in c.execute(f"SELECT orcamento, {'+'.join(MESES)} AS t FROM receitas WHERE ciclo=? AND orcamento IN ({marks})", (config.CICLO_PLANO, *ids)):
        out[r["orcamento"]]["receitas"]["n"] += 1
        out[r["orcamento"]]["receitas"]["total"] += r["t"]

    tar, bv, dolar = vg.tarifas_map(c), vg.bagagem_vezes(c), _dolar(c)
    for v in c.execute(f"SELECT * FROM viagens WHERE ciclo=? AND orcamento IN ({marks})", (config.CICLO_PLANO, *ids)):
        t = tar.get((v["tipo"], v["origem"], v["destino"]))
        x = out[v["orcamento"]]["viagens"]
        x["n"] += 1
        x["total"] += vg.calcular(v["tipo"], t, v["n_viagens"], v["dias"], v["pernoites"], bv)["total"]
        if t is None or not v["edt"] or not v["tarefa"]:
            x["pendentes"] += 1
    for r in c.execute(f"SELECT * FROM eventos WHERE orcamento IN ({marks})", ids):
        d = _calc_evento(r, tar, bv, dolar)
        x = out[r["orcamento"]]["eventos"]
        x["n"] += 1; x["total"] += d["total"]; x["pendentes"] += 0 if d["completo"] else 1
    par, reaj = pessoal.parametros(c), _reajuste(c)
    for r in c.execute(f"SELECT * FROM headcount WHERE orcamento IN ({marks})", ids):
        d = _calc_hc(r, par, reaj)
        x = out[r["orcamento"]]["headcount"]
        x["n"] += r["quantidade"]; x["total"] += d["custo_2027"]; x["pendentes"] += 1 if d["faltando"] else 0

    for p in out.values():
        for k in ("despesas", "receitas", "viagens", "eventos", "headcount"):
            for f in ("aprovado", "plano", "total"):
                if f in p[k]:
                    p[k][f] = _arred(p[k][f])
        p["pendencias"] = p["viagens"]["pendentes"] + p["eventos"]["pendentes"] + p["headcount"]["pendentes"]
    return out


def _etapas(projetos: list[dict]) -> dict:
    soma = lambda k, f: sum(p[k][f] for p in projetos)
    return {
        "despesas": {"projetos": len(projetos), "sem_ajuste": sum(1 for p in projetos if not (p["despesas"]["ajustadas"] or p["despesas"]["novas"] or p["despesas"]["excluidas"])),
                     "plano": _arred(soma("despesas", "plano")), "ajustadas": soma("despesas", "ajustadas") + soma("despesas", "novas") + soma("despesas", "excluidas")},
        "receitas": {"n": soma("receitas", "n"), "total": _arred(soma("receitas", "total")), "sem_receita": sum(1 for p in projetos if not p["receitas"]["n"])},
        "viagens": {"n": soma("viagens", "n"), "total": _arred(soma("viagens", "total")), "pendentes": soma("viagens", "pendentes")},
        "eventos": {"n": soma("eventos", "n"), "total": _arred(soma("eventos", "total")), "pendentes": soma("eventos", "pendentes")},
        "headcount": {"n": soma("headcount", "n"), "total": _arred(soma("headcount", "total")), "pendentes": soma("headcount", "pendentes")},
    }


def _situacao(c: sqlite3.Connection, u: dict) -> dict:
    projetos = list(resumir(c, list(permitidos(c, u))).values())
    etapas = _etapas(projetos)
    # headcount que o usuário lançou em projeto de outro gestor também é pendência dele
    ids = permitidos(c, u)
    par, reaj = pessoal.parametros(c), _reajuste(c)
    for r in c.execute("SELECT * FROM headcount WHERE criado_por=?", (u["login"],)).fetchall():
        if r["orcamento"] in ids:
            continue
        d = _calc_hc(r, par, reaj)
        x = etapas["headcount"]
        x["n"] += r["quantidade"]; x["total"] = _arred(x["total"] + d["custo_2027"]); x["pendentes"] += 1 if d["faltando"] else 0
    pend = etapas["viagens"]["pendentes"] + etapas["eventos"]["pendentes"] + etapas["headcount"]["pendentes"]
    return {"projetos": projetos, "etapas": etapas, "pendencias": pend}


DIRETORIA = ("leandro", "celia")      # projetos cadastrados com estes gerentes pertencem à Diretoria Adjunta
GER_DSS = "DSS - Diretoria de Serviços e Soluções"
GER_DIR = "Diretoria Adjunta"
ORDEM_CARGO = {"diretor_executivo": 0, "pmo": 1, "diretor_adjunto": 2, "gerente": 3, "coordenador": 4}


def _sem_acento(t: str) -> str:
    import unicodedata
    return "".join(ch for ch in unicodedata.normalize("NFD", t or "") if unicodedata.category(ch) != "Mn").lower().strip()


def _executado(c: sqlite3.Connection, ids: set[str]) -> float:
    if not ids:
        return 0.0
    marks = ",".join("?" for _ in ids)
    return _arred(c.execute(f"SELECT COALESCE(SUM(realizado),0) FROM execucao WHERE orcamento IN ({marks})", sorted(ids)).fetchone()[0])


def _agrega(c: sqlite3.Connection, ids) -> dict:
    ids = sorted(set(ids))
    res = list(resumir(c, ids).values())
    return {"projetos": len(res), "aprovado": _arred(sum(p["despesas"]["aprovado"] for p in res)), "executado": _executado(c, set(ids)),
            "plano": _arred(sum(p["despesas"]["plano"] for p in res)), "pendencias": sum(p["pendencias"] for p in res)}


def _nivel(gerencia: str) -> str:
    g = _sem_acento(gerencia)
    return "dss" if g.startswith("dss") else "diretoria" if g.startswith("diretoria adjunta") else "gerencia"


def _por_gerencia(c: sqlite3.Connection) -> list[dict]:
    """Acompanhamento do admin, em níveis: DSS, Diretoria Adjunta e gerências.
    DSS soma todos os projetos; a Diretoria Adjunta, os projetos de Leandro e Célia; cada gerência, os projetos
    que seus gestores acompanham (cada projeto uma vez, ainda que gerente e coordenador o acompanhem)."""
    todos_ids = [r[0] for r in c.execute("SELECT orcamento FROM projetos")]
    dir_ids = [r["orcamento"] for r in c.execute("SELECT orcamento, gerente FROM projetos")
               if any(_sem_acento(r["gerente"]).startswith(k) for k in DIRETORIA)]
    grupos: dict[str, list[dict]] = {GER_DSS: [], GER_DIR: []}
    for r in c.execute("SELECT * FROM users WHERE ativo=1 ORDER BY nome").fetchall():
        nome = (r["gerencia"] or "").strip()
        nv = _nivel(nome)
        grupos.setdefault(GER_DSS if nv == "dss" else GER_DIR if nv == "diretoria" else nome, []).append(dict(r))
    out = []
    ordem = sorted(grupos.items(), key=lambda kv: ({GER_DSS: 0, GER_DIR: 1}.get(kv[0], 3 if kv[0] == "" else 2), kv[0].lower()))
    for nome, membros in ordem:
        nv = _nivel(nome) if nome else "gerencia"
        if nv != "gerencia" and not membros and nv != "dss" and not dir_ids:
            continue
        ids: set[str] = set()
        pessoas, pend, todos_concluidos, conc_em = [], 0, True, None
        for m in membros:
            cu = c.execute("SELECT concluido_em, obs FROM conclusoes WHERE login=?", (m["login"],)).fetchone()
            base = {"login": m["login"], "nome": m["nome"], "cargo": m["cargo"], "projetos": None, "plano": None, "pendencias": 0,
                    "concluido_em": cu["concluido_em"] if cu else None, "obs": cu["obs"] if cu else ""}
            if nv == "diretoria":      # projetos em que o nome do usuário é o gerente cadastrado
                pri = _sem_acento(m["nome"]).split(" ")[0]
                meus = [r["orcamento"] for r in c.execute("SELECT orcamento, gerente FROM projetos") if _sem_acento(r["gerente"]).startswith(pri)]
                a = _agrega(c, meus)
                base.update(projetos=a["projetos"], plano=a["plano"], pendencias=a["pendencias"], aprovado=a["aprovado"], executado=a["executado"])
            elif m["perfil"] != "admin" and nv == "gerencia":
                ids |= set(permitidos(c, m))
                su = _situacao(c, m)
                pend += su["pendencias"]
                todos_concluidos = todos_concluidos and bool(cu)
                if cu and (conc_em is None or cu["concluido_em"] > conc_em):
                    conc_em = cu["concluido_em"]
                base.update(projetos=len(su["projetos"]), plano=su["etapas"]["despesas"]["plano"], pendencias=su["pendencias"])
            pessoas.append(base)
        pessoas.sort(key=lambda p: (ORDEM_CARGO.get(p["cargo"], 9), p["nome"].lower()))
        if nv == "dss":
            a = _agrega(c, todos_ids)
        elif nv == "diretoria":
            a = _agrega(c, dir_ids)
        else:
            a = _agrega(c, ids)
            a["pendencias"] = pend
        out.append({"gerencia": nome, "nivel": nv, **a, "concluido": nv == "gerencia" and todos_concluidos and bool(membros),
                    "concluido_em": conc_em if todos_concluidos else None, "pessoas": pessoas})
    return out


@router.get("")
def planejamento(u: dict = Depends(usuario_liberado), c: sqlite3.Connection = Depends(_conn)):
    s = _situacao(c, u)
    conc = c.execute("SELECT concluido_em, obs FROM conclusoes WHERE login=?", (u["login"],)).fetchone()
    s["concluido"] = dict(conc) if conc else None
    if u["perfil"] == "admin":
        s["gerencias"] = _por_gerencia(c)
    return s


@router.get("/projeto/{orcamento}")
def do_projeto(orcamento: str, u: dict = Depends(usuario_liberado), c: sqlite3.Connection = Depends(_conn)):
    exige_acesso(c, u, orcamento)
    return resumir(c, [orcamento])[orcamento]


@router.post("/concluir")
def concluir(d: ConcluirIn, u: dict = Depends(usuario_liberado)):
    with tx() as c:
        if d.concluido:
            s = _situacao(c, u)
            if s["pendencias"]:
                raise HTTPException(409, f"Ainda há {s['pendencias']} pendência(s) em Viagens, Eventos ou Headcount. Resolva antes de concluir.")
            c.execute("INSERT INTO conclusoes (login, obs) VALUES (?,?) ON CONFLICT(login) DO UPDATE SET concluido_em=datetime('now'), obs=excluded.obs",
                      (u["login"], d.obs.strip()))
            audit(c, u["login"], "concluiu o planejamento 2027", detalhe=d.obs.strip())
        else:
            c.execute("DELETE FROM conclusoes WHERE login=?", (u["login"],))
            audit(c, u["login"], "reabriu o planejamento 2027")
    return {"ok": True}
