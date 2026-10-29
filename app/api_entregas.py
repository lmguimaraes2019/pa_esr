"""Entregas previstas de cada projeto em 2027 e a conexão estratégica com o PO e o Contrato de Gestão.

Cada entrega tem descrição, mês previsto, KPI próprio (indicador e meta) e vínculos com resultados-chave do Plano de Operação
e com indicadores do Contrato de Gestão, cadastrados pelo administrador (Administração, Tabelas de referência).
"""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from . import config, estrategia
from .api import _arred, _conn, exige_acesso, permitidos, usuario_liberado
from .db import MESES, audit, tx

router = APIRouter(prefix="/api")
SOMA = "+".join(MESES)


class EntregaIn(BaseModel):
    descricao: str = Field(min_length=3, max_length=1000)
    mes: int = Field(default=0, ge=0, le=12)            # 0 = sem mês definido
    kpi: str = Field(default="", max_length=200)
    meta: str = Field(default="", max_length=200)
    estrategia: list[int] = Field(default_factory=list, max_length=30)


class LoteIn(BaseModel):
    linhas: list[str] = Field(min_length=1, max_length=100)


def _catalogo(c: sqlite3.Connection) -> list[dict]:
    return estrategia.arvore(c)


class VinculoIn(BaseModel):
    ids: list[int] = Field(default_factory=list, max_length=60)


def _entregas(c: sqlite3.Connection, orcamento: str) -> list[dict]:
    vinc: dict[int, list[int]] = {}
    for r in c.execute("SELECT x.entrega_id, x.estrategia_id FROM entrega_estrategia x JOIN entregas e ON e.id=x.entrega_id WHERE e.orcamento=?", (orcamento,)):
        vinc.setdefault(r[0], []).append(r[1])
    return [{"id": r["id"], "descricao": r["descricao"], "mes": r["mes"], "kpi": r["kpi"], "meta": r["meta"], "estrategia": sorted(vinc.get(r["id"], [])),
             "atualizado_por": r["atualizado_por"]}
            for r in c.execute("SELECT * FROM entregas WHERE orcamento=? ORDER BY ordem, id", (orcamento,))]


def _grava_vinculos(c: sqlite3.Connection, eid: int, ids: list[int]) -> None:
    validos = {r[0] for r in c.execute("SELECT id FROM estrategia")}
    c.execute("DELETE FROM entrega_estrategia WHERE entrega_id=?", (eid,))
    c.executemany("INSERT INTO entrega_estrategia (entrega_id, estrategia_id) VALUES (?,?)", [(eid, i) for i in sorted(set(ids) & validos)])


@router.get("/projetos/{orcamento}/entregas")
def listar(orcamento: str, u: dict = Depends(usuario_liberado), c: sqlite3.Connection = Depends(_conn)):
    exige_acesso(c, u, orcamento)
    vinc = sorted(r[0] for r in c.execute("SELECT estrategia_id FROM projeto_estrategia WHERE orcamento=?", (orcamento,)))
    return {"entregas": _entregas(c, orcamento), "catalogo": _catalogo(c), "vinculos": vinc}


@router.put("/projetos/{orcamento}/estrategia")
def vincular(orcamento: str, d: VinculoIn, u: dict = Depends(usuario_liberado)):
    """Define a que diretriz, RE, RO do PO e indicador do CG o orçamento do projeto está ligado."""
    with tx() as c:
        exige_acesso(c, u, orcamento)
        validos = {r[0] for r in c.execute("SELECT id FROM estrategia")}
        ids = sorted(set(d.ids) & validos)
        c.execute("DELETE FROM projeto_estrategia WHERE orcamento=?", (orcamento,))
        c.executemany("INSERT INTO projeto_estrategia (orcamento, estrategia_id) VALUES (?,?)", [(orcamento, i) for i in ids])
        audit(c, u["login"], "vinculou projeto à estratégia", orcamento, detalhe=f"{len(ids)} item(ns)")
    return {"ok": True, "vinculos": ids}


@router.post("/projetos/{orcamento}/entregas", status_code=201)
def criar(orcamento: str, d: EntregaIn, u: dict = Depends(usuario_liberado)):
    with tx() as c:
        exige_acesso(c, u, orcamento)
        ordem = c.execute("SELECT COALESCE(MAX(ordem),0)+1 FROM entregas WHERE orcamento=?", (orcamento,)).fetchone()[0]
        cur = c.execute("INSERT INTO entregas (orcamento, descricao, mes, kpi, meta, ordem, criado_por, atualizado_por) VALUES (?,?,?,?,?,?,?,?)",
                        (orcamento, d.descricao.strip(), d.mes, d.kpi.strip(), d.meta.strip(), ordem, u["login"], u["login"]))
        _grava_vinculos(c, cur.lastrowid, d.estrategia)
        audit(c, u["login"], "incluiu entrega", orcamento, detalhe=d.descricao.strip()[:200])
        return {"id": cur.lastrowid}


@router.post("/projetos/{orcamento}/entregas/lote", status_code=201)
def criar_lote(orcamento: str, d: LoteIn, u: dict = Depends(usuario_liberado)):
    """Uma entrega por linha de texto; os detalhes (prazo, KPI e vínculos) o gestor completa depois."""
    linhas = [l.strip(" \t-•*") for l in d.linhas if len(l.strip(" \t-•*")) >= 3]
    if not linhas:
        raise HTTPException(422, "Escreva ao menos uma entrega com 3 caracteres ou mais.")
    with tx() as c:
        exige_acesso(c, u, orcamento)
        ordem = c.execute("SELECT COALESCE(MAX(ordem),0) FROM entregas WHERE orcamento=?", (orcamento,)).fetchone()[0]
        for i, l in enumerate(linhas, start=1):
            c.execute("INSERT INTO entregas (orcamento, descricao, ordem, criado_por, atualizado_por) VALUES (?,?,?,?,?)", (orcamento, l[:1000], ordem + i, u["login"], u["login"]))
        audit(c, u["login"], "incluiu entregas em lote", orcamento, detalhe=f"{len(linhas)} entrega(s)")
    return {"incluidas": len(linhas)}


