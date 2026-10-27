"""Leva Eventos e Headcount para o orçamento 2027 como linhas bloqueadas (fonte 'eventos' e 'headcount').

As linhas são recriadas por inteiro a cada alteração, a partir dos registros das duas páginas. O gerente altera o evento ou
a posição na página própria, e o orçamento do projeto acompanha. Itens sem a tarefa do orçamento escolhida ficam de fora
e aparecem como pendência.
"""
from __future__ import annotations

import json
import re
import sqlite3

from . import config, equipamentos, pessoal, viagens as vg
from .db import MESES

FONTES_SYNC = ("eventos", "headcount")

# conta onde entra a inscrição em eventos (Serviços PJ, "Treinamento / Curso / Workshop")
CONTA_INSCRICAO = "51040104"

# componente do custo de pessoal -> conta contábil
CONTAS_PESSOAL = {
    "salario": "51010101", "inss": "51010401", "fgts": "51010402", "pis": "51010403",
    "vr": "51010503", "plano_saude": "51010502", "seguro_vida": "51010506", "vt": "51010507",
    "internet": "51010518", "provisao_ferias": "51020101", "provisao_13": "51020201",
}

PADRAO_TAREFA = {"eventos": r"EVENT|CAPACIT|TREINAM|CONGRESS|PARTICIP", "headcount": r"PESSOA|RH|CONTRAT|FOLHA|QUADRO|HEADCOUNT|SALARI"}


def sugerir_tarefa(tarefas: list[dict], tipo: str) -> dict | None:
    """Tarefa do projeto cujo nome combina com o assunto, se for uma só."""
    achadas = [t for t in tarefas if re.search(PADRAO_TAREFA[tipo], f"{t['edt']} {t['tarefa']}".upper())]
    return achadas[0] if len(achadas) == 1 else None


def _soma(dest: dict, chave: tuple, mes: int, valor: float) -> None:
    if valor:
        linha = dest.setdefault(chave, [0.0] * 12)
        linha[mes - 1] = round(linha[mes - 1] + valor, 2)


def linhas_de_eventos(c: sqlite3.Connection, orcamento: str) -> dict:
    from .api_eventos import _dolar
    tarifas, bv, dolar = vg.tarifas_map(c), vg.bagagem_vezes(c), _dolar(c)
    out: dict[tuple, list[float]] = {}
    for r in c.execute("SELECT * FROM eventos WHERE orcamento=?", (orcamento,)):
        if not (r["edt"] and r["tarefa"]):
            continue
        custo = vg.calcular(r["tipo"], tarifas.get((r["tipo"], r["origem"], r["destino"])), r["n_pessoas"], r["dias"], r["pernoites"], bv)
        for comp, conta in vg.CONTAS[r["tipo"]].items():
            _soma(out, (r["edt"], r["tarefa"], conta, "eventos"), r["mes"], custo[comp])
        insc = (r["inscricao"] or 0.0) * (dolar if r["moeda"] == "USD" else 1.0) * r["n_pessoas"]
        _soma(out, (r["edt"], r["tarefa"], CONTA_INSCRICAO, "eventos"), r["mes"], round(insc, 2))
    return out


def linhas_de_headcount(c: sqlite3.Connection, orcamento: str) -> dict:
    from .api_headcount import _reajuste
    par, reaj = pessoal.parametros(c), _reajuste(c)
    out: dict[tuple, list[float]] = {}
    for r in c.execute("SELECT * FROM headcount WHERE orcamento=?", (orcamento,)):
        f = pessoal.faixa(r["trajetoria"], r["nivel"], r["grupo"])
        if not (f and r["edt"] and r["tarefa"]):
            continue
        sal = round(pessoal.salario_na_faixa(f, r["posicao"]) * (1 + reaj / 100), 2)
        cm = pessoal.custo_mensal(sal, par)
        for comp, conta in CONTAS_PESSOAL.items():
            for mes in range(r["mes_inicio"], 13):
                _soma(out, (r["edt"], r["tarefa"], conta, "headcount"), mes, round(cm[comp] * r["quantidade"], 2))
        hw = equipamentos.custo(r["computador"], r["monitor"], r["periferico"])["total"]      # custo pontual, no mês de início
        _soma(out, (r["edt"], r["tarefa"], equipamentos.CONTA_HARDWARE, "headcount"), r["mes_inicio"], round(hw * r["quantidade"], 2))
    return out


def sincronizar(c: sqlite3.Connection, orcamento: str, usuario: str) -> None:
    """Recria no plano 2027 as linhas de eventos e de headcount do projeto."""
    if not orcamento:
        return
    c.execute("DELETE FROM linhas WHERE ciclo=? AND orcamento=? AND fonte IN ('eventos','headcount')", (config.CICLO_PLANO, orcamento))
    novas = {**linhas_de_eventos(c, orcamento), **linhas_de_headcount(c, orcamento)}
    existe = {r[0] for r in c.execute("SELECT codigo FROM contas")}
    for (edt, tarefa, conta, fonte), meses in sorted(novas.items()):
        if conta not in existe or sum(meses) <= 0:
            continue
        c.execute(f"INSERT INTO linhas (ciclo, orcamento, edt, tarefa, conta_codigo, {', '.join(MESES)}, fonte, atualizado_por) "
                  f"VALUES (?,?,?,?,?,{','.join('?' for _ in MESES)},?,?)",
                  (config.CICLO_PLANO, orcamento, edt, tarefa, conta, *meses, fonte, usuario))


def sincronizar_todos(c: sqlite3.Connection, usuario: str = "sistema") -> int:
    ids = {r[0] for r in c.execute("SELECT orcamento FROM eventos UNION SELECT orcamento FROM headcount")}
    ids |= {r[0] for r in c.execute("SELECT DISTINCT orcamento FROM linhas WHERE fonte IN ('eventos','headcount')")}
    for o in sorted(ids):
        sincronizar(c, o, usuario)
    return len(ids)
