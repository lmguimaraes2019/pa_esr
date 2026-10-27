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
    r = client.post("/api/usuarios", json={"login": "novo.gestor", "nome": "Novo Gestor", "perfil": "gestor", "gerente": "X", "gerencia": "G", "cargo": "gerente"})
    assert r.status_code == 201 and len(r.json()["senha_temporaria"]) >= 10
    assert client.post("/api/usuarios", json={"login": "novo.gestor", "nome": "Outro", "perfil": "admin", "gerencia": "G", "cargo": "pmo"}).status_code == 409
    me = client.get("/api/me").json()
    assert client.patch(f"/api/usuarios/{me['id']}", json={"ativo": False}).status_code == 400
    r = client.post("/api/logout", headers={"origin": "https://malicioso.example"})
    assert r.status_code == 403


def test_editar_acessos_do_usuario(client):
    entrar(client)
    dados = client.get("/api/usuarios").json()
    g1, g2 = dados["gerentes"][0], dados["gerentes"][1]
    r = client.post("/api/usuarios", json={"login": "ed.teste", "nome": "Ed Teste", "perfil": "gestor", "gerentes": [g1], "gerencia": "G", "cargo": "gerente"})
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


def test_receitas(client):
    entrar(client)
    r = client.get("/api/receitas").json()
    assert r["totais"]["receita_2026"] == 6000000 and r["linhas"][0]["fonte"] == "Growth"
    orc = r["projetos"][0]["orcamento"]
    c = client.post("/api/receitas", json={"orcamento": orc, "fonte": "Parcerias", "meses": [1000] * 12})
    assert c.status_code == 201 and c.json()["total"] == 12000
    rid = c.json()["id"]
    assert client.put(f"/api/receitas/{rid}", json={"meses": [2000] + [0] * 11}).json()["total"] == 2000
    assert client.post("/api/receitas", json={"orcamento": orc, "fonte": "X", "meses": [1] * 11}).status_code == 422
    assert client.post("/api/receitas", json={"orcamento": "9999", "fonte": "X", "meses": [1] * 12}).status_code == 404
    t = client.get("/api/receitas").json()["totais"]
    assert t["receita"] == 6000000 + 2000
    assert client.delete(f"/api/receitas/{rid}").status_code == 200


def test_excluir_e_restaurar_grupo(client):
    entrar(client)
    p = client.get("/api/projetos").json()[0]["orcamento"]
    d = client.get(f"/api/projetos/{p}").json()
    l = next(x for x in d["linhas"] if x["fonte"] != "viagens")
    n = sum(1 for x in d["linhas"] if x["edt"] == l["edt"])
    r = client.delete(f"/api/projetos/{p}/linhas", params={"edt": l["edt"]})
    assert r.status_code == 200 and r.json()["linhas"] == n
    assert client.delete(f"/api/projetos/{p}/linhas", params={"edt": l["edt"]}).status_code == 404
    assert client.post(f"/api/projetos/{p}/linhas/restaurar", params={"edt": l["edt"]}).json()["linhas"] == n
    assert client.post(f"/api/projetos/{p}/linhas/restaurar", params={"edt": l["edt"]}).json()["linhas"] == 0


def test_orcamento_novo_e_mudanca_de_origem(client):
    entrar(client)
    L = client.get("/api/listas").json()
    assert "Associacao" in L["origens"] and L["gerentes"]
    r = client.post("/api/projetos", json={"descricao": "Projeto de teste novo", "origem": "Associacao", "gerente": L["gerentes"][0]})
    assert r.status_code == 201
    o = r.json()["orcamento"]
    assert o.startswith("N27-")
    assert client.post("/api/projetos", json={"descricao": "Outro", "origem": "Inexistente", "gerente": L["gerentes"][0]}).status_code == 422
    lista = {p["orcamento"]: p for p in client.get("/api/projetos").json()}
    assert lista[o]["novo"] is True and lista[o]["total_2027"] == 0
    d = client.get(f"/api/projetos/{o}").json()
    assert d["projeto"]["novo"] is True and d["linhas"] == []
    assert client.post(f"/api/projetos/{o}/linhas", json={"edt": "01", "tarefa": "Teste", "conta_codigo": client.get("/api/contas").json()[0]["codigo"], "meses": [10] * 12}).status_code == 201
    assert client.patch(f"/api/projetos/{o}", json={"origem": "Fomento"}).status_code == 200
    assert client.get(f"/api/projetos/{o}").json()["projeto"]["origem"] == "Fomento"
    assert client.patch(f"/api/projetos/{o}", json={"origem": "Xis"}).status_code == 422
    seg = client.get("/api/export/preflight").json()
    assert seg["bloqueado"] and any(o in (a["orcamento"] or "") for a in seg["avisos"])


