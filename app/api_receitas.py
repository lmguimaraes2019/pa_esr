"""Gestão de receitas 2027: previsão mensal por projeto, origem e fonte, comparada à despesa planejada."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from . import config
from .api import _arred, _conn, exige_acesso, permitidos, usuario_liberado
from .db import MESES, NOMES_MESES, audit, tx

router = APIRouter(prefix="/api/receitas")
SOMA = "+".join(MESES)


def _meses(v: list[float]) -> list[float]:
    if len(v) != 12:
        raise ValueError("Informe os 12 meses.")
    if any((x is None) or x != x or x < 0 or x > 1e10 for x in v):
        raise ValueError("Os valores mensais devem ser números positivos.")
    return [round(float(x), 2) for x in v]


class ReceitaIn(BaseModel):
    orcamento: str = Field(min_length=1, max_length=20)
    fonte: str = Field(min_length=1, max_length=80)
    descricao: str = Field(default="", max_length=200)
    meses: list[float]
    obs: str = Field(default="", max_length=1000)
    _m = field_validator("meses")(_meses)


class ReceitaPatch(BaseModel):
    orcamento: str | None = Field(default=None, min_length=1, max_length=20)
    fonte: str | None = Field(default=None, min_length=1, max_length=80)
    descricao: str | None = Field(default=None, max_length=200)
    meses: list[float] | None = None
    obs: str | None = Field(default=None, max_length=1000)

    @field_validator("meses")
    @classmethod
    def _mm(cls, v):
        return None if v is None else _meses(v)


def _linha(r: sqlite3.Row, ref: sqlite3.Row | None) -> dict:
    meses = [_arred(r[m]) for m in MESES]
    out = {"id": r["id"], "orcamento": r["orcamento"], "projeto": r["projeto"], "origem": r["origem"], "gerente": r["gerente"],
           "fonte": r["fonte"], "descricao": r["descricao"], "obs": r["obs"], "meses": meses, "total": _arred(sum(meses)),
           "base_id": r["base_id"], "atualizado_por": r["atualizado_por"], "ref": None}
    if ref is not None:
        rm = [_arred(ref[m]) for m in MESES]
        out["ref"] = {"meses": rm, "total": _arred(sum(rm))}
    return out


_SQL = f"""SELECT r.*, p.descricao AS projeto, p.origem, p.gerente FROM receitas r JOIN projetos p USING (orcamento)
           WHERE r.ciclo = ?"""


@router.get("")
def listar(u: dict = Depends(usuario_liberado), c: sqlite3.Connection = Depends(_conn)):
    ids = sorted(permitidos(c, u))
    marks = ",".join("?" for _ in ids) or "''"
    rows = c.execute(_SQL + f" AND r.orcamento IN ({marks}) ORDER BY p.origem, r.orcamento, r.fonte, r.id",
                     (config.CICLO_PLANO, *ids)).fetchall()
    refs = {r["id"]: r for r in c.execute("SELECT * FROM receitas WHERE ciclo=?", (config.CICLO_BASE,))}
    linhas = [_linha(r, refs.get(r["base_id"])) for r in rows]

    # receita de 2026 que não tem mais linha em 2027 (para a comparação ficar completa)
    usadas = {r["base_id"] for r in rows if r["base_id"]}
    ref_total = sum(x["total"] for x in (_linha_ref(r, c) for r in refs.values() if r["orcamento"] in ids))
    despesa = {r["orcamento"]: _arred(r["t"]) for r in c.execute(
        f"SELECT orcamento, SUM({SOMA}) t FROM linhas WHERE ciclo=? AND orcamento IN ({marks}) GROUP BY orcamento",
        (config.CICLO_PLANO, *ids))}
    despesa_base = {r["orcamento"]: _arred(r["t"]) for r in c.execute(
        f"SELECT orcamento, SUM({SOMA}) t FROM linhas WHERE ciclo=? AND orcamento IN ({marks}) GROUP BY orcamento",
        (config.CICLO_BASE, *ids))}
    despesa_mes = c.execute(
        f"SELECT {', '.join(f'COALESCE(SUM({m}),0) {m}' for m in MESES)} FROM linhas WHERE ciclo=? AND orcamento IN ({marks})",
        (config.CICLO_PLANO, *ids)).fetchone()
    projetos = {r["orcamento"]: r for r in c.execute(
        f"SELECT orcamento, descricao, origem, gerente FROM projetos WHERE orcamento IN ({marks}) ORDER BY orcamento", ids)}

    rec_proj: dict[str, float] = {}
    ref_proj: dict[str, float] = {}
    rec_mes = [0.0] * 12
    for l in linhas:
        rec_proj[l["orcamento"]] = rec_proj.get(l["orcamento"], 0.0) + l["total"]
        for i, v in enumerate(l["meses"]):
            rec_mes[i] += v
    for r in refs.values():
        if r["orcamento"] in projetos:
            ref_proj[r["orcamento"]] = ref_proj.get(r["orcamento"], 0.0) + sum(r[m] for m in MESES)

    por_projeto, por_origem = [], {}
    for o, p in projetos.items():
        rec, ref, desp = rec_proj.get(o, 0.0), ref_proj.get(o, 0.0), despesa.get(o, 0.0)
        por_projeto.append({"orcamento": o, "projeto": p["descricao"], "origem": p["origem"], "gerente": p["gerente"],
                            "receita": _arred(rec), "receita_2026": _arred(ref), "despesa": desp,
                            "despesa_2026": despesa_base.get(o, 0.0), "resultado": _arred(rec - desp)})
        d = por_origem.setdefault(p["origem"], {"origem": p["origem"], "receita": 0.0, "receita_2026": 0.0, "despesa": 0.0,
                                                "despesa_2026": 0.0, "projetos": 0})
        d["receita"] += rec; d["receita_2026"] += ref; d["despesa"] += desp; d["despesa_2026"] += despesa_base.get(o, 0.0)
        d["projetos"] += 1
    for d in por_origem.values():
        for k in ("receita", "receita_2026", "despesa", "despesa_2026"):
            d[k] = _arred(d[k])
        d["resultado"] = _arred(d["receita"] - d["despesa"])
    tot_rec = _arred(sum(rec_mes))
    tot_desp = _arred(sum(despesa.values()))
    return {
        "linhas": linhas,
        "fontes": sorted({l["fonte"] for l in linhas}),
        "projetos": [{"orcamento": o, "descricao": p["descricao"], "origem": p["origem"], "gerente": p["gerente"]} for o, p in projetos.items()],
        "por_projeto": por_projeto, "por_origem": sorted(por_origem.values(), key=lambda d: d["origem"]),
        "mensal": [{"mes": NOMES_MESES[i], "receita": _arred(rec_mes[i]), "despesa": _arred(despesa_mes[m])} for i, m in enumerate(MESES)],
        "totais": {"receita": tot_rec, "receita_2026": _arred(ref_total), "despesa": tot_desp,
                   "despesa_2026": _arred(sum(despesa_base.values())), "resultado": _arred(tot_rec - tot_desp),
                   "linhas": len(linhas), "sem_receita": sum(1 for p in por_projeto if p["receita"] == 0)},
    }


def _linha_ref(r: sqlite3.Row, c) -> dict:
    return {"total": _arred(sum(r[m] for m in MESES))}


def _uma(c: sqlite3.Connection, rid: int) -> dict:
    r = c.execute(_SQL + " AND r.id=?", (config.CICLO_PLANO, rid)).fetchone()
    ref = c.execute("SELECT * FROM receitas WHERE id=?", (r["base_id"],)).fetchone() if r["base_id"] else None
    return _linha(r, ref)


def _do_usuario(c: sqlite3.Connection, u: dict, rid: int) -> sqlite3.Row:
    r = c.execute("SELECT * FROM receitas WHERE id=? AND ciclo=?", (rid, config.CICLO_PLANO)).fetchone()
    if not r:
        raise HTTPException(404, "Receita não encontrada.")
    exige_acesso(c, u, r["orcamento"])
    return r


@router.post("", status_code=201)
def criar(d: ReceitaIn, u: dict = Depends(usuario_liberado)):
    with tx() as c:
        exige_acesso(c, u, d.orcamento)
        cur = c.execute(
            f"INSERT INTO receitas (ciclo, orcamento, fonte, descricao, {', '.join(MESES)}, obs, atualizado_por) "
            f"VALUES (?,?,?,?,{', '.join('?' for _ in MESES)},?,?)",
            (config.CICLO_PLANO, d.orcamento, d.fonte.strip(), d.descricao.strip(), *d.meses, d.obs.strip(), u["login"]))
        audit(c, u["login"], "criou receita", d.orcamento, None, f"{d.fonte} / {_arred(sum(d.meses))}")
        return _uma(c, cur.lastrowid)


@router.put("/{rid}")
def editar(rid: int, d: ReceitaPatch, u: dict = Depends(usuario_liberado)):
    with tx() as c:
        atual = _do_usuario(c, u, rid)
        novo = d.model_dump(exclude_none=True)
        if "orcamento" in novo:
            exige_acesso(c, u, novo["orcamento"])
        sets, vals = [], []
        for k in ("orcamento", "fonte", "descricao", "obs"):
            if k in novo:
                sets.append(f"{k}=?"); vals.append(novo[k].strip())
        if "meses" in novo:
            sets += [f"{m}=?" for m in MESES]; vals += novo["meses"]
        if not sets:
            raise HTTPException(422, "Nada para alterar.")
        antes = _arred(sum(atual[m] for m in MESES))
        c.execute(f"UPDATE receitas SET {', '.join(sets)}, atualizado_por=?, atualizado_em=datetime('now') WHERE id=?",
                  (*vals, u["login"], rid))
        depois = _arred(sum(novo["meses"])) if "meses" in novo else antes
        audit(c, u["login"], "editou receita", atual["orcamento"], None, f"{atual['fonte']}: total {antes} para {depois}")
        return _uma(c, rid)


@router.delete("/{rid}")
def excluir(rid: int, u: dict = Depends(usuario_liberado)):
    with tx() as c:
        atual = _do_usuario(c, u, rid)
        c.execute("DELETE FROM receitas WHERE id=?", (rid,))
        audit(c, u["login"], "excluiu receita", atual["orcamento"], None,
              f"{atual['fonte']} / {_arred(sum(atual[m] for m in MESES))}")
    return {"ok": True}
