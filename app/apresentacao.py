"""Apresentação executiva do orçamento (PowerPoint), no padrão visual do template ESR 20 Anos.

Foco em alto nível: números principais, evolução de 2026 para 2027 por origem, finalidade e grupo de despesa, gerências, principais projetos,
receitas e resultado, conexão com o Plano Operacional e o Contrato de Gestão e pontos de atenção.
Usa os mesmos dados do relatório do Diretor Executivo (relatorio.coletar)."""
from __future__ import annotations

import copy
import io
import sqlite3
from datetime import datetime
from pathlib import Path

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

from . import relatorio
from .relatorio import corta, mi, n0, pc, rotulo, sinal, var_pc

TEMPLATE = Path(__file__).parent / "assets" / "ESR_20Anos_Template.pptx"
NAVY, LARANJA, ESCURO = RGBColor(0x1B, 0x2D, 0x5B), RGBColor(0xE8, 0x77, 0x22), RGBColor(0x0D, 0x1B, 0x3E)
CLARO, BORDA, AZULC, BRANCO = RGBColor(0xF4, 0xF6, 0xFA), RGBColor(0xD0, 0xD7, 0xE8), RGBColor(0x9F, 0xB0, 0xD3), RGBColor(0xFF, 0xFF, 0xFF)
TEXTO, MUDO, VERDE, VERMELHO = RGBColor(0x1B, 0x2D, 0x5B), RGBColor(0x5B, 0x67, 0x86), RGBColor(0x1E, 0x8E, 0x3E), RGBColor(0xB4, 0x23, 0x18)
FONTE = "Calibri"
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
ABREV = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
L, R_ = 0.3, 9.7                    # margens laterais, em polegadas
TOPO, BASE = 1.05, 5.2              # área útil abaixo do cabeçalho e acima do rodapé


# ---------------------------------------------------------------- blocos de desenho

def _rect(s, x, y, w, h, fill, linha=None):
    sh = s.shapes.add_shape(1, Inches(x), Inches(y), Inches(w), Inches(h))
    sh.fill.solid()
    sh.fill.fore_color.rgb = fill
    if linha is None:
        sh.line.fill.background()
    else:
        sh.line.color.rgb = linha
        sh.line.width = Pt(0.5)
    sh.shadow.inherit = False
    return sh


def _txt(s, x, y, w, h, texto, tam=12, negrito=False, cor=TEXTO, alin=PP_ALIGN.LEFT, ancora=MSO_ANCHOR.TOP, italico=False):
    """Caixa de texto; `texto` pode ser uma string ou uma lista de parágrafos (cada um string ou lista de (texto, negrito, cor))."""
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = ancora
    paragrafos = texto if isinstance(texto, list) else [texto]
    for i, par in enumerate(paragrafos):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = alin
        if i:
            p.space_before = Pt(5)
        trechos = par if isinstance(par, list) else [(par, negrito, cor)]
        for t, neg, c in trechos:
            r = p.add_run()
            r.text = t
            r.font.size, r.font.bold, r.font.italic, r.font.name = Pt(tam), neg, italico, FONTE
            r.font.color.rgb = c
    return tb


def _novo(prs, titulo: str, n: int):
    """Slide de conteúdo no padrão do template: faixa azul com título, barra laranja e rodapé."""
    s = prs.slides.add_slide(prs.slide_layouts[0])
    _rect(s, 0, 0, 10, 0.85, NAVY)
    _rect(s, 0, 0, 0.18, 0.85, LARANJA)
    _txt(s, 0.35, 0, 8.4, 0.85, titulo.upper(), 20, True, BRANCO, ancora=MSO_ANCHOR.MIDDLE)
    _rect(s, 0, 5.35, 10, 0.275, NAVY)
    _txt(s, 0.3, 5.35, 6, 0.275, "ESR — Escola Superior de Redes | Orçamento 2027", 8, False, BRANCO, ancora=MSO_ANCHOR.MIDDLE)
    _txt(s, 8.5, 5.35, 1.2, 0.275, str(n), 8, True, LARANJA, PP_ALIGN.RIGHT, MSO_ANCHOR.MIDDLE)
    return s


