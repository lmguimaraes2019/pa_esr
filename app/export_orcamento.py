"""Planilha do orçamento 2027 para o PMO e a diretoria: sumário das ações, uma aba por projeto vivo e abas de viagens,
headcount, eventos e equipamentos de TIC. Os totais e o saldo são fórmulas, para a planilha poder ser manuseada."""
from __future__ import annotations

import io
import re
import sqlite3
from datetime import datetime

from pathlib import Path

from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.worksheet.hyperlink import Hyperlink
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter as L
from openpyxl.worksheet.properties import PageSetupProperties
from openpyxl.worksheet.worksheet import Worksheet

from . import api, api_eventos, api_exposicao, api_headcount, api_viagens, config, equipamentos
from .db import MESES, NOMES_MESES

AZUL, LARANJA, CINZA = "0B2E59", "E87722", "5B6573"
F_TIT = Font(name="Calibri", size=16, bold=True, color=AZUL)
F_CAB = Font(name="Calibri", bold=True, color="FFFFFF")
F_NEG = Font(name="Calibri", bold=True)
F_NOTA = Font(name="Calibri", italic=True, color=CINZA, size=10)
F_EXT = Font(name="Calibri", color=CINZA)
P_CAB = PatternFill("solid", fgColor=AZUL)
P_SUB = PatternFill("solid", fgColor="DCE6F2")
P_EXT = PatternFill("solid", fgColor="ECEFF2")
P_CONT = PatternFill("solid", fgColor="FFE9C7")
P_INFO = PatternFill("solid", fgColor="FFF8DC")
P_TOT = PatternFill("solid", fgColor="F2F2F2")
P_26 = PatternFill("solid", fgColor="6B7280")
P_27 = PatternFill("solid", fgColor=LARANJA)
FINO = Side(style="thin", color="D0D5DD")
BORDA = Border(top=FINO, bottom=FINO, left=FINO, right=FINO)
MOEDA = '#,##0.00;[Red]-#,##0.00;"-"'
FINALIDADES = {"caixa": "Fluxo de caixa", "headcount": "Headcount", "sustentacao": "Sustentação", "investimento": "Investimento",
               "crescimento": "Crescimento ou projeto", "capacitacao": "Capacitação e eventos", "gestao": "Gestão da área"}
TIPOS_VIAGEM = {"nac": "Nacional", "int": "Internacional"}
MES = [m[:3].capitalize() for m in NOMES_MESES]


def _cab(ws: Worksheet, linha: int, titulos: list[str], fills: dict[int, PatternFill] | None = None) -> None:
    for j, t in enumerate(titulos, 1):
        c = ws.cell(row=linha, column=j, value=t)
        c.font, c.fill, c.border = F_CAB, (fills or {}).get(j, P_CAB), BORDA
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[linha].height = 32


def _larguras(ws: Worksheet, larguras: list[float]) -> None:
    for j, w in enumerate(larguras, 1):
        ws.column_dimensions[L(j)].width = w


def _titulo(ws: Worksheet, texto: str, sub: str = "") -> None:
    ws["A1"] = texto
    ws["A1"].font = F_TIT
    if sub:
        ws["A2"] = sub
        ws["A2"].font = F_NOTA
    ws.sheet_view.showGridLines = False


def _linha(ws: Worksheet, r: int, valores: list, moeda: set[int] = frozenset(), centro: set[int] = frozenset(), quebra: set[int] = frozenset(),
           fonte: Font | None = None, fill: PatternFill | None = None) -> None:
    for j, v in enumerate(valores, 1):
        c = ws.cell(row=r, column=j, value=v)
        c.border = BORDA
        if j in moeda:
            c.number_format = MOEDA
        c.alignment = Alignment(horizontal="center" if j in centro else None, vertical="top", wrap_text=j in quebra)
        if fonte:
            c.font = fonte
        if fill:
            c.fill = fill


def _total(ws: Worksheet, r: int, rotulo_col: int, cols: list[int], ini: int, fim: int, rotulo: str = "Total") -> None:
    ws.cell(row=r, column=rotulo_col, value=rotulo)
    for j in range(1, max(cols) + 1):
        c = ws.cell(row=r, column=j)
        c.font, c.fill, c.border = F_NEG, P_TOT, BORDA
    for j in cols:
        c = ws.cell(row=r, column=j, value=f"=SUBTOTAL(109,{L(j)}{ini}:{L(j)}{fim})")
        c.number_format = MOEDA


def _nome_aba(base: str, usados: set[str]) -> str:
    n = re.sub(r"[\[\]\*\?/\\:]", "-", base)[:31] or "Projeto"
    k, orig = 2, n
    while n.lower() in usados:
        n = f"{orig[:28]}-{k}"; k += 1
    usados.add(n.lower())
    return n


