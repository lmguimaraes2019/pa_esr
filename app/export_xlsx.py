"""Exportação no Template Planejamento Anual 2027.

O template tem matrizes dinâmicas, consultas do Power Query e validações dependentes. Reabrir e salvar com uma
biblioteca de planilhas as quebraria, então este módulo edita apenas o XML da aba Calendarização, a definição da
Tabela2 e os sqref das validações. Todo o resto do arquivo segue byte a byte como veio do template.
"""
from __future__ import annotations

import io
import re
import sqlite3
import zipfile
from dataclasses import dataclass, field
from functools import lru_cache
from xml.sax.saxutils import escape

from . import config, importers
from .db import MESES

COLUNAS = list("ABCDEFGHIJKLMNOPQRSTUVW")      # A..W
LINHA_MODELO = 4                                 # linha do template que serve de modelo de estilo e fórmulas
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


@dataclass
class Aviso:
    nivel: str            # "erro" bloqueia a exportação, "aviso" apenas informa
    mensagem: str
    orcamento: str | None = None


@dataclass
class Resultado:
    linhas: list[dict] = field(default_factory=list)
    avisos: list[Aviso] = field(default_factory=list)

    @property
    def bloqueado(self) -> bool:
        return any(a.nivel == "erro" for a in self.avisos)


@lru_cache(maxsize=1)
def _listas_template() -> dict[str, list[str]]:
    return importers.load_listas_template(config.TEMPLATE_PATH)


def preparar(conn: sqlite3.Connection, ciclo: int = config.CICLO_PLANO) -> Resultado:
    """Lê as linhas do ciclo, valida contra as listas do template e devolve o que será exportado."""
    listas = _listas_template()
    res = Resultado()
    cols = ", ".join(f"l.{m}" for m in MESES)
    rows = conn.execute(
        f"SELECT l.id, l.orcamento, l.edt, l.tarefa, l.conta_codigo, {cols}, "
        "p.n_projeto, p.descricao, COALESCE(NULLIF(p.origem_2027, ''), p.origem) AS origem, p.gerente, p.diretoria, k.descricao AS conta_desc, k.grupo "
        "FROM linhas l JOIN projetos p USING (orcamento) JOIN contas k ON k.codigo = l.conta_codigo "
        "WHERE l.ciclo = ? AND p.tipo = 'despesa' ORDER BY l.orcamento, l.edt, l.tarefa, l.conta_codigo", (ciclo,)).fetchall()

    zeradas = 0
    pend_num: set[str] = set()
    com_linha: set[str] = set()
    for r in rows:
        meses = [float(r[m]) for m in MESES]
        if abs(sum(meses)) < 0.005:
            zeradas += 1
            continue
        com_linha.add(r["orcamento"])
        if any(v < 0 for v in meses):
            res.avisos.append(Aviso("aviso", f"Linha {r['tarefa']} / {r['conta_desc']} tem valor negativo.", r["orcamento"]))
        if not r["n_projeto"]:
            pend_num.add(r["orcamento"])
        res.linhas.append({
            "diretoria": r["diretoria"], "n_projeto": r["n_projeto"], "descricao": r["descricao"],
            "origem": r["origem"], "gerente": r["gerente"], "edt": r["edt"], "tarefa": r["tarefa"],
            "grupo": r["grupo"], "conta_desc": r["conta_desc"], "conta_cod": r["conta_codigo"], "meses": meses,
        })

    for o in sorted(pend_num):
        res.avisos.append(Aviso("erro", "Projeto com orçamento lançado e sem Nº do Projeto. Preencha antes de exportar.", o))
    for lin in res.linhas:
        if lin["gerente"] not in listas["gerentes"]:
            res.avisos.append(Aviso("erro", f"Gerente '{lin['gerente']}' não está na lista do template."))
            break
    for lin in res.linhas:
        if lin["origem"] not in listas["origens"]:
            res.avisos.append(Aviso("erro", f"Origem '{lin['origem']}' não está na lista do template."))
            break
    for lin in res.linhas:
        if lin["diretoria"] not in listas["diretorias"]:
            res.avisos.append(Aviso("erro", f"Diretoria '{lin['diretoria']}' não está na lista do template."))
            break
    for r in conn.execute("SELECT u.login, u.nome FROM users u WHERE u.ativo=1 AND u.perfil<>'admin' AND u.login NOT IN (SELECT login FROM conclusoes) "
                          "AND (EXISTS (SELECT 1 FROM user_projetos p WHERE p.user_id=u.id) OR EXISTS (SELECT 1 FROM user_gerentes g WHERE g.user_id=u.id))"):
        res.avisos.append(Aviso("aviso", f"{r['nome']} ainda não marcou o planejamento como concluído."))
    if zeradas:
        res.avisos.append(Aviso("aviso", f"{zeradas} linha(s) com total zero não serão exportadas."))
    todos = {r["orcamento"] for r in conn.execute("SELECT orcamento FROM projetos WHERE tipo='despesa'")}
    for r in conn.execute("SELECT orcamento, descricao FROM projetos WHERE tipo='receita'"):
        res.avisos.append(Aviso("aviso", "Orçamento de receita não vai no Template de despesas do PMO.", r["orcamento"]))
    for o in sorted(todos - com_linha):
        res.avisos.append(Aviso("aviso", "Projeto sem nenhuma linha com valor em 2027.", o))
    if not res.linhas:
        res.avisos.append(Aviso("erro", "Não há nenhuma linha com valor para exportar."))
    return res


# ---------------------------------------------------------------- geração do arquivo

def _s(v: str) -> str:
    return escape(_CTRL.sub("", str(v)))


def _num(v: float) -> str:
    return repr(round(float(v), 2)).rstrip("0").rstrip(".") if v else "0"


