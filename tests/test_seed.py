import stat

import pytest

from app import db
from conftest import precisa_dados

pytestmark = precisa_dados

APROVADO_2026 = {"Associacao": 14_401_350.80, "Fomento": 6_707_915.30, "RA": 907_221.00}


def _um(env, sql, *a):
    with db.tx() as c:
        return c.execute(sql, a).fetchone()[0]


def test_totais_por_origem_batem_com_aprovado(env):
    with db.tx() as c:
        rows = c.execute("SELECT p.origem, SUM(" + "+".join(db.MESES) + ") t FROM linhas l "
                         "JOIN projetos p USING (orcamento) WHERE l.ciclo=2026 GROUP BY p.origem").fetchall()
    por_origem = {r["origem"]: r["t"] for r in rows}
    assert set(por_origem) == set(APROVADO_2026)       # FNDCT (IA para Todos) fica de fora
    for origem, esperado in APROVADO_2026.items():
        assert por_origem[origem] == pytest.approx(esperado, abs=0.5), origem


def test_total_geral_2026(env):
    total = _um(env, "SELECT SUM(" + "+".join(db.MESES) + ") FROM linhas WHERE ciclo=2026")
    assert total == pytest.approx(22_016_487.10, abs=1.0)


def test_2027_nasce_como_copia_do_2026(env):
    with db.tx() as c:
        n26 = c.execute("SELECT COUNT(*) FROM linhas WHERE ciclo=2026").fetchone()[0]
        n27 = c.execute("SELECT COUNT(*) FROM linhas WHERE ciclo=2027").fetchone()[0]
        sem_base = c.execute("SELECT COUNT(*) FROM linhas WHERE ciclo=2027 AND base_id IS NULL").fetchone()[0]
        difer = c.execute("SELECT COUNT(*) FROM linhas a JOIN linhas b ON a.base_id=b.id "
                          "WHERE " + " OR ".join(f"a.{m}<>b.{m}" for m in db.MESES)).fetchone()[0]
    assert n26 == n27 == 225        # 316 linhas do Orçado menos 91 do IA para Todos (7016), fora da base
    assert sem_base == 0 and difer == 0


def test_toda_linha_tem_conta_valida_do_template(env):
    with db.tx() as c:
        orfas = c.execute("SELECT COUNT(*) FROM linhas l LEFT JOIN contas k ON k.codigo=l.conta_codigo "
                          "WHERE k.codigo IS NULL").fetchone()[0]
        n_contas = c.execute("SELECT COUNT(*) FROM contas").fetchone()[0]
        grupo = c.execute("SELECT grupo FROM contas WHERE codigo='51050207'").fetchone()[0]
    assert orfas == 0 and n_contas == 130
    assert grupo == "Impostos e Taxas"      # o grupo vem do template, não do Protheus


def test_projetos_e_pendencias(env):
    with db.tx() as c:
        projs = {r["orcamento"]: dict(r) for r in c.execute("SELECT * FROM projetos")}
    assert len(projs) == 18
    pend = {o for o, p in projs.items() if not p["n_projeto"]}
    assert pend == {"7016", "7044"}
    assert projs["6839"]["n_projeto"] == "1044"
    assert projs["6839"]["descricao"] == "DSS-ESR-ASSOCIACAO-GROWTH"
    assert projs["6839"]["original_2026"] == pytest.approx(3_087_521.40, abs=0.01)
    assert _um(env, "SELECT COUNT(*) FROM linhas WHERE orcamento='7016'") == 0


def test_usuarios_e_arquivo_de_senhas(env):
    with db.tx() as c:
        us = {r["login"]: dict(r) for r in c.execute("SELECT * FROM users")}
    assert set(us) == {"leandro", "luciana", "olavo", "renato", "yve"}
    assert us["leandro"]["perfil"] == "admin"
    assert all(u["perfil"] == "gestor" and u["trocar_senha"] == 1 for k, u in us.items() if k != "leandro")
    assert all(u["senha_hash"].startswith("$2") for u in us.values())
    modo = stat.S_IMODE((env / "senhas_iniciais.txt").stat().st_mode)
    assert modo == 0o600


def test_execucao_importada(env):
    with db.tx() as c:
        r = c.execute("SELECT SUM(realizado) r, SUM(empenhado) e FROM execucao").fetchone()
    assert r["r"] == pytest.approx(11_397_273.28, abs=1.0)
    assert r["e"] == pytest.approx(3_120_285.67, abs=1.0)