def _cartao(s, x, y, w, h, titulo=None):
    _rect(s, x, y, w, h, CLARO, BORDA)
    _rect(s, x, y, 0.07, h, LARANJA)
    if titulo:
        _txt(s, x + 0.2, y + 0.1, w - 0.3, 0.3, titulo, 13, True, NAVY, ancora=MSO_ANCHOR.MIDDLE)


def _kpi(s, x, y, w, h, valor, rotulo_, apoio="", laranja=False):
    """Cartão de número, alternando azul e laranja como no slide 'Nossos números' do template."""
    _rect(s, x, y, w, h, LARANJA if laranja else NAVY)
    cor_num = BRANCO if laranja else LARANJA
    _txt(s, x, y + h * 0.16, w, h * 0.36, valor, 26, True, cor_num, PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)
    _rect(s, x + w * 0.3, y + h * 0.56, w * 0.4, 0.03, BRANCO if not laranja else BRANCO)
    _txt(s, x + 0.1, y + h * 0.62, w - 0.2, 0.3, rotulo_, 12, True, BRANCO, PP_ALIGN.CENTER)
    if apoio:
        _txt(s, x + 0.1, y + h * 0.62 + 0.27, w - 0.2, 0.4, apoio, 10, False, BRANCO, PP_ALIGN.CENTER)


def _kpi_leve(s, x, y, w, h, valor, rotulo_, apoio=""):
    _rect(s, x, y, w, h, CLARO, BORDA)
    _rect(s, x, y, 0.06, h, LARANJA)
    _txt(s, x + 0.2, y + 0.08, w - 0.3, 0.42, valor, 20, True, NAVY, ancora=MSO_ANCHOR.MIDDLE)
    _txt(s, x + 0.2, y + 0.52, w - 0.3, 0.25, rotulo_, 11, True, MUDO)
    if apoio:
        _txt(s, x + 0.2, y + 0.75, w - 0.3, h - 0.78, apoio, 9.5, False, MUDO)


def _grafico(s, x, y, w, h, cats, series, horizontal=False, rotulos=True):
    """Barras agrupadas nativas (editáveis no PowerPoint). Valores em R$ milhões."""
    cd = CategoryChartData()
    if horizontal:                                # barras horizontais desenham de baixo para cima: invertemos para ler de cima para baixo
        cats, series = list(cats)[::-1], [(n_, list(v)[::-1], c_) for n_, v, c_ in series][::-1]
    cd.categories = [corta(str(c), 30) for c in cats]
    for nome, vals, _ in series:
        cd.add_series(nome, [round(v / 1e6, 2) for v in vals])
    tipo = XL_CHART_TYPE.BAR_CLUSTERED if horizontal else XL_CHART_TYPE.COLUMN_CLUSTERED
    gf = s.shapes.add_chart(tipo, Inches(x), Inches(y), Inches(w), Inches(h), cd)
    ch = gf.chart
    ch.font.size, ch.font.name = Pt(10), FONTE
    ch.font.color.rgb = TEXTO
    ch.has_legend = len(series) > 1
    if ch.has_legend:
        ch.legend.position = XL_LEGEND_POSITION.TOP
        ch.legend.include_in_layout = False
    plot = ch.plots[0]
    plot.gap_width, plot.overlap = 60, -5
    for ser, (_, _, cor) in zip(plot.series, series):
        ser.format.fill.solid()
        ser.format.fill.fore_color.rgb = cor
    if rotulos:
        plot.has_data_labels = True
        dl = plot.data_labels
        dl.number_format, dl.number_format_is_linked = '#,##0.0', False
        dl.font.size = Pt(9)
    va = ch.value_axis
    va.minimum_scale = 0
    va.has_major_gridlines = True
    va.major_gridlines.format.line.color.rgb = BORDA
    va.format.line.fill.background()
    va.tick_labels.font.size = Pt(9)
    va.tick_labels.number_format, va.tick_labels.number_format_is_linked = '#,##0', False
    va.has_title = True
    va.axis_title.text_frame.text = "R$ milhões"
    va.axis_title.text_frame.paragraphs[0].runs[0].font.size = Pt(9)
    va.axis_title.text_frame.paragraphs[0].runs[0].font.bold = False
    ca = ch.category_axis
    ca.tick_labels.font.size = Pt(9)
    ca.format.line.color.rgb = BORDA
    return ch


