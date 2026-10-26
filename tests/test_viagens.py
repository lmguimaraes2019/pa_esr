import pytest
from fastapi.testclient import TestClient

from app import config, db, viagens
from conftest import ADMIN_SENHA, F_TEMPLATE, F_VIAGENS, precisa_dados

pytestmark = [precisa_dados, pytest.mark.skipif(not F_VIAGENS.exists(), reason="planilha de viagens ausente")]

SOMA = "+".join(db.MESES)


def _total_plano(c, bagagem_vezes):
    tar = viagens.tarifas_map(c)
    tot = {"nac": 0.0, "int": 0.0}
    for v in c.execute("SELECT * FROM viagens WHERE ciclo=2026"):
        t = tar.get((v["tipo"], v["origem"], v["destino"]))
        tot[v["tipo"]] += viagens.calcular(v["tipo"], t, v["n_viagens"], v["dias"], v["pernoites"], bagagem_vezes)["total"]
    return tot


def test_calculadora_reproduz_a_planilha(env):
    with db.tx() as c:
        # contando a bagagem duas vezes, como o consolidado de 2026, os nacionais batem com a planilha e com o Protheus
        assert _total_plano(c, 2)["nac"] == pytest.approx(941_773.54, abs=0.01)
        assert _total_plano(c, 1)["nac"] == pytest.approx(941_773.54 - 35_520, abs=0.01)
        # a planilha ignorou "3 viagens" numa linha internacional; a calculadora multiplica (diferença de 23.496)
        assert _total_plano(c, 1)["int"] == pytest.approx(84_993 + 23_496, abs=0.01)


def test_carga_e_tarefas_padrao(env):
    with db.tx() as c:
        assert c.execute("SELECT COUNT(*) FROM viagem_tarifas").fetchone()[0] == 46
        assert c.execute("SELECT COUNT(*) FROM viagens WHERE ciclo=2026").fetchone()[0] == 109 - 0
        assert c.execute("SELECT COUNT(*) FROM viagens WHERE ciclo=2027 AND base_id IS NOT NULL").fetchone()[0] == 109
        # 6819 tem uma única tarefa de viagens; 6814 tem quatro e fica para o usuário escolher
        assert c.execute("SELECT DISTINCT tarefa FROM viagens WHERE ciclo=2027 AND orcamento='6819'").fetchone()[0] == "01.02-VIAGEM NACIONAL"
        assert c.execute("SELECT COUNT(*) FROM viagens WHERE ciclo=2027 AND orcamento='6814' AND tarefa IS NULL").fetchone()[0] == 5
        # as viagens internacionais não têm projeto na planilha
        assert c.execute("SELECT COUNT(*) FROM viagens WHERE ciclo=2027 AND tipo='int' AND orcamento IS NULL").fetchone()[0] == 6


def test_aplicar_bloqueia_com_pendencias(env):
    with db.tx() as c:
        r = viagens.aplicar_ao_orcamento(c, "teste", True)
    assert r["bloqueado"] and any("sem projeto ou tarefa" in e for e in r["erros"])


def _resolver_pendencias(c):
    """Atribui projeto e tarefa às viagens pendentes, como o usuário faria na tela."""
    c.execute("UPDATE viagens SET edt='01-UNIDADE BRASILIA', tarefa='01.05-VIAGENS' WHERE ciclo=2027 AND orcamento='6814'")
    c.execute("UPDATE viagens SET orcamento='6839', edt='03-PARTICIPACAO EM EVENTOS', tarefa='03.03-VIAGEM NACIONAL' "
              "WHERE ciclo=2027 AND orcamento IS NULL")


def test_aplicar_ao_orcamento(env):
    with db.tx() as c:
        c.execute("UPDATE premissas SET valor=2 WHERE chave='viagens_bagagem_vezes'")
        _resolver_pendencias(c)
        antes = c.execute(f"SELECT SUM({SOMA}) FROM linhas WHERE ciclo=2027 AND orcamento='6819'").fetchone()[0]
        sim = viagens.aplicar_ao_orcamento(c, "teste", True)
        assert not sim["bloqueado"], sim["erros"]
        assert c.execute(f"SELECT SUM({SOMA}) FROM linhas WHERE ciclo=2027 AND orcamento='6819'").fetchone()[0] == pytest.approx(antes)
        real = viagens.aplicar_ao_orcamento(c, "teste", False)
        depois = c.execute(f"SELECT SUM({SOMA}) FROM linhas WHERE ciclo=2027 AND orcamento='6819' AND fonte='viagens'").fetchone()[0]
    # com bagagem em dobro, o projeto 6819 volta ao valor aprovado em 2026 (R$ 290.903)
    assert depois == pytest.approx(290_903.0, abs=0.01)
    assert real["total_depois"] > real["total_antes"]       # entram as viagens internacionais e as de unidades
    with db.tx() as c:
        # reaplicar é idempotente
        r2 = viagens.aplicar_ao_orcamento(c, "teste", False)
        assert r2["total_antes"] == pytest.approx(r2["total_depois"], abs=0.01)
        # a referência de 2026 continua ligada nas linhas atualizadas
        assert c.execute("SELECT COUNT(*) FROM linhas WHERE ciclo=2027 AND fonte='viagens' AND base_id IS NOT NULL").fetchone()[0] >= 20