def _estilos_e_formulas(sheet_xml: str) -> tuple[dict[str, str], str, str, str]:
    """Estilo de cada coluna, fórmula da conta, fórmula do total e abertura da tag <row> na linha modelo."""
    m = re.search(rf'<row r="{LINHA_MODELO}"[^>]*>.*?</row>', sheet_xml, flags=re.S)
    if not m:
        raise ValueError("Linha modelo não encontrada no template")
    row = m.group(0)
    estilos = {col: s for col, s in re.findall(rf'<c r="([A-Z]+){LINHA_MODELO}" s="(\d+)"', row)}
    f_conta = re.search(rf'<c r="J{LINHA_MODELO}"[^>]*><f>(.*?)</f>', row, flags=re.S).group(1)
    f_total = re.search(rf'<c r="W{LINHA_MODELO}"[^>]*><f>(.*?)</f>', row, flags=re.S).group(1)
    abre = re.match(r"<row [^>]*>", row).group(0)
    return estilos, f_conta, f_total, abre


def _linha_xml(n: int, lin: dict, estilos: dict[str, str], f_conta: str, f_total: str, abre: str) -> str:
    def txt(col: str, valor: str) -> str:
        if valor == "":
            return f'<c r="{col}{n}" s="{estilos[col]}"/>'
        return f'<c r="{col}{n}" s="{estilos[col]}" t="inlineStr"><is><t xml:space="preserve">{_s(valor)}</t></is></c>'

    abre_n = re.sub(r'r="\d+"', f'r="{n}"', abre, count=1)
    cel = [txt("A", lin["diretoria"])]
    if lin["n_projeto"].isdigit():
        cel.append(f'<c r="B{n}" s="{estilos["B"]}"><v>{int(lin["n_projeto"])}</v></c>')
    else:
        cel.append(txt("B", lin["n_projeto"]))
    cel += [txt("C", lin["descricao"]), txt("D", lin["origem"]), txt("E", lin["gerente"]),
            txt("F", lin["edt"]), txt("G", lin["tarefa"]), txt("H", lin["grupo"]), txt("I", lin["conta_desc"])]
    cel.append(f'<c r="J{n}" s="{estilos["J"]}" t="str"><f>{f_conta}</f><v>{_s(lin["conta_cod"])}</v></c>')
    for i, v in enumerate(lin["meses"]):
        col = COLUNAS[10 + i]
        cel.append(f'<c r="{col}{n}" s="{estilos[col]}"><v>{_num(v)}</v></c>')
    cel.append(f'<c r="W{n}" s="{estilos["W"]}"><f>{f_total}</f><v>{_num(sum(lin["meses"]))}</v></c>')
    return abre_n + "".join(cel) + "</row>"


def gerar(linhas: list[dict]) -> bytes:
    """Devolve o conteúdo do .xlsx: o template original com a aba Calendarização preenchida."""
    if not linhas:
        raise ValueError("Nenhuma linha para exportar")
    with zipfile.ZipFile(config.TEMPLATE_PATH) as zin:
        info = zin.infolist()
        arquivos = {i.filename: zin.read(i.filename) for i in info}

    sheet = arquivos["xl/worksheets/sheet1.xml"].decode("utf-8")
    estilos, f_conta, f_total, abre = _estilos_e_formulas(sheet)

    ini, fim = sheet.index("<sheetData>") + len("<sheetData>"), sheet.index("</sheetData>")
    linha1 = re.search(r'<row r="1".*?</row>', sheet[ini:fim], flags=re.S).group(0)
    novas = [_linha_xml(i + 2, lin, estilos, f_conta, f_total, abre) for i, lin in enumerate(linhas)]
    ultima = len(linhas) + 1
    sheet = sheet[:ini] + linha1 + "".join(novas) + sheet[fim:]
    sheet = re.sub(r'<dimension ref="[^"]*"/>', f'<dimension ref="A1:W{ultima}"/>', sheet, count=1)
    sheet = re.sub(r'sqref="([A-Z])2:\1\d+"', lambda m: f'sqref="{m.group(1)}2:{m.group(1)}{ultima}"', sheet)
    arquivos["xl/worksheets/sheet1.xml"] = sheet.encode("utf-8")

    tabela = arquivos["xl/tables/table1.xml"].decode("utf-8")
    if 'name="Tabela2"' not in tabela:
        raise ValueError("Tabela2 não está em table1.xml: estrutura do template mudou")
    tabela = re.sub(r'ref="A1:W\d+"', f'ref="A1:W{ultima}"', tabela)
    arquivos["xl/tables/table1.xml"] = tabela.encode("utf-8")

    # a cadeia de cálculo ficaria desatualizada; o Excel a reconstrói sozinho
    arquivos.pop("xl/calcChain.xml", None)
    ct = arquivos["[Content_Types].xml"].decode("utf-8")
    arquivos["[Content_Types].xml"] = re.sub(r'<Override PartName="/xl/calcChain.xml"[^>]*/>', "", ct).encode("utf-8")
    rels = arquivos["xl/_rels/workbook.xml.rels"].decode("utf-8")
    arquivos["xl/_rels/workbook.xml.rels"] = re.sub(r'<Relationship [^>]*calcChain[^>]*/>', "", rels).encode("utf-8")
    wb = arquivos["xl/workbook.xml"].decode("utf-8")
    arquivos["xl/workbook.xml"] = re.sub(r'<calcPr ([^>]*?)/>', r'<calcPr \1 fullCalcOnLoad="1"/>', wb, count=1).encode("utf-8")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zout:
        for i in info:
            if i.filename in arquivos:
                zout.writestr(i.filename, arquivos[i.filename])
    return buf.getvalue()