def _tabela(s, x, y, larguras, cab, linhas, total=None, tam=10, alin=None, alt=0.3):
    """Tabela nativa no estilo do template: cabeçalho azul, linhas zebradas, total em destaque."""
    nl = len(linhas) + 1 + (1 if total else 0)
    gf = s.shapes.add_table(nl, len(cab), Inches(x), Inches(y), Inches(sum(larguras)), Inches(alt * nl))
    t = gf.table
    tblPr = gf._element.graphic.graphicData.tbl.tblPr
    tblPr.set("bandRow", "0")
    tblPr.set("firstRow", "0")
    for i, wcol in enumerate(larguras):
        t.columns[i].width = Inches(wcol)
    alin = alin or (["l"] + ["r"] * (len(cab) - 1))
    todas = [("cab", cab)] + [("lin", r) for r in linhas] + ([("tot", total)] if total else [])
    for i, (tipo, vals) in enumerate(todas):
        t.rows[i].height = Inches(alt)
        for j, v in enumerate(vals):
            c = t.cell(i, j)
            c.margin_left = c.margin_right = Inches(0.07)
            c.margin_top = c.margin_bottom = Inches(0.02)
            c.vertical_anchor = MSO_ANCHOR.MIDDLE
            c.fill.solid()
            c.fill.fore_color.rgb = NAVY if tipo == "cab" else (BORDA if tipo == "tot" else (CLARO if i % 2 == 0 else BRANCO))
            p = c.text_frame.paragraphs[0]
            p.alignment = PP_ALIGN.RIGHT if alin[j] == "r" else PP_ALIGN.LEFT
            r = p.add_run()
            r.text = str(v)
            r.font.size, r.font.name = Pt(tam), FONTE
            r.font.bold = tipo != "lin"
            r.font.color.rgb = BRANCO if tipo == "cab" else TEXTO
    return t


def _leitura(s, x, y, w, h, titulo, pontos, tam=12):
    _cartao(s, x, y, w, h, titulo)
    _txt(s, x + 0.2, y + 0.5, w - 0.35, h - 0.6, [[("• ", True, LARANJA), (p, False, TEXTO)] for p in pontos], tam)


def _ms(v: float) -> str:
    """Valor em R$ milhões para tabelas, com uma casa."""
    return f"{v / 1e6:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _pl(n: int, um: str, varios: str) -> str:
    return f"{n} {um if n == 1 else varios}"


def _nome(g: dict) -> str:
    return g.get("gerencia") or "Sem gerência"


# ---------------------------------------------------------------- slides

def _capa(prs, agora: datetime) -> None:
    s = prs.slides[0]
    _texto(s, "Text 4", "ORÇAMENTO ESR 2027")
    _texto(s, "Text 5", "Visão executiva do planejamento anual")
    _texto(s, "Text 7", f"Diretoria Adjunta da ESR • {MESES[agora.month - 1].capitalize()} de {agora.year}")


def _texto(slide, nome: str, novo: str) -> None:
    """Troca o texto de uma forma do template mantendo a formatação do primeiro trecho."""
    for sh in slide.shapes:
        if sh.name == nome and sh.has_text_frame:
            p = sh.text_frame.paragraphs[0]
            runs = p.runs
            runs[0].text = novo
            for r in runs[1:]:
                r._r.getparent().remove(r._r)
            for extra in sh.text_frame.paragraphs[1:]:
                extra._p.getparent().remove(extra._p)
            return