LOGO = Path(__file__).parent / "assets" / "logo_esr.png"
LINHAS_LOGO = 2


def _logo(ws: Worksheet) -> None:
    """Abre duas linhas no topo da aba, com o logo da ESR. O conteúdo desce junto: fórmulas, mesclagens, filtro, painel congelado e links."""
    n = LINHAS_LOGO
    maxr, maxc = ws.max_row, ws.max_column
    mescladas = [(m.min_row, m.min_col, m.max_row, m.max_col) for m in list(ws.merged_cells.ranges)]
    for m in list(ws.merged_cells.ranges):
        ws.unmerge_cells(str(m))
    alturas = {r: d.height for r, d in ws.row_dimensions.items() if d.height}
    ws.move_range(f"A1:{L(maxc)}{maxr}", rows=n, translate=True)
    for a, b, c2, d in mescladas:
        ws.merge_cells(start_row=a + n, start_column=b, end_row=c2 + n, end_column=d)
    for r in list(ws.row_dimensions.keys()):
        ws.row_dimensions[r].height = None
    for r, h in alturas.items():
        ws.row_dimensions[r + n].height = h
    if ws.freeze_panes:
        col = re.match(r"[A-Z]+", ws.freeze_panes).group()
        ws.freeze_panes = f"{col}{int(ws.freeze_panes[len(col):]) + n}"
    if ws.auto_filter.ref:
        ws.auto_filter.ref = re.sub(r"([A-Z]+)(\d+)", lambda m: f"{m.group(1)}{int(m.group(2)) + n}", ws.auto_filter.ref)
    for r in range(1, n + 1):
        ws.row_dimensions[r].height = 24
    img = XLImage(str(LOGO))
    img.height = 54
    img.width = round(54 * 1414 / 570)
    ws.add_image(img, "A1")


def _admin_contexto(u: dict, c: sqlite3.Connection) -> tuple[list[dict], set[str]]:
    ps = api.projetos(u, c)
    return [p for p in ps if p["tipo"] != "receita"], api.proprios(c, u, extintos=True)


def _informativos(u: dict, c: sqlite3.Connection) -> list[dict]:
    """Projetos fora da contabilidade (lançados pela DSS): aparecem só como informação, sem somar nos totais."""
    return [p for p in api.listar_projetos(u, c, incluir_fora=True) if p["fora_contabilidade"] and p["tipo"] != "receita"]


def gerar(u: dict, c: sqlite3.Connection) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Sumário"
    usados = {"sumário"}
    ps, _ = _admin_contexto(u, c)
    ordem_ger = lambda g: (0 if g == "Diretoria Adjunta" else 2 if g.startswith("Sem") else 1, g)      # noqa: E731
    ps.sort(key=lambda p: (ordem_ger(p["gerencia"]), p["origem"], p["extinto"], p["descricao"]))
    info = _informativos(u, c)
    vivos = [p for p in ps if not p["extinto"]] + [p for p in info if not p["extinto"]]
    abas = {p["orcamento"]: _nome_aba(p["orcamento"], usados) for p in vivos}
    gerado = datetime.now().strftime("%d/%m/%Y %H:%M")

    _sumario(ws, ps, abas, gerado, info)
    _aba_viagens(wb.create_sheet("Viagens"), u, c)
    _aba_headcount(wb.create_sheet("Headcount"), u, c)
    _aba_eventos(wb.create_sheet("Eventos"), u, c)
    _aba_equipamentos(wb.create_sheet("Equipamentos TIC"), u, c)
    _aba_receitas(wb.create_sheet("Receitas"), ps, c)
    _aba_exposicao(wb.create_sheet("Exposição cambial"), u, c)
    for p in vivos:
        _aba_projeto(wb.create_sheet(abas[p["orcamento"]]), p, c)
    ws.sheet_properties.tabColor = AZUL
    for nome, cor in (("Viagens", LARANJA), ("Headcount", LARANJA), ("Eventos", LARANJA), ("Equipamentos TIC", LARANJA), ("Receitas", "2F9E6F"),
                      ("Exposição cambial", "2F9E6F")):
        wb[nome].sheet_properties.tabColor = cor
    for w in wb.worksheets:      # logo da ESR, impressão em paisagem e uma página de largura
        _logo(w)
        if w is ws:      # links do sumário para a aba de cada projeto, feitos depois que o conteúdo desceu
            for linha in ws.iter_rows(min_row=1, max_col=1):
                cel = linha[0]
                if cel.value in abas:
                    cel.hyperlink = Hyperlink(ref=cel.coordinate, location=f"'{abas[cel.value]}'!A1", display=str(cel.value))
                    cel.font = Font(name="Calibri", color="0563C1", underline="single")
        w.page_setup.orientation = "landscape"
        w.page_setup.fitToWidth = 1
        w.page_setup.fitToHeight = 0
        w.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------- sumário

