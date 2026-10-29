"""Relatório do planejamento anual para o Diretor Executivo (Word, no modelo da RNP).

Parte 1: visão geral (síntese, evolução 2026 para 2027, receitas, headcount, viagens, eventos, conexão estratégica, acompanhamento).
Parte 2: um capítulo por projeto, com todo o detalhamento e a relação estratégica."""
from __future__ import annotations

import io
import logging
import re
import sqlite3
from datetime import datetime

from . import api, api_entregas, api_eventos, api_headcount, api_planejamento, api_receitas, api_viagens, config, estrategia
from .db import MESES, NOMES_MESES
from .relatorio_docx import AZUL, CIANO, CINZA, LARANJA, NAVY, ROXO, VERDE, Doc, montar

ABREV = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
TIPOS = {"diretriz": "Diretriz", "re": "RE", "po": "RO", "cg": "CG"}
NOME_TIPO = {"diretriz": "Diretriz", "re": "Resultado Estratégico (RE)", "po": "Resultado Operacional (RO)", "cg": "Indicador do Contrato de Gestão"}
STATUS = {"mantida": "Mantida", "ajustada": "Ajustada", "nova": "Nova", "viagens": "Plano"}


# ---------------------------------------------------------------- formatação

def n0(v: float) -> str:
    return f"{v:,.0f}".replace(",", ".")


def rs(v: float) -> str:
    return ("-" if v < -0.5 else "") + "R$ " + n0(abs(v))


def mi(v: float) -> str:
    a, neg = abs(v), "-" if v < -0.5 else ""
    if a >= 1e6:
        return neg + "R$ " + f"{a / 1e6:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".") + " mi"
    if a >= 1e3:
        return neg + "R$ " + n0(a / 1e3) + " mil"
    return rs(v)


def pc(v: float, casas: int = 1) -> str:
    return f"{v:.{casas}f}".replace(".", ",") + "%"


def sinal(v: float) -> str:
    return ("+" if v > 0.5 else "") + n0(v)


def var_pc(novo: float, base: float) -> str:
    if not base:
        return "novo" if novo else "-"
    d = (novo - base) / base * 100
    return ("+" if d > 0.05 else "") + pc(d)


def rotulo(it: dict) -> str:
    cod = it["codigo"]
    return cod if not re.match(r"\d", cod) else f"{TIPOS[it['tipo']]} {cod}"


def compara(novo: float, base: float) -> str:
    """'3,2% acima do', '1,0% abaixo do' ou 'igual ao'."""
    if not base:
        return "sem comparação com o"
    d = (novo - base) / base * 100
    return "igual ao" if abs(d) < 0.05 else f"{pc(abs(d))} {'acima' if d > 0 else 'abaixo'} do"


def corta(t: str, n: int) -> str:
    t = (t or "").strip()
    return t if len(t) <= n else t[:n - 1].rstrip() + "…"


def data_br(iso: str | None) -> str:
    try:
        return datetime.fromisoformat(iso[:19]).strftime("%d/%m/%Y")
    except Exception:
        return iso or ""


# ---------------------------------------------------------------- gráficos

def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)
    plt.rcParams.update({"font.family": ["Barlow", "DejaVu Sans"], "font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
                         "axes.edgecolor": "#BFBFBF", "axes.labelcolor": "#404040", "xtick.color": "#404040", "ytick.color": "#404040",
                         "axes.grid": True, "grid.color": "#E6E6E6", "grid.linewidth": 0.6, "axes.axisbelow": True})
    return plt


def _png(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=190, bbox_inches="tight", facecolor="white")
    import matplotlib.pyplot as plt
    plt.close(fig)
    return buf.getvalue()


def _fmt(x, _=None):
    return (f"{x:,.1f}" if abs(x) < 100 else f"{x:,.0f}").replace(",", "X").replace(".", ",").replace("X", ".")


def grafico_grupos(cats: list[str], series: list[tuple[str, list[float], str]], horizontal: bool = True) -> tuple[bytes, float]:
    """Barras agrupadas (valores em R$ milhões). Devolve o PNG e a proporção altura/largura."""
    plt = _plt()
    n, k = len(cats), len(series)
    pico = max((max(v, default=0) for _, v, _ in series), default=0)
    escala, unidade = (1e3, "R$ mil") if pico < 1e6 else (1e6, "R$ milhões")
    series = [(nome, [x / escala for x in vals], cor) for nome, vals, cor in series]
    larg = 0.8 / k
    if horizontal:
        fig, ax = plt.subplots(figsize=(7.0, max(2.2, 0.42 * n * k + 0.9)))
        for j, (nome, vals, cor) in enumerate(series):
            ys = [i + (j - (k - 1) / 2) * larg for i in range(n)]
            ax.barh(ys, vals, height=larg * 0.92, color='#' + cor, label=nome)
        ax.set_yticks(range(n))
        ax.set_yticklabels([corta(c, 38) for c in cats])
        ax.invert_yaxis()
        ax.xaxis.set_major_formatter(_fmt)
        ax.set_xlabel(unidade)
        ax.grid(axis="y", visible=False)
    else:
        fig, ax = plt.subplots(figsize=(7.0, 3.0))
        for j, (nome, vals, cor) in enumerate(series):
            xs = [i + (j - (k - 1) / 2) * larg for i in range(n)]
            ax.bar(xs, vals, width=larg * 0.92, color='#' + cor, label=nome)
        ax.set_xticks(range(n))
        ax.set_xticklabels(cats)
        ax.yaxis.set_major_formatter(_fmt)
        ax.set_ylabel(unidade)
        ax.grid(axis="x", visible=False)
    if k > 1:
        ax.legend(frameon=False, ncol=k, loc="lower center", bbox_to_anchor=(0.5, 1.0))
    png = _png(fig)
    from PIL import Image
    w, h = Image.open(io.BytesIO(png)).size
    return png, h / w