def test_origem_2027_nao_altera_2026(client):
    entrar(client)
    ps = client.get("/api/projetos").json()
    p = next(x for x in ps if not x["novo"] and x["origem"] == "Associacao" and x["total_2026"] > 0)
    o = p["orcamento"]
    antes = {x["nome"]: x for x in client.get("/api/resumo").json()["por_origem"]}
    assert client.patch(f"/api/projetos/{o}", json={"origem": "Fomento"}).status_code == 200
    d = client.get(f"/api/projetos/{o}").json()["projeto"]
    assert d["origem"] == "Fomento" and d["origem_2026"] == "Associacao"
    depois = {x["nome"]: x for x in client.get("/api/resumo").json()["por_origem"]}
    assert depois["Associacao"]["base"] == antes["Associacao"]["base"]          # 2026 intacto
    assert depois["Fomento"]["base"] == antes["Fomento"]["base"]
    assert round(depois["Associacao"]["plano"], 2) == round(antes["Associacao"]["plano"] - p["total_2027"], 2)
    assert round(depois["Fomento"]["plano"], 2) == round(antes["Fomento"]["plano"] + p["total_2027"], 2)
    lista = {x["orcamento"]: x for x in client.get("/api/projetos").json()}
    assert lista[o]["origem"] == "Fomento" and lista[o]["origem_2026"] == "Associacao"
    client.patch(f"/api/projetos/{o}", json={"origem": "Associacao"})


def test_headcount_formulas_da_planilha(client):
    entrar(client)
    h = client.get("/api/headcount").json()
    assert len(h["tabela"]) == 42 and h["itens"] == []
    orc = h["projetos"][0]["orcamento"]
    tf = h["tarefas"][orc]["lista"][0]
    # faixa PLENO GRUPO 01 da Gestão do Negócio: 6418,58 a 9627,88; posição 0 = início da faixa
    r = client.post("/api/headcount", json={"orcamento": orc, "funcao": "Analista", "cargo": "Analista Pleno", "trajetoria": "GESTAO DO NEGOCIO",
                                            "nivel": "PLENO", "grupo": "GRUPO 01", "posicao": 0, "mes_inicio": 7, "quantidade": 2,
                                            "justificativa": "Demanda nova", "edt": tf["edt"], "tarefa": tf["tarefa"]})
    assert r.status_code == 201
    d = r.json()
    assert d["custo"]["salario"] == 6418.58 and d["meses_2027"] == 6 and d["faltando"] == []
    j = 6418.58
    esperado = (j * 1.269044 + j * 0.09) + (22 * 35 + 299.77 + 1208.5158888888889 + j * 0.005811 + 100) \
        + ((j / 30 * 10) / 12 + (j / 12 + (j / 30 * 10) / 12) / 3 + j / 12)
    assert abs(d["custo"]["mensal"] - esperado) < 0.02 and abs(d["anualizado"] - esperado * 12 * 2) < 0.1
    assert abs(d["custo_2027"] - esperado * 6 * 2) < 0.1
    # o orçamento do projeto acompanha: linhas bloqueadas com o mesmo total
    p = client.get(f"/api/projetos/{orc}").json()
    bloq = [x for x in p["linhas"] if x["fonte"] == "headcount"]
    assert bloq and abs(sum(x["total"] for x in bloq) - d["custo_2027"]) < 0.5
    assert client.put(f"/api/linhas/{bloq[0]['id']}", json={"meses": [1] * 12}).status_code == 409
    assert client.delete(f"/api/linhas/{bloq[0]['id']}").status_code == 409
    assert client.post("/api/headcount", json={"orcamento": orc, "trajetoria": "X", "nivel": "Y", "grupo": "Z"}).status_code == 422
    assert client.delete(f"/api/headcount/{d['id']}").status_code == 200
    assert not [x for x in client.get(f"/api/projetos/{orc}").json()["linhas"] if x["fonte"] == "headcount"]