SUM_COLS = ["Orçamento", "Nº do projeto", "Projeto", "Gerência", "Gerente", "Situação", "Tipo de projeto", "Origem de recursos", "Fonte de financiamento",
            "Previsto 2026", "Empenhado 2026", "Executado 2026", "Saldo 2026", "Previsão de execução 31/12/2026", "% previsto de execução",
            "Previsto 2027", "Δ 2027 vs 2026", "Status"]
P_PREV = PatternFill("solid", fgColor="FCE9D2")      # previsão do gestor para o fim de 2026
PCT = '0%;[Red]-0%;"-"'


def _prev_pct(r: int) -> str:
    return f'=IF(OR(N{r}="",J{r}=0),"",N{r}/J{r})'


def _sumario(ws: Worksheet, ps: list[dict], abas: dict[str, str], gerado: str, info: list[dict] = ()) -> None:
    _titulo(ws, "Orçamento ESR 2027: sumário das ações", f"Gerado em {gerado}. Executado = realizado de 2026 (o empenhado é informativo e não entra no saldo). "
            "Saldo 2026 = previsto menos executado. Previsão de execução = valor que o gestor informou que o projeto terá executado até 31/12/2026; % previsto = previsão ÷ previsto 2026 "
            "(vazio quando o gestor ainda não informou). Valores em R$. Use os filtros para fatiar por gerência, origem ou tipo.")
    ini = 5
    _cab(ws, ini - 1, SUM_COLS, {10: P_26, 11: P_26, 12: P_26, 13: P_26, 14: P_PREV, 15: P_PREV, 16: P_27, 17: P_27})
    ws.freeze_panes = ws.cell(row=ini, column=4)
    moeda = {10, 11, 12, 13, 14, 16, 17}
    r = ini
    for p in ps:
        ext = p["extinto"]
        status = "Extinto" if ext else "Contingenciado" if p["contingenciado"] else "Ativo"
        prev27 = 0 if ext else p["total_2027"]
        _linha(ws, r, [p["orcamento"] if not p["novo"] else p["orcamento"], p["n_projeto"], p["descricao"], p["gerencia"], p["gerente"],
                       "Novo" if p["novo"] else "Existente", FINALIDADES.get(p["finalidade"], p["finalidade"]), p["origem"], p["financiamento"] or "",
                       p["total_2026"], p["empenhado_2026"], p["realizado_2026"], f"=J{r}-L{r}", p["previsao_2026"], _prev_pct(r), prev27, f"=P{r}-J{r}", status],
               moeda=moeda, centro={1, 2, 6, 18}, quebra={3, 5}, fonte=F_EXT if ext else None,
               fill=P_EXT if ext else P_CONT if p["contingenciado"] else None)
        ws.cell(row=r, column=15).number_format = PCT
        r += 1
    fim = r - 1
    _total(ws, r, 3, [10, 11, 12, 13, 14, 16, 17], ini, fim, "Total (conforme filtro)")
    cc = ws.cell(row=r, column=15, value=f'=IFERROR(SUBTOTAL(109,N{ini}:N{fim})/SUMIF(N{ini}:N{fim},"<>",J{ini}:J{fim}),"")')
    cc.number_format = PCT
    ws.cell(row=r + 1, column=3, value="O % do total compara a previsão com o previsto 2026 apenas dos projetos que já informaram a previsão.").font = F_NOTA
    ws.auto_filter.ref = f"A{ini - 1}:{L(len(SUM_COLS))}{fim}"
    if info:      # projeto lançado pela DSS: só informação, fora dos totais, dos filtros e dos resumos
        r += 3
        ws.cell(row=r, column=3, value="Informativo: projeto lançado pela DSS (não soma nos totais nem nos resumos)").font = Font(name="Calibri", size=12, bold=True, color="7A4A00")
        for p in info:
            r += 1
            _linha(ws, r, [p["orcamento"], p["n_projeto"], p["descricao"], p["gerencia"], p["gerente"],
                           "Novo" if p["novo"] else "Existente", FINALIDADES.get(p["finalidade"], p["finalidade"]), p["origem"], p["financiamento"] or "",
                           p["total_2026"], p["empenhado_2026"], p["realizado_2026"], p["total_2026"] - p["realizado_2026"], p["previsao_2026"], _prev_pct(r),
                           0 if p["extinto"] else p["total_2027"], (0 if p["extinto"] else p["total_2027"]) - p["total_2026"], "Informativo (DSS)"],
                   moeda=moeda, centro={1, 2, 6, 18}, quebra={3, 5}, fonte=Font(name="Calibri", italic=True, color="7A4A00"), fill=P_INFO)
            ws.cell(row=r, column=15).number_format = PCT
        fim_info = r
        r += 1
    else:
        fim_info = fim
    _larguras(ws, [12, 12, 48, 20, 22, 11, 22, 16, 22, 15, 15, 15, 15, 17, 13, 15, 15, 14])
    # resumos por origem e por gerência (fórmulas sobre a tabela acima, sem contar extintos no 2027)
    r += 3
    for titulo, col, chaves in (("Resumo por origem de recursos", "H", sorted({p["origem"] for p in ps})),
                                ("Resumo por gerência", "D", sorted({p["gerencia"] for p in ps}, key=ordem_ger_g))):
        ws.cell(row=r, column=3, value=titulo).font = Font(name="Calibri", size=13, bold=True, color=AZUL)
        r += 1
        _cab(ws, r, ["", "", titulo.split(" por ")[1].capitalize(), "", "", "", "", "", "", "Previsto 2026", "Empenhado 2026", "Executado 2026", "Saldo 2026",
                     "Previsão de execução 31/12/2026", "% previsto de execução", "Previsto 2027", "Δ 2027 vs 2026"],
             {10: P_26, 11: P_26, 12: P_26, 13: P_26, 14: P_PREV, 15: P_PREV, 16: P_27, 17: P_27})
        ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=9)
        a = r + 1
        for k in chaves:
            r += 1
            ws.cell(row=r, column=3, value=k)
            ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=9)
            for j in range(3, 18):
                ws.cell(row=r, column=j).border = BORDA
            for j, cl in ((10, "J"), (11, "K"), (12, "L"), (14, "N"), (16, "P")):
                cc = ws.cell(row=r, column=j, value=f"=SUMIF(${col}${ini}:${col}${fim},$C{r},{cl}${ini}:{cl}${fim})")
                cc.number_format = MOEDA
            ws.cell(row=r, column=13, value=f"=J{r}-L{r}").number_format = MOEDA
            ws.cell(row=r, column=15, value=f'=IFERROR(N{r}/SUMIFS($J${ini}:$J${fim},${col}${ini}:${col}${fim},$C{r},$N${ini}:$N${fim},"<>"),"")').number_format = PCT
            ws.cell(row=r, column=17, value=f"=P{r}-J{r}").number_format = MOEDA
        r += 1
        ws.cell(row=r, column=3, value="Total")
        for j in range(3, 18):
            cc = ws.cell(row=r, column=j); cc.font, cc.fill, cc.border = F_NEG, P_TOT, BORDA
        ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=9)
        for j in (10, 11, 12, 13, 14, 16, 17):
            ws.cell(row=r, column=j, value=f"=SUM({L(j)}{a}:{L(j)}{r - 1})").number_format = MOEDA
        ws.cell(row=r, column=15, value=f'=IFERROR(N{r}/SUMIF($N${ini}:$N${fim},"<>",$J${ini}:$J${fim}),"")').number_format = PCT
        r += 3