# ---------------------------------------------------------------- coleta

def coletar(c: sqlite3.Connection, u: dict) -> dict:
    """Reúne, com as mesmas funções que alimentam as telas, tudo o que o relatório conta."""
    projetos = api.projetos(u, c)
    ids = [p["orcamento"] for p in projetos]
    d = {
        "resumo": api.resumo(u, c), "projetos": projetos, "receitas": api_receitas.listar(u, c), "viagens": api_viagens.listar(u, c),
        "eventos": api_eventos.listar(u, c), "headcount": api_headcount.listar(u, c), "cobertura": api_entregas.cobertura(u, c),
        "gerencias": api_planejamento._por_gerencia(c), "situacao": api_planejamento.resumir(c, ids),
        "premissas": [dict(r) for r in c.execute("SELECT chave, valor, descricao FROM premissas ORDER BY chave")],
        "catalogo": estrategia.arvore(c), "detalhe": {}, "entregas": {}, "vinculos": {},
        "total_projetos_vazios": 0,
    }
    for o in ids:
        d["detalhe"][o] = api.detalhe_projeto(o, u, c)
        d["entregas"][o] = api_entregas._entregas(c, o)
        d["vinculos"][o] = sorted(r[0] for r in c.execute("SELECT estrategia_id FROM projeto_estrategia WHERE orcamento=?", (o,)))
    return d


# ---------------------------------------------------------------- parte 1: visão geral