def _slide_resumo(prs, d, n):
    r, rec, hc, vi, ev, P = d["resumo"], d["receitas"], d["headcount"], d["viagens"], d["eventos"], d["projetos"]
    plano, base, exe, t = r["total_plano"], r["total_base"], r["total_executado"], rec["totais"]
    desp = [p for p in P if p["tipo"] == "despesa"]
    s = _novo(prs, "Resumo executivo", n)
    w, gap = 2.15, 0.267
    x = lambda i: L + i * (w + gap)
    _kpi(s, x(0), TOPO, w, 1.95, mi(plano), "Plano 2027", "despesas planejadas")
    _kpi(s, x(1), TOPO, w, 1.95, mi(base), "Aprovado 2026", f"executado {mi(exe)} ({pc(exe / base * 100 if base else 0, 0)})", laranja=True)
    _kpi(s, x(2), TOPO, w, 1.95, var_pc(plano, base), "Variação", ("+" if plano - base > 0.5 else "") + mi(plano - base))
    _kpi(s, x(3), TOPO, w, 1.95, str(len(desp)), "Projetos", _pl(sum(1 for p in desp if p["novo"]), "novo em 2027", "novos em 2027"), laranja=True)
    y2 = TOPO + 1.95 + 0.22
    _kpi_leve(s, x(0), y2, w, 1.4, mi(t["receita"]), "Receitas 2027", f"2026: {mi(t['receita_2026'])}")
    _kpi_leve(s, x(1), y2, w, 1.4, mi(t["resultado"]), "Resultado 2027", "receitas menos despesas")
    _kpi_leve(s, x(2), y2, w, 1.4, f"{hc['totais']['posicoes']} posições", "Headcount novo", f"{mi(hc['totais']['custo_2027'])} em 2027")
    _kpi_leve(s, x(3), y2, w, 1.4, mi(vi["totais"]["plano"] + ev["totais"]["total"]), "Viagens e eventos", f"{vi['totais']['viagens']} viagens, {ev['totais']['eventos']} eventos")


def _slide_origem(prs, d, n):
    r = d["resumo"]
    org = [o for o in r["por_origem"] if o["plano"] or o["base"]]
    s = _novo(prs, "De 2026 para 2027 por origem de recurso", n)
    _grafico(s, L, TOPO, 5.9, BASE - TOPO, [o["nome"] for o in org], [("Aprovado 2026", [o["base"] for o in org], AZULC), ("Plano 2027", [o["plano"] for o in org], NAVY)])
    pontos = []
    if org:
        mais = max(org, key=lambda o: o["plano"] - o["base"])
        menos = min(org, key=lambda o: o["plano"] - o["base"])
        maior = max(org, key=lambda o: o["plano"])
        pontos.append(f"{maior['nome']} é a maior origem em 2027: {mi(maior['plano'])} ({pc(maior['plano'] / r['total_plano'] * 100 if r['total_plano'] else 0, 0)} do plano).")
        if mais["plano"] - mais["base"] > 0:
            pontos.append(f"Maior aumento: {mais['nome']}, +{mi(mais['plano'] - mais['base'])} ({var_pc(mais['plano'], mais['base'])}).")
        if menos["plano"] - menos["base"] < 0:
            pontos.append(f"Maior redução: {menos['nome']}, {mi(menos['plano'] - menos['base'])} ({var_pc(menos['plano'], menos['base'])}).")
    pontos.append(f"Total: {mi(r['total_plano'])} contra {mi(r['total_base'])} aprovados em 2026 ({var_pc(r['total_plano'], r['total_base'])}).")
    _leitura(s, 6.4, TOPO, 3.3, BASE - TOPO, "Leitura", pontos, 12)