def test_eventos_calculam_viagem(client):
    entrar(client)
    e = client.get("/api/eventos").json()
    assert e["tarifas"]
    orc = e["projetos"][0]["orcamento"]
    tf = e["tarefas"][orc]["lista"][0]
    t = next(x for x in e["tarifas"] if x["tipo"] == "nac")
    r = client.post("/api/eventos", json={"orcamento": orc, "nome": "Congresso X", "local": "Recife", "tipo": "nac", "mes": 5, "n_pessoas": 2,
                                          "dias": 3, "inscricao": 1000, "origem": t["origem"], "destino": t["destino"], "pessoas": ["Ana"],
                                          "justificativa": "", "edt": tf["edt"], "tarefa": tf["tarefa"]})
    assert r.status_code == 201
    d = r.json()
    assert d["inscricao_total"] == 2000 and d["viagem"]["total"] > 0 and d["total"] == round(2000 + d["viagem"]["total"], 2)
    assert "justificativa" in d["faltando"] and any("pessoas" in x for x in d["faltando"]) and not d["completo"]
    r2 = client.put(f"/api/eventos/{d['id']}", json={**{k: d[k] for k in ("orcamento", "nome", "local", "tipo", "mes", "n_pessoas", "dias", "inscricao", "moeda", "origem", "destino", "edt", "tarefa")},
                                                  "pessoas": ["Ana", "Bia"], "justificativa": "Divulgação"})
    assert r2.json()["completo"] is True
    p = client.get(f"/api/projetos/{orc}").json()
    bloq = [x for x in p["linhas"] if x["fonte"] == "eventos"]
    assert abs(sum(x["total"] for x in bloq) - d["total"]) < 0.05 and any(x["conta_codigo"] == "51040104" for x in bloq)
    assert client.get("/api/eventos").json()["totais"]["eventos"] == 1
    assert client.delete(f"/api/eventos/{d['id']}").status_code == 200


def test_planejamento_resumo_e_conclusao(client):
    entrar(client)
    h = client.get("/api/headcount").json()
    orc = h["projetos"][0]["orcamento"]
    client.post("/api/headcount", json={"orcamento": orc, "trajetoria": "GESTAO DO NEGOCIO", "nivel": "PLENO", "grupo": "GRUPO 01"})
    pl = client.get("/api/planejamento").json()
    assert pl["etapas"]["headcount"]["pendentes"] == 1 and pl["pendencias"] >= 1 and pl["concluido"] is None
    assert isinstance(pl["gerencias"], list)
    pr = client.get(f"/api/planejamento/projeto/{orc}").json()
    assert pr["headcount"]["n"] == 1 and pr["pendencias"] >= 1
    assert client.post("/api/planejamento/concluir", json={"concluido": True}).status_code == 409
    for x in client.get("/api/headcount").json()["itens"]:
        client.delete(f"/api/headcount/{x['id']}")
    for v in client.get("/api/viagens").json()["viagens"]:      # a carga de viagens traz itens ainda sem tarefa
        if not v["orcamento"] or not v["edt"] or not v["tem_tarifa"]:
            client.delete(f"/api/viagens/{v['id']}")
    assert client.get("/api/planejamento").json()["pendencias"] == 0
    assert client.post("/api/planejamento/concluir", json={"concluido": True, "obs": "ok"}).status_code == 200
    assert client.get("/api/planejamento").json()["concluido"]["obs"] == "ok"
    assert client.post("/api/planejamento/concluir", json={"concluido": False}).status_code == 200
    assert client.get("/api/planejamento").json()["concluido"] is None


