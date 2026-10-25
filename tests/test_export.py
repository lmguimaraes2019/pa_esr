import io
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
import zipfile

import openpyxl
import pytest

from app import config, db, export_xlsx
from conftest import F_TEMPLATE, precisa_dados

pytestmark = precisa_dados

TOTAL_2027 = 22_016_487.22     # base 2026 sem o IA para Todos (R$ 0,91 de reserva)


@pytest.fixture()
def resultado(env, monkeypatch):
    monkeypatch.setattr(config, "TEMPLATE_PATH", F_TEMPLATE)
    with db.tx() as c:
        c.execute("UPDATE projetos SET n_projeto='9999' WHERE orcamento='7044'")   # resolve a pendência
        return export_xlsx.preparar(c)


@pytest.fixture()
def arquivo(resultado):
    return export_xlsx.gerar(resultado.linhas)


def test_preflight_bloqueia_projeto_sem_numero(env, monkeypatch):
    monkeypatch.setattr(config, "TEMPLATE_PATH", F_TEMPLATE)
    with db.tx() as c:
        r = export_xlsx.preparar(c)
    assert r.bloqueado
    erros = [a for a in r.avisos if a.nivel == "erro"]
    assert [a.orcamento for a in erros] == ["7044"]
    assert any(a.orcamento == "7016" and a.nivel == "aviso" for a in r.avisos)


def test_preflight_liberado_com_numero(resultado):
    assert not resultado.bloqueado
    assert len(resultado.linhas) == 225


def test_zip_integro_e_so_a_aba_foi_alterada(arquivo):
    with zipfile.ZipFile(io.BytesIO(arquivo)) as novo, zipfile.ZipFile(F_TEMPLATE) as orig:
        assert novo.testzip() is None
        assert "xl/calcChain.xml" not in novo.namelist()
        mudaram = {"xl/worksheets/sheet1.xml", "xl/tables/table1.xml", "[Content_Types].xml",
                   "xl/_rels/workbook.xml.rels", "xl/workbook.xml"}
        for nome in orig.namelist():
            if nome == "xl/calcChain.xml" or nome in mudaram:
                continue
            assert novo.read(nome) == orig.read(nome), f"{nome} foi alterado e não devia"
        for nome in ("xl/metadata.xml", "xl/worksheets/sheet2.xml", "xl/worksheets/sheet3.xml",
                     "xl/queryTables/queryTable1.xml", "xl/connections.xml"):
            assert novo.read(nome) == orig.read(nome)
        for nome in novo.namelist():
            if nome.endswith(".xml") or nome.endswith(".rels"):
                ET.fromstring(novo.read(nome))     # XML bem formado em todas as partes


def test_tabela_validacoes_e_dimensao(arquivo):
    with zipfile.ZipFile(io.BytesIO(arquivo)) as z:
        sheet = z.read("xl/worksheets/sheet1.xml").decode()
        tabela = z.read("xl/tables/table1.xml").decode()
        wb = z.read("xl/workbook.xml").decode()
    ultima = 226
    assert f'<dimension ref="A1:W{ultima}"/>' in sheet
    assert tabela.count(f'ref="A1:W{ultima}"') == 2          # tabela e autoFilter
    for col in "HAEDI":
        assert f'sqref="{col}2:{col}{ultima}"' in sheet
    assert 'fullCalcOnLoad="1"' in wb
    assert "Grupo_de_Despesa" in sheet and "INDIRECT(SUBSTITUTE" in sheet     # validações preservadas


def test_valores_e_consistencia_com_a_lista_do_template(arquivo):
    wb = openpyxl.load_workbook(io.BytesIO(arquivo), data_only=True)
    ws = wb["Calendarização"]
    contas = {str(c): (d, g) for c, d, g in __import__("app.importers", fromlist=["x"]).load_contas_template(F_TEMPLATE)}
    soma = 0.0
    n = 0
    for r in ws.iter_rows(min_row=2, max_col=23, values_only=True):
        if r[0] is None:
            continue
        n += 1
        diretoria, nproj, desc, origem, gerente, edt, tarefa, grupo, conta_desc, conta = r[:10]
        meses = r[10:22]
        assert diretoria == "ESR" and nproj is not None
        assert str(conta) in contas and contas[str(conta)] == (conta_desc, grupo)   # a lista suspensa dependente aceitaria
        assert r[22] == pytest.approx(sum(meses), abs=0.005)
        soma += r[22]
    assert n == 225
    assert soma == pytest.approx(TOTAL_2027, abs=1.0)


def test_fatores_de_linha_preservados(arquivo):
    """Fórmulas de conta e total mantidas como no template (referência estruturada à Tabela2)."""
    with zipfile.ZipFile(io.BytesIO(arquivo)) as z:
        sheet = z.read("xl/worksheets/sheet1.xml").decode()
    assert sheet.count("_xlfn.XLOOKUP") == 225
    assert sheet.count("SUM(Tabela2[[#This Row],[janeiro]]:Tabela2[[#This Row],[dezembro]])") == 225


@pytest.mark.skipif(not shutil.which("soffice"), reason="LibreOffice ausente")
def test_abre_no_libreoffice(arquivo, tmp_path):
    f = tmp_path / "saida.xlsx"
    f.write_bytes(arquivo)
    r = subprocess.run(["soffice", "--headless", "--convert-to", "csv", "--outdir", str(tmp_path), str(f)],
                       capture_output=True, text=True, timeout=120)
    csv = tmp_path / "saida.csv"
    assert csv.exists(), r.stderr
    linhas = csv.read_text(encoding="utf-8").strip().splitlines()
    assert len(linhas) == 226          # cabeçalho + 225 linhas