def _slide_finalidade(prs, d, n):
    r = d["resumo"]
    fin = [f for f in r["por_finalidade"] if f["plano"] or f["base"]]
    s = _novo(prs, "Por finalidade do orçamento", n)
    _grafico(s, L, TOPO, 5.9, BASE - TOPO, [f["nome"] for f in fin], [("Aprovado 2026", [f["base"] for f in fin], AZULC), ("Plano 2027", [f["plano"] for f in fin], NAVY)], horizontal=True)
    tot = r["total_plano"] or 1
    linhas = [[corta(f["nome"], 22), _ms(f["plano"]), pc(f["plano"] / tot * 100, 0), var_pc(f["plano"], f["base"])] for f in sorted(fin, key=lambda f: -f["plano"])]
    _cartao(s, 6.4, TOPO, 3.3, BASE - TOPO, "Plano 2027 (R$ mi)")
    _tabela(s, 6.55, TOPO + 0.5, [1.3, 0.6, 0.45, 0.65], ["Finalidade", "R$ mi", "%", "Δ"], linhas, tam=9, alt=0.3)


def _slide_matriz(prs, d, n):
    r = d["resumo"]
    org = [o for o in r["por_origem"] if o["plano"]]
    fins = [f["nome"] for f in sorted(r["por_finalidade"], key=lambda f: -f["plano"]) if f["plano"]]
    s = _novo(prs, "Origem de recurso e finalidade (plano 2027)", n)
    linhas = []
    for o in org:
        por = {f["nome"]: f["plano"] for f in o.get("finalidades", [])}
        linhas.append([o["nome"]] + [(_ms(por[f]) if por.get(f) else "-") for f in fins] + [_ms(o["plano"])])
    tot = ["Total"] + [_ms(sum(dict((f["nome"], f["plano"]) for f in o.get("finalidades", [])).get(fn, 0) for o in org)) for fn in fins] + [_ms(r["total_plano"])]
    larg_nome, larg_tot = 1.7, 0.95
    lf = (R_ - L - larg_nome - larg_tot) / max(1, len(fins))
    _tabela(s, L, TOPO + 0.05, [larg_nome] + [lf] * len(fins) + [larg_tot], ["Origem"] + [corta(f, 26) for f in fins] + ["Total"], linhas, tot, tam=10, alt=0.42)
    _txt(s, L, BASE - 0.3, R_ - L, 0.3, "Valores em R$ milhões. Cada linha mostra de qual origem de recurso vem o orçamento e para que finalidade ele é usado.", 10, False, MUDO, italico=True)


def _slide_grupos(prs, d, n):
    r = d["resumo"]
    grp = [g for g in sorted(r["por_grupo"], key=lambda g: -g["plano"]) if g["plano"] or g["base"]][:8]
    s = _novo(prs, "Principais grupos de despesa", n)
    _grafico(s, L, TOPO, 5.9, BASE - TOPO, [g["nome"] for g in grp], [("Aprovado 2026", [g["base"] for g in grp], AZULC), ("Plano 2027", [g["plano"] for g in grp], NAVY)], horizontal=True)
    sub = [g for g in r["por_grupo"] if g["plano"] or g["base"]]
    pontos = []
    if sub:
        maior = max(sub, key=lambda g: g["plano"])
        pontos.append(f"{maior['nome']} concentra {mi(maior['plano'])}, {pc(maior['plano'] / r['total_plano'] * 100 if r['total_plano'] else 0, 0)} do plano.")
        aum = max(sub, key=lambda g: g["plano"] - g["base"])
        red = min(sub, key=lambda g: g["plano"] - g["base"])
        if aum["plano"] - aum["base"] > 0:
            pontos.append(f"Maior aumento: {aum['nome']} (+{mi(aum['plano'] - aum['base'])}).")
        if red["plano"] - red["base"] < 0:
            pontos.append(f"Maior redução: {red['nome']} ({mi(red['plano'] - red['base'])}).")
    pontos.append(f"{len(sub)} grupos de despesa no plano; os oito maiores aparecem ao lado.")
    _leitura(s, 6.4, TOPO, 3.3, BASE - TOPO, "Leitura", pontos, 12)