def test_receita_intercompany(client):
    entrar(client)
    r = client.get("/api/receitas").json()
    orc, origem, gestor = r["projetos"][0]["orcamento"], r["origens"][0], r["gerentes"][0]
    base = r["totais"]["receita"]
    corpo = {"orcamento": orc, "tipo": "intercompany", "ano": 2027, "cliente": "Projeto Alfa", "origem_cliente": origem, "gestor_cliente": gestor, "valor": 1200000.01}
    assert client.post("/api/receitas", json={**corpo, "cliente": ""}).status_code == 422
    assert client.post("/api/receitas", json={**corpo, "origem_cliente": "Inventada"}).status_code == 422
    assert client.post("/api/receitas", json={**corpo, "valor": None}).status_code == 422
    c = client.post("/api/receitas", json=corpo)
    assert c.status_code == 201
    d = c.json()
    assert d["fonte"] == "Transferência intercompany" and d["total"] == 1200000.01 and len(d["meses"]) == 12 and d["cliente"] == "Projeto Alfa"
    t = client.get("/api/receitas").json()["totais"]
    assert t["receita"] == round(base + 1200000.01, 2) and t["intercompany"] == 1200000.01
    # outro ano fica registrado, mas não soma em 2027
    o = client.put(f"/api/receitas/{d['id']}", json={"ano": 2028}).json()
    assert o["ano"] == 2028      # o ano é só referência: a transferência sempre conta em 2027
    assert client.get("/api/receitas").json()["totais"]["receita"] == round(base + 1200000.01, 2)
    assert sum(m["receita"] for m in client.get("/api/receitas").json()["mensal"]) == base      # sem calendário
    assert client.put(f"/api/receitas/{d['id']}", json={"ano": 2019}).status_code == 422
    assert client.put(f"/api/receitas/{d['id']}", json={"ano": 2027, "valor": 600}).json()["total"] == 600
    assert client.delete(f"/api/receitas/{d['id']}").status_code == 200


def test_orcamento_de_receita(client):
    entrar(client)
    r0 = client.get("/api/receitas").json()
    origem, gerente = r0["origens"][0], r0["gerentes"][0]
    d0, rec0 = r0["totais"]["despesa"], r0["totais"]["receita"]
    resumo0 = client.get("/api/resumo").json()["total_plano"]
    c = client.post("/api/projetos", json={"descricao": "Receita de teste", "origem": origem, "gerente": gerente, "tipo": "receita"})
    assert c.status_code == 201
    orc = c.json()["orcamento"]
    assert client.post("/api/projetos", json={"descricao": "X", "origem": origem, "gerente": gerente, "tipo": "outro"}).status_code == 422
    assert [p for p in client.get("/api/projetos").json() if p["orcamento"] == orc][0]["tipo"] == "receita"
    # só o valor anual, sem calendarizar
    k = client.post("/api/receitas", json={"orcamento": orc, "fonte": "Parcerias", "valor": 120000})
    assert k.status_code == 201 and k.json()["total"] == 120000
    r1 = client.get("/api/receitas").json()
    assert r1["totais"]["despesa"] == d0 and r1["totais"]["receita"] == round(rec0 + 120000, 2)
    assert client.get("/api/resumo").json()["total_plano"] == resumo0