def ordem_ger_g(g: str):
    return (0 if g == "Diretoria Adjunta" else 2 if g.startswith("Sem") else 1, g)


# ---------------------------------------------------------------- uma aba por projeto

def _aba_projeto(ws: Worksheet, p: dict, c: sqlite3.Connection) -> None:
    _titulo(ws, f"{p['orcamento']} | {p['descricao']}")
    info = [("Gerente", p["gerente"]), ("Gerência", p["gerencia"]), ("Situação", "Novo" if p["novo"] else "Existente"),
            ("Tipo de projeto", FINALIDADES.get(p["finalidade"], p["finalidade"])), ("Origem de recursos", p["origem"]),
            ("Fonte de financiamento", p["financiamento"] or ""), ("Nº do projeto (PCO)", p["n_projeto"] or "a lançar"),
            ("Status", "Contingenciado (não liberado para execução)" if p["contingenciado"] else "Ativo")]
    if p["replicado_de"]:
        info.append(("Replicado de", p["replicado_de"]))
    for i, (k, v) in enumerate(info):
        a = ws.cell(row=3 + i, column=1, value=k); a.font = F_NEG
        ws.cell(row=3 + i, column=2, value=v)
    # bloco de totais ao lado das informações
    ws.cell(row=3, column=7, value="2026").font = F_NEG
    ws.cell(row=3, column=9, value="2027").font = F_NEG
    quadro = [("Previsto", p["total_2026"], p["total_2027"]), ("Empenhado", p["empenhado_2026"], None), ("Executado", p["realizado_2026"], None)]
    for i, (k, v26, v27) in enumerate(quadro):
        ws.cell(row=4 + i, column=6, value=k).font = F_NEG
        ws.cell(row=4 + i, column=7, value=v26).number_format = MOEDA
        if v27 is not None:
            ws.cell(row=4 + i, column=9, value=v27).number_format = MOEDA
    ws.cell(row=7, column=6, value="Saldo").font = F_NEG
    ws.cell(row=7, column=7, value="=G4-G6").number_format = MOEDA
    ws.cell(row=7, column=9, value="=I4-G4").number_format = MOEDA
    ws.cell(row=7, column=8, value="Δ vs 2026").font = F_NOTA
    ws.cell(row=8, column=6, value="Previsão 31/12").font = F_NEG
    pc = ws.cell(row=8, column=7, value=p["previsao_2026"])
    pc.number_format = MOEDA
    pc.fill = P_PREV
    ws.cell(row=9, column=6, value="% previsto").font = F_NEG
    pp = ws.cell(row=9, column=7, value='=IF(OR(G8="",G4=0),"",G8/G4)')
    pp.number_format = PCT
    pp.fill = P_PREV
    ws.cell(row=8, column=8, value="valor que o gestor informou" if p["previsao_2026"] is not None else "não informada").font = F_NOTA
    ini = 3 + max(len(info), 5) + 2
    cols = ["EDT", "Tarefa", "Conta", "Descrição da conta"] + MES + ["Total 2027", "Previsto 2026", "Executado 2026", "Empenhado 2026"]
    _cab(ws, ini, cols, {17: P_27, 18: P_26, 19: P_26, 20: P_26})
    cmes = ", ".join(f"l.{m}" for m in MESES)
    rows = c.execute(
        f"SELECT l.edt, l.tarefa, l.conta_codigo, k.descricao AS conta, {cmes}, "
        f"COALESCE((SELECT {'+'.join('b.' + m for m in MESES)} FROM linhas b WHERE b.id = l.base_id), 0) AS ref, "
        "COALESCE((SELECT SUM(e.realizado) FROM execucao e WHERE e.orcamento=l.orcamento AND e.edt=l.edt AND e.tarefa=l.tarefa AND e.conta_codigo=l.conta_codigo),0) AS real, "
        "COALESCE((SELECT SUM(e.empenhado) FROM execucao e WHERE e.orcamento=l.orcamento AND e.edt=l.edt AND e.tarefa=l.tarefa AND e.conta_codigo=l.conta_codigo),0) AS emp "
        "FROM linhas l JOIN contas k ON k.codigo=l.conta_codigo WHERE l.ciclo=? AND l.orcamento=? ORDER BY l.edt, l.tarefa, l.conta_codigo",
        (config.CICLO_PLANO, p["orcamento"])).fetchall()
    r = ini
    for x in rows:
        r += 1
        _linha(ws, r, [x["edt"], x["tarefa"], x["conta_codigo"], x["conta"], *[x[m] for m in MESES],
                       f"=SUM(E{r}:P{r})", x["ref"], x["real"], x["emp"]], moeda=set(range(5, 21)), centro={3}, quebra={2, 4})
    if rows:
        _total(ws, r + 1, 4, list(range(5, 21)), ini + 1, r)
    else:
        ws.cell(row=ini + 1, column=1, value="Sem linhas de orçamento lançadas para 2027.").font = F_NOTA
    # entregas e KPIs
    ent = c.execute("SELECT descricao, mes, kpi, meta FROM entregas WHERE orcamento=? ORDER BY ordem, id", (p["orcamento"],)).fetchall()
    if ent:
        r = r + 4
        ws.cell(row=r, column=1, value="Entregas e KPIs").font = Font(name="Calibri", size=13, bold=True, color=AZUL)
        _cab(ws, r + 1, ["Mês", "Entrega", "", "KPI", "Meta"])
        for e in ent:
            r += 1
            _linha(ws, r + 1, [MES[e["mes"] - 1] if 1 <= e["mes"] <= 12 else "", e["descricao"], "", e["kpi"], e["meta"]], quebra={2, 4, 5}, centro={1})
        r += 1
    _larguras(ws, [26, 36, 11, 36] + [12] * 12 + [15, 15, 15, 15])
    ws.freeze_panes = ws.cell(row=ini + 1, column=5)
    ws.sheet_properties.tabColor = "9AA5B4" if p["contingenciado"] else AZUL