def _slide_gerencias(prs, d, n):
    ger = [g for g in d["gerencias"] if g["nivel"] == "gerencia" and (g["plano"] or g["aprovado"])]
    s = _novo(prs, "Orçamento por gerência", n)
    if not ger:
        _txt(s, L, TOPO, 9.4, 1, "Não há gerências com orçamento.", 14)
        return
    ger = sorted(ger, key=lambda g: -g["plano"])[:10]
    tp, ta = sum(g["plano"] for g in ger), sum(g["aprovado"] for g in ger)
    linhas = [[corta(_nome(g), 40), str(g["projetos"]), _ms(g["aprovado"]), _ms(g["plano"]), _dm(g["plano"] - g["aprovado"]), var_pc(g["plano"], g["aprovado"]),
               "concluído" if g.get("concluido") else "em andamento"] for g in ger]
    _tabela(s, L, TOPO + 0.05, [3.3, 0.8, 1.2, 1.2, 1.1, 0.8, 1.0], ["Gerência", "Projetos", "Aprovado 2026", "Plano 2027", "Variação", "%", "Situação"], linhas,
            ["Total", str(sum(g["projetos"] for g in ger)), _ms(ta), _ms(tp), _dm(tp - ta), var_pc(tp, ta), ""], tam=10, alin=["l", "r", "r", "r", "r", "r", "l"], alt=0.33)
    _txt(s, L, BASE - 0.3, R_ - L, 0.3, "Valores em R$ milhões.", 10, False, MUDO, italico=True)


def _dm(v: float) -> str:
    return ("+" if v > 5e4 else "") + _ms(v)


def _slide_projetos(prs, d, n):
    desp = sorted((p for p in d["projetos"] if p["tipo"] == "despesa" and p["total_2027"] > 0), key=lambda p: -p["total_2027"])[:10]
    s = _novo(prs, "Dez maiores projetos de 2027", n)
    tot26 = sum(p["total_2026"] for p in desp)
    tot27 = sum(p["total_2027"] for p in desp)
    todos27 = d["resumo"]["total_plano"] or 1
    linhas = [[f"{p['orcamento']} | {corta(p['descricao'].replace('DSS-ESR-', ''), 46)}", corta(p["gerente"], 20), _ms(p["total_2026"]), _ms(p["total_2027"]), var_pc(p["total_2027"], p["total_2026"])] for p in desp]
    _tabela(s, L, TOPO + 0.05, [4.1, 1.8, 1.2, 1.2, 1.1], ["Projeto", "Gerente", "2026", "2027", "Variação"], linhas, ["Total dos dez", "", _ms(tot26), _ms(tot27), var_pc(tot27, tot26)], tam=9.5, alin=["l", "l", "r", "r", "r"], alt=0.29)
    _txt(s, L, BASE - 0.2, R_ - L, 0.25, f"Valores em R$ milhões. Os dez projetos somam {pc(tot27 / todos27 * 100, 0)} do plano de 2027.", 10, False, MUDO, italico=True)


def _slide_mudam(prs, d, n):
    desp = [p for p in d["projetos"] if p["tipo"] == "despesa"]
    ordem = sorted(desp, key=lambda p: p["total_2027"] - p["total_2026"])
    mais = [p for p in ordem[::-1][:5] if p["total_2027"] - p["total_2026"] > 0]
    menos = [p for p in ordem[:5] if p["total_2027"] - p["total_2026"] < 0]
    s = _novo(prs, "Projetos que mais mudam", n)
    for xi, titulo, lista, cor in ((L, "Maiores aumentos", mais, LARANJA), (5.1, "Maiores reduções", menos, NAVY)):
        _cartao(s, xi, TOPO, 4.6, BASE - TOPO, titulo)
        if not lista:
            _txt(s, xi + 0.2, TOPO + 0.55, 4.2, 0.4, "Nenhum projeto neste grupo.", 12, False, MUDO)
        y = TOPO + 0.55
        for p in lista:
            dif = p["total_2027"] - p["total_2026"]
            _txt(s, xi + 0.2, y, 2.95, 0.62, [[(corta(p["descricao"].replace("DSS-ESR-", ""), 44), True, NAVY)], [(f"{p['orcamento']} | {corta(p['gerente'], 24)}", False, MUDO)]], 10.5)
            _txt(s, xi + 3.1, y, 1.35, 0.62, [[(("+" if dif > 0 else "") + mi(dif), True, cor if cor == LARANJA else NAVY)], [(var_pc(p["total_2027"], p["total_2026"]), False, MUDO)]], 11, alin=PP_ALIGN.RIGHT)
            y += 0.7