def test_editar_tipo_e_excluir_orcamento(client):
    entrar(client)
    r0 = client.get("/api/receitas").json()
    origem, gerente = r0["origens"][0], r0["gerentes"][0]
    orc = client.post("/api/projetos", json={"descricao": "Orçamento de teste", "origem": origem, "gerente": gerente}).json()["orcamento"]
    tipo = lambda: [p for p in client.get("/api/projetos").json() if p["orcamento"] == orc][0]["tipo"]
    assert tipo() == "despesa"
    assert client.patch(f"/api/projetos/{orc}", json={"tipo": "receita"}).status_code == 200 and tipo() == "receita"
    assert client.patch(f"/api/projetos/{orc}", json={"tipo": "xx"}).status_code == 422
    assert client.patch(f"/api/projetos/{orc}", json={"tipo": "despesa"}).status_code == 200 and tipo() == "despesa"
    client.post("/api/receitas", json={"orcamento": orc, "fonte": "Parcerias", "valor": 1000})
    d = client.delete(f"/api/projetos/{orc}")
    assert d.status_code == 200 and d.json()["removidos"]["receitas"] == 1
    assert not [p for p in client.get("/api/projetos").json() if p["orcamento"] == orc]
    # orçamento que existia em 2026 não pode ser excluído
    existente = next(p["orcamento"] for p in client.get("/api/projetos").json() if not p["novo"])
    assert client.delete(f"/api/projetos/{existente}").status_code == 409


def test_headcount_em_projeto_de_outro_gestor(client):
    entrar(client)
    h = client.get("/api/headcount").json()
    assert all("meu" in p for p in h["projetos"]) and len(h["projetos"]) >= 5
    assert client.get("/api/headcount/parametros").json()["parametros"]
    gestor_liberado(client, "luciana")
    h = client.get("/api/headcount").json()
    alheio = next(p for p in h["projetos"] if not p["meu"])
    tf = h["tarefas"][alheio["orcamento"]]["lista"][0]
    corpo = {"orcamento": alheio["orcamento"], "funcao": "Analista", "cargo": "Pleno", "trajetoria": "GESTAO DO NEGOCIO", "nivel": "PLENO",
             "grupo": "GRUPO 01", "justificativa": "x", "edt": tf["edt"], "tarefa": tf["tarefa"]}
    r = client.post("/api/headcount", json=corpo)
    assert r.status_code == 201, r.text
    hid = r.json()["id"]
    assert [i for i in client.get("/api/headcount").json()["itens"] if i["id"] == hid]       # quem lançou enxerga
    assert client.get("/api/headcount/parametros").status_code == 403
    assert client.put(f"/api/headcount/{hid}", json={**corpo, "quantidade": 2}).status_code == 200
    assert client.delete(f"/api/headcount/{hid}").status_code == 200


def test_acompanhamento_por_gerencia(client):
    entrar(client)
    r = client.post("/api/usuarios", json={"login": "coord.x", "nome": "Coord X", "perfil": "gestor", "gerencia": "Gerência Teste",
                                           "cargo": "coordenador", "gerentes": [client.get("/api/usuarios").json()["gerentes"][0]]})
    assert r.status_code == 201, r.text
    assert r.json()["gerencia"] == "Gerência Teste" and r.json()["cargo"] == "coordenador"
    p = client.get("/api/planejamento").json()
    g = {x["gerencia"]: x for x in p["gerencias"]}
    assert "Gerência Teste" in g
    t = g["Gerência Teste"]
    assert t["pessoas"][0]["login"] == "coord.x" and t["projetos"] >= 0
    assert {"aprovado", "executado", "plano", "pendencias"} <= set(t)


def test_gerencia_e_cargo_obrigatorios_e_niveis(client):
    entrar(client)
    sem = {"login": "sem.cargo", "nome": "Sem Cargo", "perfil": "admin"}
    assert client.post("/api/usuarios", json=sem).status_code == 422
    for lg, cargo, ger in (("dir.exec", "diretor_executivo", "DSS - Diretoria de Serviços e Soluções"), ("pmo.x", "pmo", "DSS - Diretoria de Serviços e Soluções"),
                           ("dir.adj", "diretor_adjunto", "Diretoria Adjunta")):
        r = client.post("/api/usuarios", json={"login": lg, "nome": "Pessoa " + lg, "perfil": "admin", "gerencia": ger, "cargo": cargo})
        assert r.status_code == 201, r.text
    g = client.get("/api/planejamento").json()["gerencias"]
    assert [x["nivel"] for x in g[:2]] == ["dss", "diretoria"]
    assert g[0]["projetos"] == g[1]["projetos"] > 0 and g[0]["plano"] == g[1]["plano"]      # DSS repete a Diretoria Adjunta
    assert {p["cargo"] for p in g[0]["pessoas"]} == {"diretor_executivo", "pmo"}