def _da_entrega(c: sqlite3.Connection, u: dict, eid: int) -> sqlite3.Row:
    r = c.execute("SELECT * FROM entregas WHERE id=?", (eid,)).fetchone()
    if not r:
        raise HTTPException(404, "Entrega não encontrada.")
    exige_acesso(c, u, r["orcamento"])
    return r


@router.put("/entregas/{eid}")
def editar(eid: int, d: EntregaIn, u: dict = Depends(usuario_liberado)):
    with tx() as c:
        r = _da_entrega(c, u, eid)
        c.execute("UPDATE entregas SET descricao=?, mes=?, kpi=?, meta=?, atualizado_por=?, atualizado_em=datetime('now') WHERE id=?",
                  (d.descricao.strip(), d.mes, d.kpi.strip(), d.meta.strip(), u["login"], eid))
        _grava_vinculos(c, eid, d.estrategia)
        audit(c, u["login"], "editou entrega", r["orcamento"], detalhe=f"id {eid}")
    return {"ok": True}


@router.delete("/entregas/{eid}")
def excluir(eid: int, u: dict = Depends(usuario_liberado)):
    with tx() as c:
        r = _da_entrega(c, u, eid)
        c.execute("DELETE FROM entrega_estrategia WHERE entrega_id=?", (eid,))
        c.execute("DELETE FROM entregas WHERE id=?", (eid,))
        audit(c, u["login"], "excluiu entrega", r["orcamento"], detalhe=r["descricao"][:200])
    return {"ok": True}


@router.get("/estrategia/cobertura")
def cobertura(u: dict = Depends(usuario_liberado), c: sqlite3.Connection = Depends(_conn)):
    """Para cada diretriz, RE, RO e indicador do CG: quantos projetos e entregas o atendem e quanto do plano 2027 está ligado a ele.
    Vincular um projeto a um RO cobre também o RE, a diretriz e o indicador do CG acima dele.
    O valor é o plano dos projetos vinculados (um projeto pode atender a mais de um item, por isso os valores não se somam)."""
    ids = sorted(permitidos(c, u))
    marks = ",".join("?" for _ in ids) or "''"
    plano = {r["orcamento"]: _arred(r["t"]) for r in c.execute(
        f"SELECT orcamento, SUM({SOMA}) t FROM linhas WHERE ciclo=? AND orcamento IN ({marks}) AND orcamento IN (SELECT orcamento FROM projetos WHERE tipo='despesa') GROUP BY orcamento",
        (config.CICLO_PLANO, *ids))}
    nomes = {r["orcamento"]: r["descricao"] for r in c.execute(f"SELECT orcamento, descricao FROM projetos WHERE orcamento IN ({marks})", ids)}
    cat = _catalogo(c)
    direto: dict[str, set[int]] = {o: set() for o in ids}
    for r in c.execute(f"SELECT orcamento, estrategia_id FROM projeto_estrategia WHERE orcamento IN ({marks})", ids):
        direto[r[0]].add(r[1])
    por_item: dict[int, dict] = {i["id"]: {"entregas": set(), "projetos": set()} for i in cat}
    vinc_entrega: dict[int, set[int]] = {}
    for r in c.execute(f"""SELECT x.estrategia_id, e.id AS eid, e.orcamento FROM entrega_estrategia x JOIN entregas e ON e.id=x.entrega_id
                           WHERE e.orcamento IN ({marks})""", ids):
        direto[r["orcamento"]].add(r["estrategia_id"])
        vinc_entrega.setdefault(r["eid"], set()).add(r["estrategia_id"])
        for i in estrategia.fecho(cat, {r["estrategia_id"]}):
            por_item[i]["entregas"].add(r["eid"])
    ligados = set()
    for o, ds in direto.items():
        fe = estrategia.fecho(cat, ds)
        if fe:
            ligados.add(o)
        for i in fe:
            por_item[i]["projetos"].add(o)
    itens = []
    for e in cat:
        d = por_item[e["id"]]
        itens.append({**{k: e[k] for k in ("id", "tipo", "codigo", "descricao", "meta", "objetivo", "indicador", "conclusao", "responsavel", "fomento", "lider", "pais")},
                      "entregas": len(d["entregas"]), "projetos": len(d["projetos"]),
                      "plano_projetos": _arred(sum(plano.get(o, 0.0) for o in d["projetos"])),
                      "lista_projetos": [{"orcamento": o, "projeto": nomes.get(o, ""), "plano": plano.get(o, 0.0)} for o in sorted(d["projetos"])]})
    sem_entregas = {r[0] for r in c.execute(f"SELECT DISTINCT orcamento FROM entregas WHERE orcamento IN ({marks})", ids)}
    sem_vinculo = [{"orcamento": o, "projeto": nomes.get(o, ""), "plano": v, "tem_entregas": o in sem_entregas}
                   for o, v in sorted(plano.items()) if v > 0 and o not in ligados]
    return {"itens": itens, "sem_vinculo": sem_vinculo, "catalogo_vazio": not itens, "plano_total": _arred(sum(plano.values())),
            "plano_sem_vinculo": _arred(sum(x["plano"] for x in sem_vinculo))}