def _slide_receitas(prs, d, n):
    r, rec = d["resumo"], d["receitas"]
    t = rec["totais"]
    s = _novo(prs, "Receitas, despesas e resultado", n)
    mens = [m["valor"] for m in r["mensal_plano"]]
    rec_m = [m["receita"] for m in rec["mensal"]]
    _grafico(s, L, TOPO, 5.9, BASE - TOPO, ABREV, [("Despesas 2027", mens, NAVY), ("Receitas calendarizadas", rec_m, LARANJA)], rotulos=False)
    _kpi_leve(s, 6.4, TOPO, 3.3, 1.2, mi(t["receita"]), "Receitas 2027", f"2026: {mi(t['receita_2026'])} ({var_pc(t['receita'], t['receita_2026'])})")
    _kpi_leve(s, 6.4, TOPO + 1.35, 3.3, 1.2, mi(t["despesa"]), "Despesas 2027", f"{t['sem_receita']} projetos sem receita associada")
    _kpi_leve(s, 6.4, TOPO + 2.7, 3.3, 1.2, mi(t["resultado"]), "Resultado 2027", "receitas menos despesas" + (f"; {mi(t['intercompany'])} de intercompany" if t["intercompany"] else ""))


def _slide_estrategia(prs, d, n):
    cob = d["cobertura"]
    despesa = [p for p in d["projetos"] if p["tipo"] == "despesa" and not p["contingenciado"]]
    s = _novo(prs, "Conexão com o Plano Operacional e o Contrato de Gestão", n)
    itens = cob["itens"]
    if not itens or cob.get("catalogo_vazio"):
        _txt(s, L, TOPO, 9.4, 1, "O catálogo do Plano Operacional ainda não foi carregado.", 14)
        return
    sem = {x["orcamento"] for x in cob["sem_vinculo"]}
    lig = sum(1 for p in despesa if p["orcamento"] not in sem)
    pl_vinc = cob["plano_total"] - cob["plano_sem_vinculo"]
    pct_vinc = pl_vinc / cob["plano_total"] * 100 if cob["plano_total"] else 0
    _kpi_leve(s, L, TOPO, 3.0, 0.95, f"{lig} de {len(despesa)}", "projetos vinculados", "")
    _kpi_leve(s, 3.45, TOPO, 3.0, 0.95, mi(pl_vinc), "do plano com vínculo", f"{pc(pct_vinc, 0)} do orçamento")
    _kpi_leve(s, 6.6, TOPO, 3.1, 0.95, mi(cob["plano_sem_vinculo"]), "ainda sem vínculo", _pl(len(cob["sem_vinculo"]), "projeto", "projetos"))
    y = TOPO + 1.1
    dirs = sorted((i for i in itens if i["tipo"] == "diretriz" and i["projetos"]), key=lambda i: -i["plano_projetos"])[:7]
    res = sorted((i for i in itens if i["tipo"] == "re" and i["projetos"]), key=lambda i: -i["plano_projetos"])[:7]
    if not dirs and not res:
        _txt(s, L, y + 0.3, 9.4, 1, "Nenhum projeto está vinculado ainda a diretrizes ou resultados estratégicos.", 14, False, MUDO)
        return
    cab = ["Item", "Proj.", "R$ mi"]
    _tabela(s, L, y, [3.4, 0.5, 0.7], ["Diretriz"] + cab[1:], [[corta(f"{i['codigo']}. {i['descricao']}", 50), str(i["projetos"]), _ms(i["plano_projetos"])] for i in dirs], tam=10, alt=0.42)
    _tabela(s, 5.1, y, [3.4, 0.5, 0.7], ["Resultado estratégico"] + cab[1:], [[corta(f"{i['codigo']} {i['descricao']}", 50), str(i["projetos"]), _ms(i["plano_projetos"])] for i in res], tam=10, alt=0.42)
    _txt(s, L, BASE - 0.22, R_ - L, 0.25, "Um projeto pode atender a mais de um item; por isso os valores não se somam.", 9.5, False, MUDO, italico=True)