def test_pa_por_projeto_inclui_receitas(client):
    entrar(client)
    ps = client.get("/api/projetos").json()
    alvo = next(p for p in ps if p["tipo"] == "despesa")
    antes = alvo["receitas_2027"]
    r = client.post("/api/receitas", json={"orcamento": alvo["orcamento"], "tipo": "intercompany", "ano": 2026, "cliente": "Cliente X",
                                           "origem_cliente": "Fomento", "gestor_cliente": "Fulano", "valor": 1200})
    assert r.status_code in (200, 201), r.text
    depois = next(p for p in client.get("/api/projetos").json() if p["orcamento"] == alvo["orcamento"])
    assert round(depois["receitas_2027"] - antes, 2) == 1200
    assert round(depois["resultado_2027"], 2) == round(depois["receitas_2027"] - depois["total_2027"], 2)


def test_contingenciado_e_apagar_numero(client):
    entrar(client)
    p = next(x for x in client.get("/api/projetos").json() if x["tipo"] == "despesa" and x["n_linhas"])
    o = p["orcamento"]
    assert client.patch(f"/api/projetos/{o}", json={"n_projeto": "1234"}).status_code == 200
    assert client.patch(f"/api/projetos/{o}", json={"n_projeto": ""}).status_code == 200
    x = next(y for y in client.get("/api/projetos").json() if y["orcamento"] == o)
    assert x["n_projeto"] == "" and "Nº do Projeto" in x["pendencias"]
    assert client.patch(f"/api/projetos/{o}", json={"contingenciado": True}).status_code == 200
    x = next(y for y in client.get("/api/projetos").json() if y["orcamento"] == o)
    assert x["contingenciado"] and x["pendencias"] == []
    assert client.get(f"/api/projetos/{o}").json()["projeto"]["contingenciado"] is True


def test_descricao_do_projeto(client):
    entrar(client)
    o = client.get("/api/projetos").json()[0]["orcamento"]
    assert client.patch(f"/api/projetos/{o}", json={"detalhe": "  Objetivo do projeto em 2027.  "}).status_code == 200
    assert client.get(f"/api/projetos/{o}").json()["projeto"]["detalhe"] == "Objetivo do projeto em 2027."
    assert client.patch(f"/api/projetos/{o}", json={"detalhe": "x" * 3001}).status_code == 422


def test_headcount_com_equipamentos_do_catalogo(client):
    entrar(client)
    h = client.get("/api/headcount").json()
    assert len(h["catalogo"]["itens"]) == 11
    orc = h["projetos"][0]["orcamento"]
    tf = h["tarefas"][orc]["lista"][0]
    base = {"orcamento": orc, "funcao": "Analista", "cargo": "Pleno", "trajetoria": "GESTAO DO NEGOCIO", "nivel": "PLENO", "grupo": "GRUPO 01",
            "posicao": 0, "mes_inicio": 3, "quantidade": 2, "justificativa": "x", "edt": tf["edt"], "tarefa": tf["tarefa"]}
    sem = client.post("/api/headcount", json=base).json()
    com = client.post("/api/headcount", json={**base, "computador": "N2.B", "monitor": "M2", "periferico": "DS1"})
    assert com.status_code == 201, com.text
    com = com.json()
    unit = 7203.00 + 850.00 + 1219.00
    assert com["equipamentos"]["unitario"] == unit and com["equipamentos"]["total"] == unit * 2
    assert round(com["custo_2027"] - sem["custo_2027"], 2) == unit * 2
    assert round(com["anualizado"] - sem["anualizado"], 2) == 0
    hw = [x for x in client.get(f"/api/projetos/{orc}").json()["linhas"] if x["conta_codigo"] == "13010102" and x["fonte"] == "headcount"]
    assert hw and hw[0]["meses"][2] == unit * 2 and sum(hw[0]["meses"]) == unit * 2      # só no mês de início
    assert client.post("/api/headcount", json={**base, "monitor": "N2.B"}).status_code == 422      # código de outro tipo


