"""Rotas do planejamento de viagens e da ligação do plano com o orçamento 2027."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from . import config, sync, viagens as vg
from .api import _arred, _conn, exige_admin, permitidos, usuario_liberado
from .db import MESES, NOMES_MESES, audit, tx

router = APIRouter(prefix="/api/viagens")
SOMA = "+".join(MESES)


class ViagemIn(BaseModel):
    tipo: str = Field(pattern="^(nac|int)$")
    mes: int = Field(ge=1, le=12)
    origem: str = Field(min_length=1, max_length=80)
    destino: str = Field(min_length=1, max_length=80)
    n_viagens: int = Field(ge=1, le=500)
    dias: int = Field(ge=1, le=60)
    pernoites: int | None = Field(default=None, ge=0, le=60)
    objetivo: str = Field(default="", max_length=300)
    area: str = Field(default="", max_length=40)
    orcamento: str | None = None
    edt: str | None = None
    tarefa: str | None = None


class TarifaIn(BaseModel):
    passagem: float = Field(ge=0, le=1e7)
    hospedagem: float = Field(ge=0, le=1e7)
    bagagem: float = Field(ge=0, le=1e7)
    aux_transporte: float = Field(ge=0, le=1e7)
    ajuda_custo: float = Field(ge=0, le=1e7)
    seguro: float = Field(ge=0, le=1e7)


class ReajusteIn(BaseModel):
    percentual: float = Field(ge=-50, le=100)
    tipo: str | None = Field(default=None, pattern="^(nac|int)$")
    simular: bool = True


class AplicarIn(BaseModel):
    simular: bool = True


def _tarefas_por_projeto(c: sqlite3.Connection, ids: set[str]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {o: [] for o in ids}
    for r in c.execute("SELECT DISTINCT orcamento, edt, tarefa FROM linhas ORDER BY edt, tarefa"):
        if r["orcamento"] in out:
            out[r["orcamento"]].append({"edt": r["edt"], "tarefa": r["tarefa"]})
    return out


def _json(v: sqlite3.Row, tar, bvezes: float, base: sqlite3.Row | None, nomes: dict[str, str]) -> dict:
    t = tar.get((v["tipo"], v["origem"], v["destino"]))
    custo = vg.calcular(v["tipo"], t, v["n_viagens"], v["dias"], v["pernoites"], bvezes)
    ref = None
    if base is not None:
        bt = tar.get((base["tipo"], base["origem"], base["destino"]))
        ref = vg.calcular(base["tipo"], bt, base["n_viagens"], base["dias"], base["pernoites"], bvezes)["total"]
    return {"id": v["id"], "tipo": v["tipo"], "mes": v["mes"], "origem": v["origem"], "destino": v["destino"],
            "n_viagens": v["n_viagens"], "dias": v["dias"], "pernoites": v["pernoites"], "objetivo": v["objetivo"],
            "area": v["area"], "orcamento": v["orcamento"], "projeto": nomes.get(v["orcamento"] or "", ""),
            "edt": v["edt"], "tarefa": v["tarefa"], "tem_tarifa": t is not None, "custo": custo,
            "ref_2026": ref, "atualizado_por": v["atualizado_por"]}


def _visiveis(c: sqlite3.Connection, u: dict, ciclo: int):
    ids = permitidos(c, u)
    rows = c.execute("SELECT * FROM viagens WHERE ciclo=? ORDER BY mes, id", (ciclo,)).fetchall()
    return [v for v in rows if (v["orcamento"] in ids) or (u["perfil"] == "admin" and not v["orcamento"])], ids


@router.get("")
def listar(u: dict = Depends(usuario_liberado), c: sqlite3.Connection = Depends(_conn)):
    tar = vg.tarifas_map(c)
    bv = vg.bagagem_vezes(c)
    nomes = {r["orcamento"]: r["descricao"] for r in c.execute("SELECT orcamento, descricao FROM projetos")}
    rows, ids = _visiveis(c, u, config.CICLO_PLANO)
    bases = {r["id"]: r for r in c.execute("SELECT * FROM viagens WHERE ciclo=?", (config.CICLO_BASE,))}
    itens = [_json(v, tar, bv, bases.get(v["base_id"]), nomes) for v in rows]

    # visão por projeto: plano de viagens x orçamento aprovado x executado x orçamento 2027 atual
    contas = ",".join("?" for _ in vg.CONTAS_VIAGEM)
    cv = sorted(vg.CONTAS_VIAGEM)

    def soma(sql: str, *args) -> dict[str, float]:
        return {r[0]: float(r[1] or 0) for r in c.execute(sql, args)}
    aprovado = soma(f"SELECT orcamento, SUM({SOMA}) FROM linhas WHERE ciclo=? AND conta_codigo IN ({contas}) GROUP BY orcamento",
                    config.CICLO_BASE, *cv)
    atual = soma(f"SELECT orcamento, SUM({SOMA}) FROM linhas WHERE ciclo=? AND conta_codigo IN ({contas}) GROUP BY orcamento",
                 config.CICLO_PLANO, *cv)
    exec_ = soma(f"SELECT orcamento, SUM(realizado+empenhado) FROM execucao WHERE conta_codigo IN ({contas}) GROUP BY orcamento", *cv)
    plano_prj: dict[str, float] = {}
    ref_prj: dict[str, float] = {}
    for i in itens:
        k = i["orcamento"] or ""
        plano_prj[k] = plano_prj.get(k, 0) + i["custo"]["total"]
        ref_prj[k] = ref_prj.get(k, 0) + (i["ref_2026"] or 0)
    projetos = []
    for o in sorted(ids | ({""} if u["perfil"] == "admin" else set())):
        if not (plano_prj.get(o) or aprovado.get(o) or atual.get(o) or exec_.get(o) or ref_prj.get(o)):
            continue
        projetos.append({"orcamento": o, "projeto": nomes.get(o, "Sem projeto definido"),
                         "aprovado_2026": _arred(aprovado.get(o, 0)), "executado_2026": _arred(exec_.get(o, 0)),
                         "planilha_2026": _arred(ref_prj.get(o, 0)), "plano_2027": _arred(plano_prj.get(o, 0)),
                         "orcamento_2027": _arred(atual.get(o, 0)),
                         "conectado": abs(plano_prj.get(o, 0) - atual.get(o, 0)) < 0.01})
    mensal = [0.0] * 12
    mensal_ref = [0.0] * 12
    for i in itens:
        mensal[i["mes"] - 1] += i["custo"]["total"]
        mensal_ref[i["mes"] - 1] += i["ref_2026"] or 0
    ids_tarefas = _tarefas_por_projeto(c, ids)
    pend = sum(1 for i in itens if not i["orcamento"] or not i["edt"] or not i["tem_tarifa"])
    return {
        "viagens": itens, "projetos": projetos,
        "mensal": [{"mes": NOMES_MESES[i], "plano": _arred(mensal[i]), "ref": _arred(mensal_ref[i])} for i in range(12)],
        "totais": {"plano": _arred(sum(mensal)), "ref": _arred(sum(mensal_ref)),
                   "aprovado": _arred(sum(aprovado.get(o, 0) for o in ids)),
                   "executado": _arred(sum(exec_.get(o, 0) for o in ids)),
                   "orcamento": _arred(sum(atual.get(o, 0) for o in ids)),
                   "viagens": sum(i["n_viagens"] for i in itens), "pendentes": pend},
        "bagagem_vezes": bv,
        "opcoes": {
            "tarifas": [{"tipo": k[0], "origem": k[1], "destino": k[2]} for k in sorted(tar)],
            "projetos": [{"orcamento": o, "nome": nomes.get(o, o), "tarefas": ids_tarefas[o]} for o in sorted(ids)],
        },
    }


def _validar(c: sqlite3.Connection, u: dict, d: ViagemIn) -> None:
    if not c.execute("SELECT 1 FROM viagem_tarifas WHERE tipo=? AND origem=? AND destino=?", (d.tipo, d.origem, d.destino)).fetchone():
        raise HTTPException(422, "Não há tarifa cadastrada para esse trecho. O administrador pode incluí-la em Tarifas.")
    if d.orcamento:
        if d.orcamento not in permitidos(c, u):
            raise HTTPException(404, "Projeto não encontrado.")
        if (d.edt or d.tarefa) and not c.execute("SELECT 1 FROM linhas WHERE orcamento=? AND edt=? AND tarefa=? LIMIT 1",
                                                 (d.orcamento, d.edt, d.tarefa)).fetchone():
            raise HTTPException(422, "A tarefa escolhida não existe nesse projeto.")
    elif d.edt or d.tarefa:
        raise HTTPException(422, "Escolha o projeto antes da tarefa.")
    if u["perfil"] != "admin" and not d.orcamento:
        raise HTTPException(422, "Escolha o projeto que vai pagar a viagem.")


def _grava(c: sqlite3.Connection, d: ViagemIn) -> tuple:
    return (d.tipo, d.mes, d.origem, d.destino, d.n_viagens, d.dias, d.pernoites, d.objetivo.strip(), d.area.strip(),
            d.orcamento or None, (d.edt or None) if d.orcamento else None, (d.tarefa or None) if d.orcamento else None)


def _viagem_do_usuario(c: sqlite3.Connection, u: dict, vid: int) -> sqlite3.Row:
    v = c.execute("SELECT * FROM viagens WHERE id=? AND ciclo=?", (vid, config.CICLO_PLANO)).fetchone()
    if not v or not ((v["orcamento"] in permitidos(c, u)) or (u["perfil"] == "admin" and not v["orcamento"])):
        raise HTTPException(404, "Viagem não encontrada.")
    return v


@router.post("", status_code=201)
def criar(d: ViagemIn, u: dict = Depends(usuario_liberado)):
    with tx() as c:
        _validar(c, u, d)
        cur = c.execute("INSERT INTO viagens (ciclo, tipo, mes, origem, destino, n_viagens, dias, pernoites, objetivo, area,"
                        " orcamento, edt, tarefa, atualizado_por) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (config.CICLO_PLANO, *_grava(c, d), u["login"]))
        audit(c, u["login"], "incluiu viagem", d.orcamento, detalhe=f"{d.origem} para {d.destino}, mês {d.mes}")
    return {"id": cur.lastrowid}


@router.put("/{vid}")
def editar(vid: int, d: ViagemIn, u: dict = Depends(usuario_liberado)):
    with tx() as c:
        v = _viagem_do_usuario(c, u, vid)
        _validar(c, u, d)
        c.execute("UPDATE viagens SET tipo=?, mes=?, origem=?, destino=?, n_viagens=?, dias=?, pernoites=?, objetivo=?, area=?,"
                  " orcamento=?, edt=?, tarefa=?, atualizado_por=?, atualizado_em=datetime('now') WHERE id=?",
                  (*_grava(c, d), u["login"], vid))
        audit(c, u["login"], "editou viagem", d.orcamento or v["orcamento"], detalhe=f"id {vid}: {d.origem} para {d.destino}")
    return {"ok": True}


@router.delete("/{vid}")
def excluir(vid: int, u: dict = Depends(usuario_liberado)):
    with tx() as c:
        v = _viagem_do_usuario(c, u, vid)
        c.execute("DELETE FROM viagens WHERE id=?", (vid,))
        audit(c, u["login"], "excluiu viagem", v["orcamento"], detalhe=f"id {vid}: {v['origem']} para {v['destino']}")
    return {"ok": True}


# ---------------------------------------------------------------- tarifas (administrador)

@router.get("/tarifas")
def tarifas(_: dict = Depends(usuario_liberado), c: sqlite3.Connection = Depends(_conn)):
    return [dict(r) for r in c.execute("SELECT * FROM viagem_tarifas ORDER BY tipo, origem, destino")]


@router.put("/tarifas/{tid}")
def gravar_tarifa(tid: int, d: TarifaIn, u: dict = Depends(exige_admin)):
    with tx() as c:
        if not c.execute("SELECT 1 FROM viagem_tarifas WHERE id=?", (tid,)).fetchone():
            raise HTTPException(404, "Tarifa não encontrada.")
        c.execute("UPDATE viagem_tarifas SET passagem=?, hospedagem=?, bagagem=?, aux_transporte=?, ajuda_custo=?, seguro=? WHERE id=?",
                  (*[round(getattr(d, k), 2) for k in vg.CAMPOS_TARIFA], tid))
        audit(c, u["login"], "alterou tarifa", detalhe=f"id {tid}: {d.model_dump()}")
        sync.sincronizar_todos(c, u["login"])
    return {"ok": True}


@router.post("/tarifas/reajuste")
def reajustar(d: ReajusteIn, u: dict = Depends(exige_admin)):
    """Aplica um percentual sobre as tarifas de 2026 (referência), substituindo os valores de 2027."""
    f = 1 + d.percentual / 100
    with tx() as c:
        filtro, args = ("WHERE tipo=?", (d.tipo,)) if d.tipo else ("", ())
        n = c.execute(f"SELECT COUNT(*) FROM viagem_tarifas {filtro}", args).fetchone()[0]
        if not d.simular:
            sets = ", ".join(f"{k}=ROUND(ref_{k}*?,2)" for k in vg.CAMPOS_TARIFA)
            c.execute(f"UPDATE viagem_tarifas SET {sets} {filtro}", (*[f] * len(vg.CAMPOS_TARIFA), *args))
            audit(c, u["login"], "reajustou tarifas de viagens", detalhe=f"{d.percentual}% sobre 2026 ({d.tipo or 'todas'})")
            sync.sincronizar_todos(c, u["login"])
    return {"tarifas_afetadas": n, "simulacao": d.simular}


# ---------------------------------------------------------------- ligação com o orçamento

@router.post("/aplicar")
def aplicar(d: AplicarIn, u: dict = Depends(exige_admin)):
    with tx() as c:
        return vg.aplicar_ao_orcamento(c, u["login"], d.simular)