# ---------------------------------------------------------------- viagens

def _aba_viagens(ws: Worksheet, u: dict, c: sqlite3.Connection) -> None:
    d = api_viagens.listar(u, c)
    _titulo(ws, "Viagens previstas em 2027", "Uma linha por conjunto de viagens. Custo calculado pela tabela de tarifas vigente. Inclui as viagens vindas de eventos.")
    cols = ["Orçamento", "Projeto", "Tipo", "Mês", "Origem", "Destino", "Nº de viagens", "Dias", "Pernoites", "Objetivo", "Área", "Passagem (c/ bagagem)",
            "Hospedagem", "Ajuda de custo", "Aux. transporte", "Seguro", "Total 2027", "Referência 2026", "Evento", "Lançado por", "Gerências"]
    _cab(ws, 4, cols, {17: P_27, 18: P_26})
    r = 4
    for v in sorted(d["viagens"], key=lambda x: (x["orcamento"] or "", x["mes"], x["id"])):
        r += 1
        k = v["custo"]
        _linha(ws, r, [v["orcamento"] or "sem projeto", v["projeto"], TIPOS_VIAGEM.get(v["tipo"], v["tipo"]), MES[v["mes"] - 1] if 1 <= v["mes"] <= 12 else "", v["origem"], v["destino"],
                       v["n_viagens"], v["dias"], v["pernoites"] if v["pernoites"] is not None else k["pernoites"], v["objetivo"], v["area"],
                       k["passagem"], k["hospedagem"], k["ajuda_custo"], k["aux_transporte"], k["seguro"], f"=SUM(L{r}:P{r})", v["ref_2026"] or 0,
                       "Sim" if v["evento_id"] else "", v["atualizado_por"], ", ".join(v["ger_filtro"])], moeda={12, 13, 14, 15, 16, 17, 18}, centro={1, 3, 4, 7, 8, 9, 19}, quebra={2, 10, 21})
    _fecha(ws, r, [7, 12, 13, 14, 15, 16, 17, 18], 5, "Nenhuma viagem lançada.")
    _larguras(ws, [12, 36, 13, 7, 22, 22, 9, 7, 10, 34, 16, 15, 14, 14, 14, 12, 15, 15, 8, 16, 26])
    ws.freeze_panes = "C5"


