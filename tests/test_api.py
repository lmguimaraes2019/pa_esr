import pytest
from fastapi.testclient import TestClient

from app import config, db
from conftest import ADMIN_SENHA, F_TEMPLATE, precisa_dados

pytestmark = precisa_dados


@pytest.fixture()
def client(env, monkeypatch):
    monkeypatch.setattr(config, "TEMPLATE_PATH", F_TEMPLATE)
    from app.main import app
    with TestClient(app, base_url="http://testserver") as c:
        yield c


def entrar(client, login="leandro", senha=ADMIN_SENHA):
    r = client.post("/api/login", json={"login": login, "senha": senha})
    return r


def gestor_liberado(client, login="luciana", senha="NovaSenha2027x"):
    r = client.post("/api/usuarios/%d/reset-senha" % _uid(login))
    temp = r.json()["senha_temporaria"]
    client.post("/api/logout")
    assert entrar(client, login, temp).json()["trocar_senha"] is True
    assert client.get("/api/projetos").status_code == 403          # bloqueado até trocar a senha
    assert client.post("/api/me/senha", json={"atual": temp, "nova": senha}).status_code == 200
    return client


def _uid(login):
    with db.tx() as c:
        return c.execute("SELECT id FROM users WHERE login=?", (login,)).fetchone()[0]


def test_exige_login(client):
    assert client.get("/api/projetos").status_code == 401
    assert entrar(client, senha="errada").status_code == 401


def test_bloqueio_por_tentativas(client):
    for _ in range(5):
        entrar(client, senha="x")
    assert entrar(client).status_code == 429


def test_admin_ve_tudo_e_resumo_bate(client):
    assert entrar(client).status_code == 200
    ps = client.get("/api/projetos").json()
    assert len(ps) == 18
    r = client.get("/api/resumo").json()
    assert r["total_plano"] == pytest.approx(22_016_487.22, abs=1.0)
    assert r["total_base"] == pytest.approx(r["total_plano"], abs=0.01)
    assert {p["orcamento"] for p in ps if p["pendencias"]} == {"7044"}


def test_gestor_so_ve_seus_projetos_e_edita_com_auditoria(client):
    entrar(client)
    todos = client.get("/api/projetos").json()
    gestor_liberado(client)
    meus = client.get("/api/projetos").json()
    assert 0 < len(meus) < len(todos)
    assert {p["gerente"] for p in meus} == {meus[0]["gerente"]}
    alheio = next(p for p in todos if p["orcamento"] not in {m["orcamento"] for m in meus})
    assert client.get(f"/api/projetos/{alheio['orcamento']}").status_code == 404
    assert client.post("/api/export/preflight").status_code in (404, 405)
    assert client.get("/api/export/preflight").status_code == 403
    assert client.get("/api/usuarios").status_code == 403

    det = client.get(f"/api/projetos/{meus[0]['orcamento']}").json()
    ln = det["linhas"][0]
    meses = [1000.0] + [0.0] * 11
    r = client.put(f"/api/linhas/{ln['id']}", json={"meses": meses})
    assert r.status_code == 200 and r.json()["total"] == 1000 and r.json()["editada"]
    assert r.json()["ref"]["total"] == ln["ref"]["total"]          # 2026 permanece como referência
    assert client.put(f"/api/linhas/{ln['id']}", json={"meses": [-1] + [0] * 11}).status_code == 422
    assert client.put(f"/api/linhas/{ln['id']}", json={"conta_codigo": "000"}).status_code == 422
    assert client.delete(f"/api/linhas/{ln['id']}").status_code == 200
    client.post("/api/logout")
    entrar(client)
    acoes = client.get("/api/auditoria").json()
    assert [a["usuario"] for a in acoes if a["acao"] in ("editou linha", "excluiu linha")] == ["luciana", "luciana"]


def test_nova_linha_e_validacoes(client):
    entrar(client)
    contas = client.get("/api/contas").json()
    assert len(contas) == 130
    body = {"edt": "1", "tarefa": "01", "conta_codigo": contas[0]["codigo"], "meses": [10] * 12}
    r = client.post("/api/projetos/6839/linhas", json=body)
    assert r.status_code == 201 and r.json()["ref"] is None and r.json()["total"] == 120
    assert client.post("/api/projetos/6839/linhas", json={**body, "meses": [1] * 11}).status_code == 422
    assert client.post("/api/projetos/9999/linhas", json=body).status_code == 404


