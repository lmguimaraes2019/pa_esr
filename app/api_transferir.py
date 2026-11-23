"""Transferência de linhas do plano 2027 de um orçamento para outro, levando a estrutura (Meta/EDT e Ação/Tarefa).

A estrutura não é uma tabela: Meta/EDT e Ação/Tarefa existem enquanto houver linhas com aquele texto. Por isso transferir
a linha cria a estrutura no destino (se faltar) e a faz desaparecer da origem quando a última linha sai."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from . import config
from .api import MESES, _arred, _conn, exige_acesso, permitidos, usuario_liberado
from .db import audit, tx

router = APIRouter(prefix="/api", tags=["transferir"])

FONTES = {"viagens": "plano de viagens", "eventos": "página Eventos", "headcount": "página Headcount"}


class TransferenciaIn(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=200)
    destino: str
    edt: str | None = Field(default=None, max_length=200)          # novo nome da Meta/EDT no destino (vale para todas as linhas)
    tarefa: str | None = Field(default=None, max_length=200)       # novo nome da Ação/Tarefa no destino
    valor: float | None = Field(default=None, gt=0)                # só com uma linha: transfere parte do valor
    simular: bool = True


@router.get("/linhas/destinos")
def destinos(origem: str, u: dict = Depends(usuario_liberado), c: sqlite3.Connection = Depends(_conn)):
    exige_acesso(c, u, origem)
    ids = sorted(permitidos(c, u) - {origem})
    marks = ",".join("?" for _ in ids) or "''"
    return [{"orcamento": r["orcamento"], "descricao": r["descricao"], "gerente": r["gerente"], "n_projeto": r["n_projeto"]}
            for r in c.execute(f"SELECT * FROM projetos WHERE orcamento IN ({marks}) AND tipo<>'receita' AND extinto=0 "
                               f"ORDER BY descricao", ids)]


def _total(r) -> float:
    return _arred(sum(r[m] for m in MESES))


def _soma(c: sqlite3.Connection, orc: str) -> float:
    return _arred(c.execute(f"SELECT COALESCE(SUM({'+'.join(MESES)}),0) FROM linhas WHERE ciclo=? AND orcamento=?",
                            (config.CICLO_PLANO, orc)).fetchone()[0])


def _concluiu(c: sqlite3.Connection, gerente: str) -> bool:
    return bool(c.execute(
        "SELECT 1 FROM user_gerentes ug JOIN users us ON us.id=ug.user_id JOIN conclusoes cn ON cn.login=us.login "
        "WHERE ug.gerente=? AND us.ativo=1 AND COALESCE(us.cargo,'')<>'coordenador' LIMIT 1", (gerente,)).fetchone())


def _planejar(c: sqlite3.Connection, u: dict, d: TransferenciaIn) -> tuple[dict, list]:
    marks = ",".join("?" for _ in d.ids)
    linhas = c.execute(f"SELECT * FROM linhas WHERE ciclo=? AND id IN ({marks}) ORDER BY edt, tarefa, conta_codigo, id",
                       (config.CICLO_PLANO, *d.ids)).fetchall()
    if len(linhas) != len(set(d.ids)):
        raise HTTPException(404, "Linha não encontrada.")
    origens = {r["orcamento"] for r in linhas}
    if len(origens) != 1:
        raise HTTPException(422, "Transfira linhas de um projeto por vez.")
    origem = origens.pop()
    po = exige_acesso(c, u, origem)
    if d.destino == origem:
        raise HTTPException(422, "O destino precisa ser outro projeto.")
    pd = exige_acesso(c, u, d.destino)
    if pd["extinto"]:
        raise HTTPException(409, "O projeto de destino foi extinto. Escolha outro.")
    if pd["tipo"] == "receita":
        raise HTTPException(409, "O projeto de destino é de receita. Escolha um projeto de despesa.")
    if d.destino not in permitidos(c, u):
        raise HTTPException(404, "Projeto de destino não encontrado.")
    travadas = [r for r in linhas if r["fonte"] != "manual"]
    if travadas:
        pag = sorted({FONTES.get(r["fonte"], r["fonte"]) for r in travadas})
        raise HTTPException(409, "Há linhas que vêm de outra página (" + ", ".join(pag) + "). Elas acompanham o item de origem e não podem ser "
                                 "transferidas por aqui. Escolha só linhas lançadas à mão.")
    if d.valor is not None and len(linhas) != 1:
        raise HTTPException(422, "A transferência parcial vale para uma linha por vez.")
    if d.valor is not None and d.valor > _total(linhas[0]) + 0.005:
        raise HTTPException(422, "O valor a transferir é maior que o total da linha.")
    if (d.edt is not None and not d.edt.strip()) or (d.tarefa is not None and not d.tarefa.strip()):
        raise HTTPException(422, "Meta/EDT e Ação/Tarefa não podem ficar vazias.")

    itens = []
    for r in linhas:
        tot = _total(r)
        mover = _arred(d.valor) if d.valor is not None else tot
        fator = 1.0 if mover >= tot else mover / tot
        if fator >= 1.0:
            meses = [r[m] for m in MESES]
        else:
            meses = [round(r[m] * fator, 2) for m in MESES]
            resto = _arred(mover - sum(meses))
            if resto:
                k = max((i for i, v in enumerate(meses) if v), default=len(MESES) - 1)
                meses[k] = _arred(meses[k] + resto)
        edt, tarefa = (d.edt or r["edt"]).strip(), (d.tarefa or r["tarefa"]).strip()
        igual = c.execute("SELECT * FROM linhas WHERE ciclo=? AND orcamento=? AND edt=? AND tarefa=? AND conta_codigo=? AND fonte='manual' LIMIT 1",
                          (config.CICLO_PLANO, d.destino, edt, tarefa, r["conta_codigo"])).fetchone()
        itens.append({"linha": r, "meses": meses, "valor": _arred(sum(meses)), "parcial": fator < 1.0, "edt": edt, "tarefa": tarefa, "igual": igual})

    # estrutura no destino e na origem
    movidos = {i["linha"]["id"] for i in itens if not i["parcial"]}
    metas_dest = {r[0] for r in c.execute("SELECT DISTINCT edt FROM linhas WHERE ciclo=? AND orcamento=?", (config.CICLO_PLANO, d.destino))}
    acoes_dest = {(r[0], r[1]) for r in c.execute("SELECT DISTINCT edt, tarefa FROM linhas WHERE ciclo=? AND orcamento=?", (config.CICLO_PLANO, d.destino))}
    ficam = [r for r in c.execute("SELECT id, edt, tarefa FROM linhas WHERE ciclo=? AND orcamento=?", (config.CICLO_PLANO, origem)) if r["id"] not in movidos]
    metas_ficam, acoes_ficam = {r["edt"] for r in ficam}, {(r["edt"], r["tarefa"]) for r in ficam}
    metas_criar = sorted({i["edt"] for i in itens} - metas_dest)
    acoes_criar = sorted({(i["edt"], i["tarefa"]) for i in itens} - acoes_dest)
    metas_saem = sorted({i["linha"]["edt"] for i in itens} - metas_ficam)
    acoes_saem = sorted({(i["linha"]["edt"], i["linha"]["tarefa"]) for i in itens} - acoes_ficam)
    com_base = [i for i in itens if i["linha"]["base_id"] and not i["parcial"]]

    mover_total = _arred(sum(i["valor"] for i in itens))
    o_antes, d_antes = _soma(c, origem), _soma(c, d.destino)
    avisos = []
    for campo, rotulo in (("gerente", "gestor"), ("diretoria", "diretoria"), ("finalidade", "finalidade")):
        if po[campo] != pd[campo]:
            avisos.append(f"A {rotulo} muda de {po[campo]} para {pd[campo]}: o valor passa a contar no grupo do projeto de destino nos resumos e na página executiva.")
    if com_base:
        avisos.append(f"{len(com_base)} linha(s) tinham base em 2026. A linha de 2026 continua no projeto de origem como 'removida' (pode ser trazida de volta) "
                      "e, no destino, o valor entra como linha nova.")
    if any(i["igual"] for i in itens):
        avisos.append("Já existe no destino uma linha com a mesma ação e conta: os valores serão somados nela.")
    if _concluiu(c, pd["gerente"]):
        avisos.append(f"O gestor do destino ({pd['gerente']}) já marcou o planejamento como concluído. Avise-o da mudança.")
    plano = {
        "origem": {"orcamento": origem, "descricao": po["descricao"], "antes": o_antes, "depois": _arred(o_antes - mover_total)},
        "destino": {"orcamento": d.destino, "descricao": pd["descricao"], "antes": d_antes, "depois": _arred(d_antes + mover_total)},
        "valor": mover_total, "n_linhas": len(itens), "parcial": any(i["parcial"] for i in itens),
        "criar_no_destino": {"metas": metas_criar, "acoes": [{"edt": a, "tarefa": b} for a, b in acoes_criar]},
        "sai_da_origem": {"metas": metas_saem, "acoes": [{"edt": a, "tarefa": b} for a, b in acoes_saem]},
        "linhas": [{"id": i["linha"]["id"], "edt": i["edt"], "tarefa": i["tarefa"], "conta_codigo": i["linha"]["conta_codigo"], "valor": i["valor"], "parcial": i["parcial"],
                    "soma_em_existente": bool(i["igual"])} for i in itens],
        "avisos": avisos,
    }
    return plano, itens


@router.post("/linhas/transferir")
def transferir(d: TransferenciaIn, u: dict = Depends(usuario_liberado)):
    with tx() as c:
        plano, itens = _planejar(c, u, d)
        if d.simular:
            return {**plano, "simulacao": True}
        origem, destino = plano["origem"]["orcamento"], d.destino
        nota = f"Transferida de {origem} por {u['login']}"
        for i in itens:
            r = i["linha"]
            obs = (r["obs"] + " | " if r["obs"] else "") + nota
            if i["parcial"]:
                resto = [_arred(r[m] - v) for m, v in zip(MESES, i["meses"])]
                c.execute(f"UPDATE linhas SET {', '.join(m + '=?' for m in MESES)}, editada=1, atualizado_por=?, atualizado_em=datetime('now') WHERE id=?",
                          (*resto, u["login"], r["id"]))
                if i["igual"]:
                    novo = [_arred(i["igual"][m] + v) for m, v in zip(MESES, i["meses"])]
                    c.execute(f"UPDATE linhas SET {', '.join(m + '=?' for m in MESES)}, editada=1, atualizado_por=?, atualizado_em=datetime('now') WHERE id=?",
                              (*novo, u["login"], i["igual"]["id"]))
                else:
                    c.execute(f"INSERT INTO linhas (ciclo, orcamento, edt, tarefa, conta_codigo, {', '.join(MESES)}, editada, obs, atualizado_por) "
                              f"VALUES (?,?,?,?,?,{', '.join('?' for _ in MESES)},1,?,?)",
                              (config.CICLO_PLANO, destino, i["edt"], i["tarefa"], r["conta_codigo"], *i["meses"], nota, u["login"]))
            elif i["igual"]:
                novo = [_arred(i["igual"][m] + v) for m, v in zip(MESES, i["meses"])]
                c.execute(f"UPDATE linhas SET {', '.join(m + '=?' for m in MESES)}, editada=1, atualizado_por=?, atualizado_em=datetime('now') WHERE id=?",
                          (*novo, u["login"], i["igual"]["id"]))
                c.execute("DELETE FROM linhas WHERE id=?", (r["id"],))
            else:
                c.execute("UPDATE linhas SET orcamento=?, edt=?, tarefa=?, base_id=NULL, editada=1, obs=?, atualizado_por=?, atualizado_em=datetime('now') WHERE id=?",
                          (destino, i["edt"], i["tarefa"], obs, u["login"], r["id"]))
        det = f"{plano['n_linhas']} linha(s), {plano['valor']}"
        audit(c, u["login"], "transferiu linhas para outro projeto", origem, detalhe=f"para {destino}: {det}")
        audit(c, u["login"], "recebeu linhas de outro projeto", destino, detalhe=f"de {origem}: {det}")
    return {**plano, "simulacao": False}