def _fecha(ws: Worksheet, r: int, cols: list[int], ini: int, vazio: str) -> None:
    if r >= ini:
        _total(ws, r + 1, 2, cols, ini, r)
        ws.auto_filter.ref = f"A{ini - 1}:{L(ws.max_column)}{r}"
    else:
        ws.cell(row=ini, column=1, value=vazio).font = F_NOTA


# ---------------------------------------------------------------- headcount

def _aba_headcount(ws: Worksheet, u: dict, c: sqlite3.Connection) -> None:
    d = api_headcount.listar(u, c)
    _titulo(ws, "Headcount previsto em 2027", "Custo = (salário da tabela + encargos, benefícios e provisões) x meses de 2027 x quantidade, mais equipamentos (pontual, no mês de início).")
    cols = ["Orçamento", "Projeto", "Gerência", "Função", "Cargo", "Trajetória", "Nível", "Posição", "Quantidade", "Mês de início", "Meses em 2027", "Salário (tabela)",
            "Custo mensal por posição", "Custo de pessoal 2027", "Equipamentos 2027", "Total 2027", "Projeto que custeia os equipamentos", "Justificativa", "Lançado por"]
    _cab(ws, 4, cols, {16: P_27})
    r = 4
    for h in sorted(d["itens"], key=lambda x: (x["gerencia"], x["orcamento"], x["id"])):
        r += 1
        pessoal_27 = round(h["custo"]["mensal"] * h["meses_2027"] * h["quantidade"], 2)
        _linha(ws, r, [h["orcamento"], h["projeto"], h["gerencia"], h["funcao"], h["cargo"], h["trajetoria"], h["nivel"], h["posicao"], h["quantidade"],
                       MES[h["mes_inicio"] - 1], h["meses_2027"], h["salario_tabela"], h["custo"]["mensal"], pessoal_27, h["equipamentos"]["total"], f"=N{r}+O{r}",
                       (f"{h['equip_orcamento']} | {h['projeto_equip']}" if h["equip_orcamento"] != h["orcamento"] and h["equipamentos"]["total"] else ""),
                       h["justificativa"], h["atualizado_por"]], moeda={12, 13, 14, 15, 16}, centro={1, 9, 10, 11}, quebra={2, 4, 5, 17, 18})
    _fecha(ws, r, [9, 14, 15, 16], 5, "Nenhuma posição lançada.")
    _larguras(ws, [12, 34, 18, 26, 22, 14, 10, 9, 11, 10, 10, 14, 14, 16, 15, 15, 32, 40, 16])
    ws.freeze_panes = "C5"


# ---------------------------------------------------------------- eventos