def test_premissas_simulacao_e_aplicacao_preservam_editadas(client):
    entrar(client)
    base = client.get("/api/resumo").json()["total_plano"]
    ln = client.get("/api/projetos/6839").json()["linhas"][0]
    client.put(f"/api/linhas/{ln['id']}", json={"obs": "ajuste manual"})
    assert client.put("/api/premissas", json={"reajuste_pessoal": 5, "reajuste_geral": 3, "dolar": 5.8}).status_code == 200
    sim = client.post("/api/premissas/aplicar", json={}).json()
    assert sim["simulacao"] and sim["total_depois"] > sim["total_antes"]
    assert client.get("/api/resumo").json()["total_plano"] == pytest.approx(base)   # simular não grava
    ok = client.post("/api/premissas/aplicar", json={"simular": False}).json()
    assert ok["linhas_editadas_preservadas"] == 1
    assert client.get("/api/resumo").json()["total_plano"] > base
    assert client.put("/api/premissas", json={"reajuste_pessoal": 500, "reajuste_geral": 0, "dolar": 5}).status_code == 422


def test_exportacao_bloqueada_ate_preencher_numero(client):
    entrar(client)
    pre = client.get("/api/export/preflight").json()
    assert pre["bloqueado"]
    assert client.get("/api/export/xlsx").status_code == 409
    assert client.patch("/api/projetos/7044", json={"n_projeto": "abc"}).status_code == 422
    assert client.patch("/api/projetos/7044", json={"n_projeto": "2999"}).status_code == 200
    r = client.get("/api/export/xlsx")
    assert r.status_code == 200 and r.content[:2] == b"PK"
    assert "Planejamento_Anual_2027_ESR_" in r.headers["content-disposition"]


def test_usuarios_admin_e_csrf(client):
    entrar(client)
    r = client.post("/api/usuarios", json={"login": "novo.gestor", "nome": "Novo Gestor", "perfil": "gestor", "gerente": "X"})
    assert r.status_code == 201 and len(r.json()["senha_temporaria"]) >= 10
    assert client.post("/api/usuarios", json={"login": "novo.gestor", "nome": "Outro", "perfil": "admin"}).status_code == 409
    me = client.get("/api/me").json()
    assert client.patch(f"/api/usuarios/{me['id']}", json={"ativo": False}).status_code == 400
    r = client.post("/api/logout", headers={"origin": "https://malicioso.example"})
    assert r.status_code == 403


def test_editar_acessos_do_usuario(client):
    entrar(client)
    dados = client.get("/api/usuarios").json()
    g1, g2 = dados["gerentes"][0], dados["gerentes"][1]
    r = client.post("/api/usuarios", json={"login": "ed.teste", "nome": "Ed Teste", "perfil": "gestor", "gerentes": [g1]})
    assert r.status_code == 201 and r.json()["gerentes"] == [g1]
    uid = r.json()["id"]
    r = client.patch(f"/api/usuarios/{uid}", json={"gerentes": [g1, g2], "projetos": [dados["projetos"][0]["orcamento"]], "nome": "Ed Novo"})
    assert r.status_code == 200 and r.json()["gerentes"] == sorted([g1, g2]) and r.json()["nome"] == "Ed Novo"
    assert client.patch(f"/api/usuarios/{uid}", json={"gerentes": [], "projetos": []}).status_code == 422
    assert client.patch(f"/api/usuarios/{uid}", json={"gerentes": [g2]}).json()["gerentes"] == [g2]


def test_restaurar_linha_e_importar_execucao(client):
    entrar(client)
    p = client.get("/api/projetos").json()[0]["orcamento"]
    d = client.get(f"/api/projetos/{p}").json()
    l = next(x for x in d["linhas"] if x["fonte"] != "viagens" and x["base_id"])
    assert client.delete(f"/api/linhas/{l['id']}").status_code == 200
    d2 = client.get(f"/api/projetos/{p}").json()
    rem = [x for x in d2["passado"] if x["removida"]]
    assert any(x["id"] == l["base_id"] for x in rem)
    assert client.post(f"/api/linhas/{l['base_id']}/restaurar").status_code == 201
    assert client.post(f"/api/linhas/{l['base_id']}/restaurar").status_code == 409
    from conftest import F_PROTHEUS
    with open(F_PROTHEUS, "rb") as f:
        r = client.post("/api/execucao/importar?simular=true", files={"arquivo": ("p.xlsx", f)})
    assert r.status_code == 200 and r.json()["simulacao"] and r.json()["linhas"] > 0
    with open(F_PROTHEUS, "rb") as f:
        r2 = client.post("/api/execucao/importar?simular=false", files={"arquivo": ("p.xlsx", f)})
    assert r2.status_code == 200
    assert r2.json()["realizado_depois"] == r.json()["realizado_depois"] == r.json()["realizado_antes"]
    assert client.post("/api/execucao/importar", files={"arquivo": ("x.xlsx", b"nao e excel")}).status_code == 422