@pytest.fixture()
def client(env, monkeypatch):
    monkeypatch.setattr(config, "TEMPLATE_PATH", F_TEMPLATE)
    from app.main import app
    with TestClient(app, base_url="http://testserver") as c:
        assert c.post("/api/login", json={"login": "leandro", "senha": ADMIN_SENHA}).status_code == 200
        yield c


def test_api_lista_e_edita_viagem(client):
    d = client.get("/api/viagens").json()
    assert len(d["viagens"]) == 109 and d["totais"]["pendentes"] > 0
    assert d["totais"]["plano"] > 0 and d["opcoes"]["projetos"]
    v = next(x for x in d["viagens"] if x["orcamento"] == "6819")
    corpo = {k: v[k] for k in ("tipo", "mes", "origem", "destino", "n_viagens", "dias", "pernoites", "objetivo", "area",
                               "orcamento", "edt", "tarefa")}
    assert client.put(f"/api/viagens/{v['id']}", json={**corpo, "dias": 10}).status_code == 200
    assert client.put(f"/api/viagens/{v['id']}", json={**corpo, "destino": "Atlântida"}).status_code == 422
    assert client.put(f"/api/viagens/{v['id']}", json={**corpo, "edt": "x", "tarefa": "y"}).status_code == 422
    novo = client.post("/api/viagens", json={**corpo, "mes": 12})
    assert novo.status_code == 201
    assert client.delete(f"/api/viagens/{novo.json()['id']}").status_code == 200


def test_api_aplicar_trava_linhas_e_reajuste(client):
    assert client.post("/api/viagens/aplicar", json={"simular": True}).json()["bloqueado"]
    d = client.get("/api/viagens").json()
    for v in d["viagens"]:
        if not v["orcamento"] or not v["edt"]:
            corpo = {k: v[k] for k in ("tipo", "mes", "origem", "destino", "n_viagens", "dias", "pernoites", "objetivo", "area")}
            corpo |= {"orcamento": "6839", "edt": "03-PARTICIPACAO EM EVENTOS", "tarefa": "03.03-VIAGEM NACIONAL"}
            assert client.put(f"/api/viagens/{v['id']}", json=corpo).status_code == 200
    r = client.post("/api/viagens/aplicar", json={"simular": False}).json()
    assert not r["bloqueado"] and r["itens"]
    det = client.get("/api/projetos/6819").json()
    lv = next(l for l in det["linhas"] if l["fonte"] == "viagens")
    assert lv["status"] == "viagens"
    assert client.put(f"/api/linhas/{lv['id']}", json={"meses": [1] + [0] * 11}).status_code == 409
    assert client.delete(f"/api/linhas/{lv['id']}").status_code == 409
    assert client.put(f"/api/linhas/{lv['id']}", json={"obs": "ok"}).status_code == 200      # observação é livre
    rj = client.post("/api/viagens/tarifas/reajuste", json={"percentual": 10, "simular": False}).json()
    assert rj["tarifas_afetadas"] == 46
    t = client.get("/api/viagens/tarifas").json()[0]
    assert t["passagem"] == pytest.approx(round(t["ref_passagem"] * 1.1, 2))
    assert client.put("/api/premissas", json={"reajuste_pessoal": 0, "reajuste_geral": 0, "dolar": 5.5,
                                              "viagens_bagagem_vezes": 2}).status_code == 200


def test_detalhe_traz_visao_do_passado(client):
    d = client.get("/api/projetos/6819").json()
    assert d["passado"] and all("aprovado" in x and "executado" in x for x in d["passado"])
    assert sum(x["aprovado"] for x in d["passado"]) == pytest.approx(d["totais"]["base"])
    r = client.get("/api/resumo").json()
    assert r["total_executado"] > 0 and r["linhas_status"]["mantida"] > 200
    assert all("executado" in o for o in r["por_origem"])