def _aba_eventos(ws: Worksheet, u: dict, c: sqlite3.Connection) -> None:
    d = api_eventos.listar(u, c)
    _titulo(ws, "Eventos previstos em 2027", "Total = inscrição + viagem das pessoas (passagem, hospedagem, ajuda de custo, auxílio e seguro). Evento RNP é organizado pela RNP.")
    cols = ["Orçamento", "Projeto", "Evento", "Local", "Âmbito", "Evento RNP", "Mês", "Nº de pessoas", "Dias", "Participantes", "Inscrição (R$)", "Passagem",
            "Hospedagem", "Ajuda de custo", "Aux. transporte", "Seguro", "Total 2027", "Situação", "Justificativa", "Site", "Lançado por", "Gerências que participam"]
    _cab(ws, 4, cols, {17: P_27})
    r = 4
    for e in sorted(d["itens"], key=lambda x: (x["orcamento"] or "", x["mes"], x["id"])):
        r += 1
        v = e["viagem"]
        _linha(ws, r, [e["orcamento"], e["projeto"], e["nome"], e["local"], TIPOS_VIAGEM.get(e["tipo"], e["tipo"]), "Sim" if e["rnp"] else "Não",
                       MES[e["mes"] - 1] if 1 <= e["mes"] <= 12 else "", e["n_pessoas"], e["dias"], ", ".join(e["pessoas"]), e["inscricao_total"],
                       v["passagem"], v["hospedagem"], v["ajuda_custo"], v["aux_transporte"], v["seguro"], f"=SUM(K{r}:P{r})",
                       "Completo" if e["completo"] else "Falta: " + ", ".join(e["faltando"]), e["justificativa"], e["site"], e["atualizado_por"], ", ".join(e["ger_filtro"])],
               moeda={11, 12, 13, 14, 15, 16, 17}, centro={1, 5, 6, 7, 8, 9}, quebra={2, 3, 4, 10, 18, 19, 22})
    _fecha(ws, r, [8, 11, 12, 13, 14, 15, 16, 17], 5, "Nenhum evento lançado.")
    _larguras(ws, [12, 32, 32, 18, 13, 10, 7, 9, 7, 30, 14, 14, 14, 14, 14, 12, 15, 30, 40, 24, 16, 28])
    ws.freeze_panes = "D5"


# ---------------------------------------------------------------- equipamentos de TIC

def _aba_equipamentos(ws: Worksheet, u: dict, c: sqlite3.Connection) -> None:
    d = api_headcount.listar(u, c)
    _titulo(ws, "Equipamentos de TIC previstos em 2027",
            f"Equipamentos das novas posições de headcount, pelo catálogo de hardware homologado ({equipamentos.carregar()['atualizado_em']}). Custo pontual no mês de início da posição.")
    cols = ["Orçamento", "Projeto", "Gerência", "Função", "Mês de início", "Quantidade de posições", "Computador", "Valor unitário", "Monitor", "Valor unitário",
            "Periférico", "Valor unitário", "Custo por posição", "Total 2027", "Posição lançada em", "Lançado por"]
    _cab(ws, 4, cols, {14: P_27})
    r = 4
    for h in sorted(d["itens"], key=lambda x: (x["gerencia"], x["orcamento"], x["id"])):
        eq = h["equipamentos"]
        if not eq["unitario"]:
            continue
        r += 1
        nomes = eq["nomes"]
        cod = lambda t, n: f"{n} ({h[t]})" if h[t] else ""      # noqa: E731
        _linha(ws, r, [h["equip_orcamento"], h["projeto_equip"], h["gerencia"], h["funcao"], MES[h["mes_inicio"] - 1], h["quantidade"],
                       cod("computador", nomes.get("computador", "")), eq.get("computador", 0), cod("monitor", nomes.get("monitor", "")), eq.get("monitor", 0),
                       cod("periferico", nomes.get("periferico", "")), eq.get("periferico", 0), f"=H{r}+J{r}+L{r}", f"=M{r}*F{r}",
                       f"{h['orcamento']} | {h['projeto']}" if h["orcamento"] != h["equip_orcamento"] else "", h["atualizado_por"]],
               moeda={8, 10, 12, 13, 14}, centro={1, 5, 6}, quebra={2, 4, 7, 9, 11, 15})
    _fecha(ws, r, [6, 14], 5, "Nenhum equipamento previsto.")
    _larguras(ws, [12, 34, 18, 26, 10, 12, 42, 13, 28, 13, 24, 13, 14, 15, 30, 16])
    ws.freeze_panes = "C5"


# ---------------------------------------------------------------- receitas