def _xlsx(linhas):
    import io
    import openpyxl
    wb = openpyxl.Workbook()
    for l in linhas:
        wb.active.append(l)
    b = io.BytesIO()
    wb.save(b)
    return b.getvalue()


def _envia(client, tipo, dados, simular, nome="t.xlsx"):
    return client.post(f"/api/referencias/{tipo}/importar?simular={'true' if simular else 'false'}", files={"arquivo": (nome, dados)})


def test_importar_equipamentos(client):
    entrar(client)
    assert len(client.get("/api/referencias").json()) == 3
    modelo = client.get("/api/referencias/equipamentos/modelo")
    assert modelo.status_code == 200 and modelo.content[:2] == b"PK"
    arq = _xlsx([["Código", "Tipo", "Equipamento", "Perfil", "Valor"],
                 ["D1", "computador", "Desktop Mini", "Regular", "5.500,00"], ["M1", "monitor", "Monitor 24", "", 700], ["DS1", "periférico", "Dock", "", 1300]])
    sim = _envia(client, "equipamentos", arq, True).json()
    assert sim["novos"] == 0 and sim["alterados"] == 3 and len(sim["ausentes"]) == 8 and sim["erros"] == []
    h = client.get("/api/headcount").json()
    assert len(h["catalogo"]["itens"]) == 11      # simulação não grava
    assert _envia(client, "equipamentos", arq, False).status_code == 200
    h = client.get("/api/headcount").json()
    assert [i["codigo"] for i in h["catalogo"]["itens"]] == ["D1", "M1", "DS1"] and h["catalogo"]["itens"][0]["valor"] == 5500.0
    ruim = _xlsx([["Código", "Tipo", "Equipamento", "Valor"], ["X1", "carro", "Fusca", 10]])
    assert _envia(client, "equipamentos", ruim, True).json()["erros"]
    assert _envia(client, "equipamentos", ruim, False).status_code == 422


def test_importar_salarios_e_tarifas(client):
    entrar(client)
    h = client.get("/api/headcount").json()
    f = next(x for x in h["tabela"] if x["trajetoria"] == "GESTAO DO NEGOCIO" and x["nivel"] == "PLENO" and x["grupo"] == "GRUPO 01")
    arq = _xlsx([["Trajetória", "Nível", "Grupo", "Início da faixa (80%)", "Fim da faixa (120%)"], ["Gestão do Negócio", "Pleno", "Grupo 01", 7000, 10000]])
    sim = _envia(client, "salarios", arq, True).json()
    assert sim["alterados"] == 1 and sim["novos"] == 0 and sim["erros"] == []
    assert _envia(client, "salarios", arq, False).status_code == 200
    h2 = client.get("/api/headcount").json()
    assert len(h2["tabela"]) == 1 and h2["tabela"][0]["inicio"] == 7000 and h2["tabela"][0]["trajetoria"] == f["trajetoria"]
    # tarifas: atualiza as existentes e inclui novas, sem apagar as demais
    t = client.get("/api/viagens/tarifas").json()
    ex = t[0]
    csv_ = ("tipo;origem;destino;passagem;hospedagem;bagagem;aux_transporte;ajuda_custo;seguro\n"
            f"{'nacional' if ex['tipo'] == 'nac' else 'internacional'};{ex['origem']};{ex['destino']};1.234,50;100;0;0;0;0\n"
            "nacional;ORIGEM X;DESTINO Y;500;200;50;30;40;0\n").encode()
    sim = _envia(client, "viagens", csv_, True, "t.csv").json()
    assert sim["novos"] == 1 and sim["alterados"] == 1 and sim["erros"] == []
    assert _envia(client, "viagens", csv_, False, "t.csv").status_code == 200
    t2 = client.get("/api/viagens/tarifas").json()
    assert len(t2) == len(t) + 1
    assert next(x for x in t2 if x["id"] == ex["id"])["passagem"] == 1234.5