def _parte1(doc: Doc, d: dict) -> None:
    r, rec, hc, vi, ev, cob = d["resumo"], d["receitas"], d["headcount"], d["viagens"], d["eventos"], d["cobertura"]
    P = d["projetos"]
    despesa_proj = [p for p in P if p["tipo"] == "despesa"]
    plano, base, exe = r["total_plano"], r["total_base"], r["total_executado"]
    t = rec["totais"]
    doc.divisoria("1", "Visão geral", "do planejamento")
    doc.lead(
        f"O planejamento de 2027 da ESR soma {mi(plano)} em despesas, em {len(despesa_proj)} projetos, "
        f"{compara(plano, base)} orçamento aprovado para 2026 ({mi(base)}). "
        f"A previsão de receitas é de {mi(t['receita'])}, o que deixa o resultado do ano em {mi(t['resultado'])}.")
    doc.p("Este relatório reúne o que foi construído no planejamento anual. A primeira parte apresenta a visão geral: como o orçamento evolui de 2026 para 2027, "
          "quanto vem de receitas, de pessoas, de viagens e de eventos, e como os projetos se conectam ao Plano Operacional e ao Contrato de Gestão. "
          "A segunda parte traz um capítulo para cada projeto, com os números, as entregas, a relação estratégica e o detalhe de cada linha de orçamento.")

    # 1.1 síntese
    doc.titulo(1, "1.1 Síntese do planejamento")
    doc.indicadores([
        ("Orçamento 2027 (despesas)", mi(plano), f"{var_pc(plano, base)} sobre 2026 aprovado"),
        ("Aprovado 2026", mi(base), f"executado {mi(exe)} ({pc(exe / base * 100 if base else 0)})"),
        ("Receitas 2027", mi(t["receita"]), f"2026: {mi(t['receita_2026'])}"),
        ("Resultado 2027", mi(t["resultado"]), "receitas menos despesas"),
        ("Headcount novo", f"{hc['totais']['posicoes']} posições", f"{mi(hc['totais']['custo_2027'])} em 2027"),
        ("Viagens", mi(vi["totais"]["plano"]), f"{vi['totais']['viagens']} viagens planejadas"),
        ("Eventos", mi(ev["totais"]["total"]), f"{ev['totais']['eventos']} eventos, {ev['totais']['pessoas']} participações"),
        ("Projetos", str(len(P)), f"{sum(1 for p in P if p['novo'])} novos, {sum(1 for p in P if p['contingenciado'])} contingenciados"),
    ])
    st = r["linhas_status"]
    tot_l = sum(st.values()) or 1
    doc.p(f"Das {n0(tot_l)} linhas de orçamento de 2027, **{n0(st['mantida'])}** foram mantidas como em 2026, **{n0(st['ajustada'])}** foram ajustadas pelos gestores, "
          f"**{n0(st['nova'])}** são novas e **{n0(st['viagens'])}** vêm dos planos de viagens, eventos e headcount, que alimentam o orçamento automaticamente.")
    doc.tabela(["Indicador", "2026", "2027", "Variação"], [
        ["Despesas (aprovado 2026 e plano 2027)", rs(base), rs(plano), f"{sinal(plano - base)} ({var_pc(plano, base)})"],
        ["Receitas", rs(t["receita_2026"]), rs(t["receita"]), f"{sinal(t['receita'] - t['receita_2026'])} ({var_pc(t['receita'], t['receita_2026'])})"],
        ["Resultado (receitas menos despesas)", rs(t["receita_2026"] - t["despesa_2026"]), rs(t["resultado"]), sinal(t["resultado"] - (t["receita_2026"] - t["despesa_2026"]))],
        ["Viagens (plano de viagens)", rs(vi["totais"]["ref"]), rs(vi["totais"]["plano"]), f"{sinal(vi['totais']['plano'] - vi['totais']['ref'])} ({var_pc(vi['totais']['plano'], vi['totais']['ref'])})"],
    ], [3600, 1900, 1900, 2238], legenda="Síntese financeira, em R$.")

    # 1.2 evolução
    doc.titulo(1, "1.2 Evolução de 2026 para 2027")
    doc.p(f"O orçamento de 2026 foi aprovado em {mi(base)}; até agora foram empenhados e realizados {mi(exe)} ({pc(exe / base * 100 if base else 0)}). "
          f"Para 2027 o plano soma {mi(plano)}, variação de {sinal(plano - base)} reais ({var_pc(plano, base)}). As tabelas abaixo abrem essa evolução por origem de recurso e por grupo de despesa.")
    doc.titulo(2, "Por origem de recurso", toc=False)
    org = r["por_origem"]
    doc.tabela(["Origem de recurso", "Aprovado 2026", "Executado 2026", "Plano 2027", "Variação", "%"],
               [[o["nome"], n0(o["base"]), n0(o["executado"]), n0(o["plano"]), sinal(o["plano"] - o["base"]), var_pc(o["plano"], o["base"])] for o in org],
               [3200, 1400, 1400, 1400, 1300, 900], total=["Total", n0(base), n0(exe), n0(plano), sinal(plano - base), var_pc(plano, base)],
               legenda="Evolução por origem de recurso, em R$. A origem de 2027 é a vigente no próximo ano.")
    if org:
        png, prop = grafico_grupos([o["nome"] for o in org], [("Aprovado 2026", [o["base"] for o in org], CIANO), ("Plano 2027", [o["plano"] for o in org], NAVY)])
        doc.imagem(png, "Aprovado 2026 e plano 2027 por origem de recurso.", 15.0, prop)
    doc.titulo(2, "Por grupo de despesa", toc=False)
    grp = r["por_grupo"]
    doc.tabela(["Grupo de despesa", "Aprovado 2026", "Executado 2026", "Plano 2027", "Variação", "%"],
               [[g["nome"], n0(g["base"]), n0(g["executado"]), n0(g["plano"]), sinal(g["plano"] - g["base"]), var_pc(g["plano"], g["base"])] for g in grp],
               [3200, 1400, 1400, 1400, 1300, 900], total=["Total", n0(base), n0(exe), n0(plano), sinal(plano - base), var_pc(plano, base)],
               legenda="Evolução por grupo de despesa, em R$.")
    if grp:
        png, prop = grafico_grupos([g["nome"] for g in grp], [("Aprovado 2026", [g["base"] for g in grp], CIANO), ("Plano 2027", [g["plano"] for g in grp], NAVY)])
        doc.imagem(png, "Aprovado 2026 e plano 2027 por grupo de despesa.", 15.0, prop)

    doc.titulo(2, "Calendarização de 2027", toc=False)
    mens = [m["valor"] for m in r["mensal_plano"]]
    rec_m = [m["receita"] for m in rec["mensal"]]
    png, prop = grafico_grupos(ABREV, [("Despesas", mens, NAVY), ("Receitas calendarizadas", rec_m, VERDE)], horizontal=False)
    doc.imagem(png, "Despesas e receitas previstas por mês em 2027.", 16.0, prop)
    doc.tabela(["Mês"] + ABREV, [["Despesas (R$ mil)"] + [n0(v / 1e3) for v in mens], ["Receitas (R$ mil)"] + [n0(v / 1e3) for v in rec_m]],
               [1500] + [670] * 12, tam=13, legenda="Calendarização mensal de 2027, em R$ mil. A receita intercompany não tem calendário.")

    # variações por projeto
    doc.titulo(2, "Projetos que mais mudam", toc=False)
    ordem = sorted(despesa_proj, key=lambda p: p["total_2027"] - p["total_2026"])
    maiores = [p for p in ordem[::-1][:10] if p["total_2027"] - p["total_2026"] > 0]
    menores = [p for p in ordem[:10] if p["total_2027"] - p["total_2026"] < 0]
    lin = lambda p: [f"{p['orcamento']} | {corta(p['descricao'], 46)}", corta(p["gerente"], 22), n0(p["total_2026"]), n0(p["total_2027"]), sinal(p["total_2027"] - p["total_2026"]), var_pc(p["total_2027"], p["total_2026"])]
    cab = ["Projeto", "Gerente", "2026", "2027", "Variação", "%"]
    larg = [3300, 1700, 1200, 1200, 1300, 900]
    if maiores:
        doc.p("**Maiores aumentos em relação ao orçamento de 2026**", keep=True)
        doc.tabela(cab, [lin(p) for p in maiores], larg, legenda="Dez maiores aumentos, em R$.")
    if menores:
        doc.p("**Maiores reduções em relação ao orçamento de 2026**", keep=True)
        doc.tabela(cab, [lin(p) for p in menores], larg, legenda="Dez maiores reduções, em R$.")

    # 1.3 receitas
    doc.titulo(1, "1.3 Receitas e resultado")
    doc.p(f"A previsão de receitas de 2027 é de **{mi(t['receita'])}** contra {mi(t['receita_2026'])} previstos em 2026. Contra as despesas de {mi(t['despesa'])}, "
          f"o resultado é de **{mi(t['resultado'])}**." + (f" Desse total, {mi(t['intercompany'])} são transferências intercompany, que entram no resultado mas não têm calendário mensal." if t["intercompany"] else ""))
    ro = [o for o in rec["por_origem"] if o["receita"] or o["despesa"] or o["receita_2026"]]
    doc.tabela(["Origem de recurso", "Receita 2026", "Receita 2027", "Despesa 2027", "Resultado 2027"],
               [[o["origem"], n0(o["receita_2026"]), n0(o["receita"]), n0(o["despesa"]), n0(o["resultado"])] for o in ro],
               [3400, 1500, 1500, 1600, 1638], total=["Total", n0(t["receita_2026"]), n0(t["receita"]), n0(t["despesa"]), n0(t["resultado"])],
               legenda="Receitas, despesas e resultado por origem de recurso, em R$.")
    com_rec = sorted((p for p in rec["por_projeto"] if p["receita"]), key=lambda p: -p["receita"])
    if com_rec:
        doc.tabela(["Projeto", "Receita 2026", "Receita 2027", "Despesa 2027", "Resultado"],
                   [[f"{p['orcamento']} | {corta(p['projeto'], 50)}", n0(p["receita_2026"]), n0(p["receita"]), n0(p["despesa"]), n0(p["resultado"])] for p in com_rec[:25]],
                   [3900, 1400, 1400, 1400, 1538], legenda="Projetos com receita prevista em 2027, em R$." + (" Os 25 maiores." if len(com_rec) > 25 else ""))
    if t["sem_receita"]:
        doc.p(f"{t['sem_receita']} dos {len(rec['por_projeto'])} projetos não têm receita associada; as suas despesas são cobertas pelas receitas dos demais.")

    # 1.4 headcount
    doc.titulo(1, "1.4 Headcount")
    ht = hc["totais"]
    if hc["itens"]:
        doc.p(f"Foram planejadas **{ht['posicoes']} novas posições** em {len(hc['por_projeto'])} projetos. O custo previsto em 2027, considerando o mês de entrada de cada posição e os equipamentos, "
              f"é de **{mi(ht['custo_2027'])}**; anualizado (doze meses), o custo das posições é de {mi(ht['anualizado'])}. Os salários seguem a tabela salarial vigente, com reajuste de {pc(hc['reajuste'])}, "
              f"mais os encargos e benefícios dos parâmetros de pessoal.")
        doc.tabela(["Projeto", "Posições", "Custo 2027", "Anualizado"],
                   [[f"{x['orcamento']} | {corta(x['projeto'], 56)}", str(x["posicoes"]), n0(x["custo_2027"]), n0(x["anualizado"])] for x in hc["por_projeto"]],
                   [5200, 1100, 1700, 1638], total=["Total", str(ht["posicoes"]), n0(ht["custo_2027"]), n0(ht["anualizado"])], legenda="Headcount por projeto, em R$.")
        doc.tabela(["Função", "Cargo", "Qtd", "Início", "Custo 2027", "Equip."],
                   [[corta(i["funcao"], 40), corta(i["cargo"], 28), str(i["quantidade"]), ABREV[i["mes_inicio"] - 1], n0(i["custo_2027"]), n0(i["equipamentos"]["total"])] for i in hc["itens"]],
                   [3300, 2200, 600, 800, 1500, 1238], alin=["left", "left", "right", "left", "right", "right"], legenda="Posições planejadas, em R$. Equip. = computador, monitor e periféricos.")
        sem = [i for i in hc["itens"] if i["faltando"]]
        if sem:
            doc.p(f"{len(sem)} posição(ões) ainda têm campos pendentes (por exemplo justificativa ou tarefa do orçamento).")
    else:
        doc.p("Não há posições novas de headcount lançadas no planejamento de 2027.")

    # 1.5 viagens
    doc.titulo(1, "1.5 Viagens")
    vt = vi["totais"]
    if vi["viagens"]:
        nac = [v for v in vi["viagens"] if v["tipo"] == "nac"]
        inter = [v for v in vi["viagens"] if v["tipo"] == "int"]
        s = lambda l: sum(v["custo"]["total"] for v in l)
        doc.p(f"O plano de viagens de 2027 soma **{mi(vt['plano'])}** em {vt['viagens']} viagens, contra {mi(vt['ref'])} previstos nas planilhas de 2026 e {mi(vt['aprovado'])} aprovados nas contas de viagem do orçamento 2026 "
              f"(executado até agora: {mi(vt['executado'])}). Valores calculados com a tabela de tarifas vigente; o orçamento 2027 nas contas de viagem é de {mi(vt['orcamento'])}.")
        doc.tabela(["Tipo", "Linhas", "Viagens", "Custo 2027"],
                   [["Nacionais", str(len(nac)), str(sum(v["n_viagens"] for v in nac)), n0(s(nac))], ["Internacionais", str(len(inter)), str(sum(v["n_viagens"] for v in inter)), n0(s(inter))]],
                   [3600, 1800, 1800, 2438], total=["Total", str(len(vi["viagens"])), str(vt["viagens"]), n0(vt["plano"])], legenda="Viagens por tipo, em R$.")
        doc.tabela(["Projeto", "Aprovado 2026", "Executado 2026", "Plano 2027", "Conectado"],
                   [[f"{p['orcamento']} | {corta(p['projeto'], 44)}", n0(p["aprovado_2026"]), n0(p["executado_2026"]), n0(p["plano_2027"]), "sim" if p["conectado"] else "não"] for p in vi["projetos"] if p["plano_2027"] or p["aprovado_2026"]],
                   [3800, 1400, 1400, 1400, 1638], legenda="Viagens por projeto, em R$. Conectado indica que o plano já foi aplicado ao orçamento.")
        png, prop = grafico_grupos(ABREV, [("Planilhas 2026", [m["ref"] for m in vi["mensal"]], CIANO), ("Plano 2027", [m["plano"] for m in vi["mensal"]], NAVY)], horizontal=False)
        doc.imagem(png, "Viagens por mês: planilhas de 2026 e plano de 2027.", 15.0, prop)
        if vt["pendentes"]:
            doc.p(f"{vt['pendentes']} linha(s) de viagem têm pendência (sem projeto, tarefa ou tarifa).")
    else:
        doc.p("Não há viagens planejadas para 2027.")

    # 1.6 eventos
    doc.titulo(1, "1.6 Eventos")
    et = ev["totais"]
    if ev["itens"]:
        doc.p(f"Estão previstos **{et['eventos']} eventos**, com {et['pessoas']} participações da equipe. O custo total é de **{mi(et['total'])}**, sendo {mi(et['inscricao'])} de inscrições "
              f"(dólar a R$ {str(ev['dolar']).replace('.', ',')}) e {mi(et['viagem'])} de viagem.")
        doc.tabela(["Evento", "Local", "Mês", "Pessoas", "Projeto", "Total"],
                   [[corta(e["nome"], 36), corta(e["local"], 22), ABREV[e["mes"] - 1], str(e["n_pessoas"]), e["orcamento"], n0(e["total"])] for e in ev["itens"]],
                   [3000, 2000, 700, 800, 1100, 2038], alin=["left", "left", "left", "right", "left", "right"], total=["Total", "", "", str(et["pessoas"]), "", n0(et["total"])],
                   legenda="Eventos previstos para 2027, em R$.")
        if et["incompletos"]:
            doc.p(f"{et['incompletos']} evento(s) ainda têm informações pendentes.")
    else:
        doc.p("Não há eventos planejados para 2027.")

    # 1.7 conexão estratégica
    doc.titulo(1, "1.7 Conexão com o Plano Operacional e o Contrato de Gestão")
    itens = cob["itens"]
    if itens:
        ligados = sum(1 for p in despesa_proj if p["orcamento"] not in {x["orcamento"] for x in cob["sem_vinculo"]})
        doc.p(f"Cada projeto informa a quais Resultados Operacionais (RO) do Plano Operacional ele serve; o vínculo cobre também o Resultado Estratégico (RE), a Diretriz e o indicador do Contrato de Gestão "
              f"(CG) acima do RO. **{ligados} de {len(despesa_proj)}** projetos de despesa estão vinculados, o que representa {mi(cob['plano_total'] - cob['plano_sem_vinculo'])} dos {mi(cob['plano_total'])} do plano; "
              f"{mi(cob['plano_sem_vinculo'])} ainda não têm vínculo. Como um projeto pode atender a mais de um item, os valores da tabela não se somam.")
        doc.tabela(["Item", "Descrição", "Projetos", "Entregas", "Plano 2027"],
                   [[("**" + rotulo(i) + "**") if i["tipo"] in ("diretriz", "re") else rotulo(i), corta(i["descricao"], 92), str(i["projetos"]), str(i["entregas"]), n0(i["plano_projetos"])] for i in itens],
                   [1100, 4900, 900, 1000, 1738], alin=["left", "left", "right", "right", "right"], legenda="Cobertura do Plano Operacional e do Contrato de Gestão.")
        sem_cobertura = [i for i in itens if i["tipo"] == "po" and not i["projetos"]]
        if sem_cobertura:
            doc.p("**Resultados Operacionais sem nenhum projeto vinculado:** " + "; ".join(f"{rotulo(i)} ({corta(i['descricao'], 70)})" for i in sem_cobertura) + ".")
        if cob["sem_vinculo"]:
            doc.p("**Projetos com orçamento e sem vínculo estratégico**", keep=True)
            doc.tabela(["Projeto", "Plano 2027", "Entregas informadas"],
                       [[f"{x['orcamento']} | {corta(x['projeto'], 64)}", n0(x["plano"]), "sim" if x["tem_entregas"] else "não"] for x in cob["sem_vinculo"]],
                       [6000, 1800, 1838], legenda="Projetos sem vínculo estratégico, em R$.")
    else:
        doc.p("O catálogo estratégico (Plano Operacional e Contrato de Gestão) ainda não foi carregado, por isso o relatório não mostra a conexão dos projetos com ele.")

    # 1.8 acompanhamento
    doc.titulo(1, "1.8 Acompanhamento do planejamento")
    ger = [g for g in d["gerencias"] if g["nivel"] == "gerencia"]
    if ger:
        doc.p("Situação do preenchimento por gerência: cada gerente conclui o seu planejamento depois de revisar projetos, receitas, viagens, eventos, headcount e entregas.")
        doc.tabela(["Gerência", "Projetos", "Plano 2027", "Pendências", "Situação"],
                   [[g["gerencia"] or "Sem gerência", str(g.get("projetos", 0)), n0(g.get("plano", 0)), str(g.get("pendencias", 0)),
                     ("concluído em " + data_br(g.get("concluido_em"))) if g.get("concluido") else "em andamento"] for g in ger],
                   [3400, 1000, 1700, 1100, 2438], alin=["left", "right", "right", "right", "left"], legenda="Situação por gerência.")
    pend = [(o, s_) for o, s_ in d["situacao"].items() if s_["pendencias"]]
    if pend:
        doc.p(f"Há **{sum(s_['pendencias'] for _, s_ in pend)} pendência(s)** em {len(pend)} projeto(s). Os detalhes de cada projeto estão no capítulo correspondente da Parte 2.")

    # 1.9 premissas
    doc.titulo(1, "1.9 Premissas e critérios")
    doc.p("O plano de 2027 parte do orçamento aprovado de 2026. Cada linha pode ser mantida, ajustada ou excluída pelo gestor, e novas linhas podem ser criadas. "
          "Viagens, eventos e headcount são calculados nas suas próprias páginas e alimentam o orçamento. As premissas usadas nos cálculos são:")
    doc.tabela(["Premissa", "Valor", "Descrição"], [[p["chave"], str(p["valor"]).replace(".", ","), p["descricao"]] for p in d["premissas"]],
               [2700, 1100, 5838], alin=["left", "right", "left"], legenda="Premissas do planejamento.")
    esp = [("Projetos novos em 2027", [p for p in P if p["novo"]]), ("Projetos contingenciados (sem exportação para o PMO)", [p for p in P if p["contingenciado"]]),
           ("Projetos replicados de 2026 para 2027", [p for p in P if p["replicado_para"]])]
    for nome, lista in esp:
        if lista:
            doc.p(f"**{nome}:** " + "; ".join(f"{p['orcamento']} ({corta(p['descricao'], 50)})" for p in lista) + ".")