def _aba_receitas(ws: Worksheet, ps: list[dict], c: sqlite3.Connection) -> None:
    _titulo(ws, "Receitas previstas em 2027", "Receitas lançadas nos projetos. A transferência intercompany é receita da ESR e custo da área que paga.")
    cols = ["Orçamento", "Projeto", "Origem", "Fonte da receita", "Descrição"] + MES + ["Total 2027"]
    _cab(ws, 4, cols, {18: P_27})
    ids = {p["orcamento"]: p for p in ps if not p["extinto"]}
    cmes = ", ".join(MESES)
    r = 4
    for x in c.execute(f"SELECT orcamento, fonte, descricao, {cmes} FROM receitas WHERE ciclo=? ORDER BY orcamento, id", (config.CICLO_PLANO,)):
        p = ids.get(x["orcamento"])
        if not p:
            continue
        r += 1
        _linha(ws, r, [x["orcamento"], p["descricao"], p["origem"], x["fonte"], x["descricao"], *[x[m] for m in MESES], f"=SUM(F{r}:Q{r})"],
               moeda=set(range(6, 19)), centro={1}, quebra={2, 4, 5})
    _fecha(ws, r, list(range(6, 19)), 5, "Nenhuma receita lançada.")
    _larguras(ws, [12, 36, 16, 26, 34] + [12] * 12 + [15])
    ws.freeze_panes = "C5"


# ---------------------------------------------------------------- exposição cambial

def _aba_exposicao(ws: Worksheet, u: dict, c: sqlite3.Connection) -> None:
    cam = api_exposicao._cambio(c)
    _titulo(ws, "Exposição ao dólar (e outras moedas) em 2027",
            f"Compras previstas em moeda estrangeira. Conversão em reais pelas premissas do plano: dólar R$ {cam['USD']:.4f}, euro R$ {cam['EUR']:.4f}, libra R$ {cam['GBP']:.4f}.")
    cols = ["Orçamento", "Projeto", "SC em andamento?", "Diretoria", "Gerência", "Ponto focal", "Tipo", "Processo (ADC ou SC)", "Descrição do produto ou serviço",
            "Fabricante / fornecedor", "Canal / distribuidor", "País de origem", "Trimestre", "Programa Conecta?", "Previsão de abertura de SC", "Moeda",
            "Valor em USD", "Valor em EUR", "Valor em GBP", "Equivalente em R$"]
    _cab(ws, 4, cols, {20: P_27})
    ids = sorted(api.proprios(c, u))
    marks = ",".join("?" for _ in ids) or "''"
    projetos = {r["orcamento"]: r for r in c.execute(f"SELECT orcamento, descricao, gerente, finalidade FROM projetos WHERE orcamento IN ({marks})", ids)}
    r = 4
    for x in c.execute(f"SELECT * FROM exposicao_cambial WHERE orcamento IN ({marks}) ORDER BY trimestre, orcamento, id", ids):
        r += 1
        m = x["moeda"]
        k = 3 + LINHAS_LOGO      # referências absolutas: a aba desce LINHAS_LOGO linhas depois
        eq_rs = f"=Q{r}*$B${k}+R{r}*$D${k}+S{r}*$F${k}"
        _linha(ws, r, [x["orcamento"], projetos[x["orcamento"]]["descricao"], x["sc_andamento"], x["diretoria"], x["gerencia"], x["ponto_focal"], x["tipo"], x["processo"],
                       x["descricao"], x["fabricante"], x["canal"], x["pais_origem"], api_exposicao.TRIMESTRES.get(x["trimestre"], ""), x["conecta"], x["previsao_sc"], m,
                       x["valor"] if m == "USD" else None, x["valor"] if m == "EUR" else None, x["valor"] if m == "GBP" else None,
                       eq_rs],
               moeda={17, 18, 19, 20}, centro={1, 3, 4, 5, 13, 14, 15, 16}, quebra={2, 6, 8, 9, 10, 11})
    ws["A3"], ws["B3"], ws["C3"], ws["D3"], ws["E3"], ws["F3"] = "Dólar (R$)", cam["USD"], "Euro (R$)", cam["EUR"], "Libra (R$)", cam["GBP"]
    for a in ("A3", "C3", "E3"):
        ws[a].font = F_NEG
    for b in ("B3", "D3", "F3"):
        ws[b].number_format = "0.0000"
        ws[b].alignment = Alignment(horizontal="left")
    _fecha(ws, r, [17, 18, 19, 20], 5, "Nenhuma compra em moeda estrangeira lançada.")
    _larguras(ws, [12, 34, 11, 10, 11, 20, 10, 22, 40, 22, 22, 14, 20, 11, 14, 8, 15, 15, 15, 17])
    ws.freeze_panes = "C5"