def _slide_atencao(prs, d, n):
    cob, P, sit = d["cobertura"], d["projetos"], d["situacao"]
    ger = [g for g in d["gerencias"] if g["nivel"] == "gerencia"]
    pend = [(o, v) for o, v in sit.items() if v["pendencias"]]
    ros_esr = [i for i in cob["itens"] if i["tipo"] == "po" and "ESR" in (i["responsavel"] or "").split()]
    ros_esr_sem = [i for i in ros_esr if not i["projetos"]]
    vazios = [p for p in P if p["tipo"] == "despesa" and not p["contingenciado"] and abs(p["total_2027"]) < 0.005]
    cont = [p for p in P if p["contingenciado"]]
    s = _novo(prs, "Pontos de atenção", n)
    w, h = 4.6, 1.85
    cartoes = [
        ("Vínculo estratégico", _pl(len(cob["sem_vinculo"]), "projeto sem vínculo", "projetos sem vínculo"), f"somam {mi(cob['plano_sem_vinculo'])} do plano de 2027." if cob["sem_vinculo"] else "todos os projetos estão vinculados."),
        ("Resultados Operacionais da ESR", f"{len(ros_esr_sem)} de {len(ros_esr)} sem projeto" if ros_esr else "sem RO da ESR no catálogo",
         "ainda não têm orçamento ligado a eles." if ros_esr_sem else "todos têm projeto vinculado."),
        ("Preenchimento do planejamento", f"{sum(1 for g in ger if g.get('concluido'))} de {_pl(len(ger), 'gerência concluiu', 'gerências concluíram')}", f"{_pl(sum(v['pendencias'] for _, v in pend), 'pendência aberta', 'pendências abertas')} em {_pl(len(pend), 'projeto', 'projetos')}."),
        ("Situação dos projetos", _pl(len(cont), "contingenciado", "contingenciados"), f"{_pl(len(vazios), 'projeto de despesa', 'projetos de despesa')} sem valor em 2027."),
    ]
    for i, (tit, grande, pequeno) in enumerate(cartoes):
        x, y = L + (i % 2) * (w + 0.2), TOPO + (i // 2) * (h + 0.2)
        _cartao(s, x, y, w, h, tit)
        _txt(s, x + 0.25, y + 0.6, w - 0.4, 0.55, grande, 20, True, LARANJA if i != 3 else NAVY, ancora=MSO_ANCHOR.MIDDLE)
        _txt(s, x + 0.25, y + 1.2, w - 0.4, 0.5, pequeno, 12, False, TEXTO)


def _encerramento(prs) -> None:
    s = prs.slides[6]
    _texto(s, "Text 5", "Diretoria Adjunta da ESR")
    _texto(s, "Text 6", "Planejamento anual 2027")


# ---------------------------------------------------------------- montagem

def _remover(prs, indices: list[int]) -> None:
    lista = prs.slides._sldIdLst
    for i in sorted(indices, reverse=True):
        sid = lista[i]
        prs.part.drop_rel(sid.rId)
        lista.remove(sid)


def gerar(c: sqlite3.Connection, u: dict) -> bytes:
    d = relatorio.coletar(c, u)
    agora = datetime.now()
    prs = Presentation(str(TEMPLATE))
    _capa(prs, agora)
    _encerramento(prs)
    n = 2
    for f in (_slide_resumo, _slide_origem, _slide_finalidade, _slide_matriz, _slide_grupos, _slide_gerencias, _slide_projetos, _slide_mudam, _slide_receitas, _slide_estrategia, _slide_atencao):
        f(prs, d, n)
        n += 1
    lista = prs.slides._sldIdLst
    fim = lista[6]                       # o slide de encerramento do template volta para o final
    lista.remove(fim)
    lista.append(fim)
    _remover(prs, [1, 2, 3, 4, 5])       # agenda, seção, citação e números do template: modelos que não são usados
    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()