# ---------------------------------------------------------------- parte 2: projetos

def _ordem_proj(p: dict) -> tuple:
    return (p["origem"] or "", p["orcamento"])


def _projeto(doc: Doc, d: dict, p: dict) -> None:
    o = p["orcamento"]
    det, ents, vinc, cat = d["detalhe"][o], d["entregas"][o], d["vinculos"][o], d["catalogo"]
    pr, tot = det["projeto"], det["totais"]
    linhas, passado = det["linhas"], det["passado"]
    receita_tipo = pr["tipo"] == "receita"
    sit = d["situacao"].get(o)
    doc.titulo(1, f"{o} | {pr['descricao']}", quebra=True)
    ficha = [("Orçamento", o), ("Nº do projeto", pr["n_projeto"] or "a informar"), ("Gerente", pr["gerente"]), ("Diretoria", pr["diretoria"]),
             ("Origem 2026", pr["origem_2026"] or "-"), ("Origem 2027", pr["origem"] or "-"),
             ("Tipo", "Receita" if receita_tipo else "Despesa")]
    marcas = []
    if pr["novo"]:
        marcas.append("projeto novo em 2027")
    if pr["contingenciado"]:
        marcas.append("contingenciado")
    if pr["replicado_de"]:
        marcas.append("criado por replicação de " + pr["replicado_de"])
    if pr["replicado_para"]:
        marcas.append(f"replicado para {pr['replicado_para']}")
    ficha.append(("Situação", ", ".join(marcas) if marcas else "projeto de 2026 em continuidade"))
    doc.ficha(ficha)
    if pr["replicado_para"]:
        doc.p(f"As linhas previstas para 2027 deste projeto foram movidas para o projeto **{pr['replicado_para']}**"
              + (f" ({pr['replicado_nome']})" if pr["replicado_nome"] else "") + (f", com origem de recurso {pr['replicado_origem']}" if pr["replicado_origem"] else "")
              + (f", em {data_br(pr['replicado_em'])}" if pr["replicado_em"] else "") + ". Este capítulo mantém só o orçamento aprovado e o executado de 2026.")
    if pr["replicado_de"]:
        doc.p(f"Este projeto foi criado para 2027 a partir de **{pr['replicado_de']}**, que mantém o orçamento de 2026.")
    if pr["contingenciado"]:
        doc.p("Orçamento contingenciado: fica registrado no planejamento mas não é enviado ao PMO.")
    if pr["detalhe"]:
        doc.p(pr["detalhe"])

    plano, aprov = tot["plano"], tot["base"]
    exec_ = tot["realizado"] + tot["empenhado"]
    if receita_tipo:
        doc.lead(f"Orçamento de receita: o total das linhas de 2027 é de {mi(p['receitas_2027'])} (resultado positivo).")
    else:
        frase = f"Em 2027 o projeto planeja {mi(plano)}"
        if aprov:
            frase += f", {compara(plano, aprov)} aprovado em 2026 ({mi(aprov)}), do qual já foram executados {mi(exec_)} ({pc(exec_ / aprov * 100)})"
        frase += f". As receitas associadas são de {mi(p['receitas_2027'])} e o resultado é de {mi(p['resultado_2027'])}." if p["receitas_2027"] else "."
        doc.lead(frase)

    # números
    doc.titulo(2, "Números do projeto")
    ind = [("Aprovado 2026 (R$)", n0(aprov), f"original: {n0(pr['original_2026'])}" if pr["original_2026"] and abs(pr["original_2026"] - aprov) > 1 else "orçamento de 2026"),
           ("Executado 2026 (R$)", n0(exec_), f"empenhado {n0(tot['empenhado'])}, realizado {n0(tot['realizado'])}"),
           ("Plano 2027 (R$)", n0(plano) if not receita_tipo else "-", f"{sinal(plano - aprov)} ({var_pc(plano, aprov)})" if not receita_tipo else "orçamento de receita"),
           ("Resultado 2027 (R$)", n0(p["resultado_2027"]), f"receitas {n0(p['receitas_2027'])}")]
    doc.indicadores(ind)
    grupos: dict[str, dict] = {}
    for x in passado:
        g = grupos.setdefault(x["grupo"] or "Sem grupo", {"base": 0.0, "exe": 0.0, "plano": 0.0})
        g["base"] += x["aprovado"]
        g["exe"] += x["executado"]
    for x in linhas:
        g = grupos.setdefault(x["grupo"] or "Sem grupo", {"base": 0.0, "exe": 0.0, "plano": 0.0})
        g["plano"] += x["total"]
    if grupos and not receita_tipo:
        doc.tabela(["Grupo de despesa", "Aprovado 2026", "Executado 2026", "Plano 2027", "Variação"],
                   [[k, n0(v["base"]), n0(v["exe"]), n0(v["plano"]), sinal(v["plano"] - v["base"])] for k, v in sorted(grupos.items(), key=lambda kv: -kv[1]["plano"])],
                   [3600, 1500, 1500, 1500, 1538], total=["Total", n0(aprov), n0(exec_), n0(plano), sinal(plano - aprov)], legenda="Orçamento do projeto por grupo de despesa, em R$.")
    mensal = [sum(x["meses"][i] for x in linhas) for i in range(12)]
    if any(mensal):
        doc.tabela(ABREV + ["Total"], [[n0(v / 1e3) for v in mensal] + [n0(sum(mensal) / 1e3)]], [700] * 12 + [1238], tam=13, alin=["right"] * 13,
                   legenda="Calendarização de 2027, em R$ mil.")
    st = tot["status"]
    if linhas:
        doc.p(f"Linhas de 2027: **{len(linhas)}** (mantidas {st['mantida']}, ajustadas {st['ajustada']}, novas {st['nova']}, do plano de viagens, eventos e headcount {st['viagens']}). "
              f"Linhas de 2026 sem correspondente em 2027: {tot['removidas']}.")

    # relação estratégica
    doc.titulo(2, "Relação estratégica")
    por_id = {e["id"]: e for e in cat}
    cobre = set(vinc)
    for e in ents:
        cobre |= set(e["estrategia"])
    if not cat:
        doc.p("O catálogo estratégico ainda não foi carregado.")
    elif not cobre:
        doc.p("**Este projeto ainda não está vinculado a nenhum Resultado Operacional, Resultado Estratégico, Diretriz ou indicador do Contrato de Gestão.**")
    else:
        fe = estrategia.fecho(cat, cobre)
        ordem_t = {"diretriz": 0, "re": 1, "po": 2, "cg": 3}
        lista = sorted((por_id[i] for i in fe), key=lambda e: (ordem_t[e["tipo"]], e["codigo"]))
        diretos = {i for i in vinc}
        doc.p("O orçamento do projeto está ligado aos itens abaixo. Os itens marcados como direto foram escolhidos pelo gestor (no projeto ou nas entregas); os demais são os que ficam acima deles na hierarquia.")
        doc.tabela(["Nível", "Item", "Descrição", "Vínculo"],
                   [[NOME_TIPO[e["tipo"]], rotulo(e), corta(e["descricao"], 150), "direto" if (e["id"] in diretos or any(e["id"] in x["estrategia"] for x in ents)) else "pela hierarquia"] for e in lista],
                   [2000, 1000, 5400, 1238], alin=["left", "left", "left", "left"], legenda="Itens do Plano Operacional e do Contrato de Gestão atendidos pelo projeto.")
        for e in lista:
            if e["tipo"] == "po" and (e["meta"] or e["objetivo"]):
                doc.p(f"**{rotulo(e)}:** " + (f"{e['objetivo']} " if e["objetivo"] else "") + (f"Meta: {e['meta']}" if e["meta"] else ""), tam=18)
    doc.titulo(2, "Entregas previstas")
    if ents:
        doc.tabela(["Entrega", "Mês", "KPI", "Meta", "Conexão"],
                   [[e["descricao"], ABREV[e["mes"] - 1] if e["mes"] else "-", e["kpi"] or "-", e["meta"] or "-",
                     ", ".join(rotulo(por_id[i]) for i in e["estrategia"] if i in por_id) or "-"] for e in ents],
                   [3500, 600, 2000, 1900, 1638], alin=["left", "left", "left", "left", "left"], legenda="Entregas previstas para 2027.")
    else:
        doc.p("Nenhuma entrega informada para 2027." if not pr["contingenciado"] else "Projeto contingenciado, sem entregas informadas.")

    # orçamento por meta e ação
    if linhas:
        doc.titulo(2, "Orçamento 2027 por meta e ação")
        rows, ant = [], (None, None)
        for x in linhas:
            chave = (x["edt"], x["tarefa"])
            rows.append([x["edt"] if chave[0] != ant[0] else "", x["tarefa"] if chave != ant else "", f"{x['conta_codigo']} {corta(x['conta_desc'], 34)}",
                         n0(x["ref"]["total"]) if x["ref"] else "-", n0(x["total"]), STATUS.get(x["status"], x["status"])])
            ant = chave
        doc.tabela(["Meta (EDT)", "Ação (tarefa)", "Conta", "2026", "2027", "Situação"], rows, [1500, 2400, 2500, 1100, 1100, 1038],
                   alin=["left", "left", "left", "right", "right", "left"], tam=14, total=["Total", "", "", n0(aprov), n0(plano), ""],
                   legenda="Linhas do orçamento, em R$. 2026 é o valor aprovado da linha correspondente.")
        obs = [x for x in linhas if x["obs"]]
        if obs:
            doc.p("**Observações dos gestores**", keep=True)
            for x in obs[:15]:
                doc.p(f"{x['conta_codigo']} {corta(x['conta_desc'], 30)}: {x['obs']}", tam=18, depois=60)
    rem = [x for x in passado if x["removida"]]
    if rem:
        doc.titulo(2, "Linhas de 2026 sem correspondente em 2027")
        doc.tabela(["Meta (EDT)", "Ação (tarefa)", "Conta", "Aprovado 2026", "Executado"],
                   [[x["edt"], x["tarefa"], f"{x['conta_codigo']} {corta(x['conta_desc'], 34)}", n0(x["aprovado"]), n0(x["executado"])] for x in rem],
                   [1500, 2700, 2700, 1400, 1338], alin=["left", "left", "left", "right", "right"], tam=14, legenda="Linhas excluídas do orçamento de 2027, em R$.")

    # viagens, eventos, headcount, receitas do projeto
    vs = [v for v in d["viagens"]["viagens"] if v["orcamento"] == o]
    if vs:
        doc.titulo(2, "Viagens")
        doc.tabela(["Mês", "Trecho", "Tipo", "Viagens", "Dias", "Objetivo", "Custo"],
                   [[ABREV[v["mes"] - 1], f"{v['origem']} - {v['destino']}", "Int." if v["tipo"] == "int" else "Nac.", str(v["n_viagens"]), str(v["dias"]), corta(v["objetivo"], 40), n0(v["custo"]["total"])] for v in vs],
                   [600, 2400, 600, 800, 600, 3000, 1638], alin=["left", "left", "left", "right", "right", "left", "right"], tam=14,
                   total=["Total", "", "", str(sum(v["n_viagens"] for v in vs)), "", "", n0(sum(v["custo"]["total"] for v in vs))], legenda="Plano de viagens do projeto, em R$.")
    es = [e for e in d["eventos"]["itens"] if e["orcamento"] == o]
    if es:
        doc.titulo(2, "Eventos")
        doc.tabela(["Evento", "Local", "Mês", "Pessoas", "Total"],
                   [[corta(e["nome"], 50), corta(e["local"], 28), ABREV[e["mes"] - 1], str(e["n_pessoas"]), n0(e["total"])] for e in es],
                   [4000, 2400, 800, 900, 1538], alin=["left", "left", "left", "right", "right"], tam=14, total=["Total", "", "", str(sum(e["n_pessoas"] for e in es)), n0(sum(e["total"] for e in es))],
                   legenda="Eventos do projeto, em R$.")
        for e in es:
            if e["justificativa"]:
                doc.p(f"**{corta(e['nome'], 50)}:** {e['justificativa']}", tam=18, depois=60)
    hs = [h for h in d["headcount"]["itens"] if h["orcamento"] == o]
    if hs:
        doc.titulo(2, "Headcount")
        doc.tabela(["Função", "Cargo", "Qtd", "Início", "Custo 2027", "Anualizado"],
                   [[corta(h["funcao"], 40), corta(h["cargo"], 28), str(h["quantidade"]), ABREV[h["mes_inicio"] - 1], n0(h["custo_2027"]), n0(h["anualizado"])] for h in hs],
                   [3300, 2200, 600, 800, 1400, 1338], alin=["left", "left", "right", "left", "right", "right"], tam=14, legenda="Posições novas do projeto, em R$.")
        for h in hs:
            if h["justificativa"]:
                doc.p(f"**{corta(h['funcao'], 40)}:** {h['justificativa']}", tam=18, depois=60)
    rs_ = [r for r in d["receitas"]["linhas"] if r["orcamento"] == o]
    if rs_:
        doc.titulo(2, "Receitas")
        doc.tabela(["Descrição", "Cliente", "Tipo", "2026", "2027"],
                   [[corta(r["descricao"], 56), corta(r["cliente"] or "-", 26), "intercompany" if r["tipo"] == "intercompany" else "externa", n0(r["ref"]["total"]) if r["ref"] else "-", n0(r["total"])] for r in rs_],
                   [3700, 2000, 1300, 1200, 1438], alin=["left", "left", "left", "right", "right"], tam=14, total=["Total", "", "", "", n0(sum(r["total"] for r in rs_))],
                   legenda="Receitas do projeto, em R$.")

    # pendências
    if sit and sit["pendencias"]:
        doc.titulo(2, "Pendências")
        itens = []
        for k, nome in (("viagens", "viagens"), ("eventos", "eventos"), ("headcount", "posições de headcount")):
            if sit[k]["pendentes"]:
                itens.append(f"{sit[k]['pendentes']} item(ns) de {nome} com informação incompleta")
        if sit["entregas"]["pendentes"]:
            itens.append({"sem entregas": "projeto sem entregas informadas", "sem vínculo estratégico": "projeto sem vínculo estratégico"}.get(sit["entregas"]["motivo"], sit["entregas"]["motivo"]))
        doc.p("; ".join(itens)[:1].upper() + "; ".join(itens)[1:] + ".")


def _parte2(doc: Doc, d: dict) -> None:
    doc.divisoria("2", "Projetos", "")
    doc.lead(f"A seguir, {len(d['projetos'])} projetos, um por capítulo e agrupados por origem de recurso de 2027. Cada capítulo traz a identificação, os números de 2026 e de 2027, "
             "a relação com o Plano Operacional e o Contrato de Gestão, as entregas e o detalhe do orçamento.")
    ordenados = sorted(d["projetos"], key=_ordem_proj)
    origem = None
    primeiro = True
    for p in ordenados:
        if p["origem"] != origem:
            origem = p["origem"]
        _projeto(doc, d, p)


def gerar(c: sqlite3.Connection, u: dict) -> bytes:
    dados = coletar(c, u)
    doc = Doc()
    _parte1(doc, dados)
    _parte2(doc, dados)
    return montar(doc, "Planejamento Anual 2027", "Para o Diretor Executivo", "PLANEJAMENTO ANUAL 2027", "ESCOLA SUPERIOR DE REDES")
