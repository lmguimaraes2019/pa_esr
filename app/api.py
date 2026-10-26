"""Rotas da API. Perfis: 'admin' vê e edita tudo; 'gestor' vê e edita só os projetos que gerencia."""
from __future__ import annotations

import math
import re
import sqlite3
from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from . import config, export_xlsx, importers, security
from .db import MESES, NOMES_MESES, audit, connect, tx

router = APIRouter(prefix="/api")
SOMA_MESES = "+".join(MESES)
# origem de recursos vigente em 2027 (a coluna "origem" guarda a de 2026 e nunca é alterada pelo plano)
ORIGEM_27 = "COALESCE(NULLIF(p.origem_2027, ''), p.origem)"


# ---------------------------------------------------------------- acesso

def _conn():
    c = connect()
    try:
        yield c
    finally:
        c.close()


def usuario_atual(request: Request, c: sqlite3.Connection = Depends(_conn)) -> dict:
    uid = security.read_session(request.cookies.get(config.COOKIE_NAME))
    row = c.execute("SELECT * FROM users WHERE id=? AND ativo=1", (uid,)).fetchone() if uid else None
    if not row:
        raise HTTPException(401, "Sessão expirada. Entre novamente.")
    return dict(row)


def usuario_liberado(u: dict = Depends(usuario_atual)) -> dict:
    if u["trocar_senha"]:
        raise HTTPException(403, "Troque a senha provisória para continuar.")
    return u


def exige_admin(u: dict = Depends(usuario_liberado)) -> dict:
    if u["perfil"] != "admin":
        raise HTTPException(403, "Apenas o administrador pode fazer isso.")
    return u


def permitidos(c: sqlite3.Connection, u: dict) -> set[str]:
    if u["perfil"] == "admin":
        return {r[0] for r in c.execute("SELECT orcamento FROM projetos")}
    rows = c.execute("SELECT orcamento FROM projetos WHERE gerente IN (SELECT gerente FROM user_gerentes WHERE user_id=?) "
                     "UNION SELECT orcamento FROM user_projetos WHERE user_id=?", (u["id"], u["id"]))
    return {r[0] for r in rows}


def exige_acesso(c: sqlite3.Connection, u: dict, orcamento: str) -> sqlite3.Row:
    p = c.execute("SELECT * FROM projetos WHERE orcamento=?", (orcamento,)).fetchone()
    if not p or orcamento not in permitidos(c, u):
        raise HTTPException(404, "Projeto não encontrado.")
    return p


def _arred(v: float) -> float:
    return round(float(v), 2)


# ---------------------------------------------------------------- modelos

class LoginIn(BaseModel):
    login: str = Field(min_length=1, max_length=60)
    senha: str = Field(min_length=1, max_length=200)


class SenhaIn(BaseModel):
    atual: str
    nova: str = Field(max_length=200)


def _validar_meses(v: list[float]) -> list[float]:
    if len(v) != 12:
        raise ValueError("Informe os 12 meses.")
    for x in v:
        if not math.isfinite(x) or x < 0 or x > 1e11:
            raise ValueError("Valores mensais devem ser números entre 0 e 100 bilhões.")
    return [_arred(x) for x in v]


class LinhaIn(BaseModel):
    edt: str = Field(min_length=1, max_length=200)
    tarefa: str = Field(min_length=1, max_length=200)
    conta_codigo: str = Field(min_length=1, max_length=20)
    meses: list[float]
    obs: str = Field(default="", max_length=1000)

    _m = field_validator("meses")(_validar_meses)


class LinhaPatch(BaseModel):
    edt: str | None = Field(default=None, min_length=1, max_length=200)
    tarefa: str | None = Field(default=None, min_length=1, max_length=200)
    conta_codigo: str | None = Field(default=None, min_length=1, max_length=20)
    meses: list[float] | None = None
    obs: str | None = Field(default=None, max_length=1000)

    @field_validator("meses")
    @classmethod
    def _m(cls, v):
        return None if v is None else _validar_meses(v)


class ProjetoNovo(BaseModel):
    descricao: str = Field(min_length=3, max_length=200)
    origem: str = Field(min_length=1, max_length=40)
    gerente: str = Field(min_length=1, max_length=100)


class ProjetoPatch(BaseModel):
    n_projeto: str | None = Field(default=None, max_length=12)
    descricao: str | None = Field(default=None, min_length=3, max_length=200)
    origem: str | None = Field(default=None, min_length=1, max_length=40)
    gerente: str | None = Field(default=None, min_length=1, max_length=100)

    @field_validator("n_projeto")
    @classmethod
    def _n(cls, v):
        if v is not None and v != "" and not re.fullmatch(r"\d{1,10}", v):
            raise ValueError("O Nº do Projeto deve conter apenas dígitos.")
        return v


class PremissasIn(BaseModel):
    reajuste_pessoal: float = Field(ge=-50, le=100)
    reajuste_geral: float = Field(ge=-50, le=100)
    dolar: float = Field(gt=0, le=50)
    viagens_bagagem_vezes: float | None = Field(default=None, ge=0, le=4)


class AplicarIn(BaseModel):
    orcamentos: list[str] | None = None
    sobrescrever_editadas: bool = False
    simular: bool = True


class UsuarioIn(BaseModel):
    login: str = Field(pattern=r"^[a-z0-9._-]{3,30}$")
    nome: str = Field(min_length=2, max_length=100)
    perfil: str = Field(pattern="^(admin|gestor)$")
    gerente: str | None = Field(default=None, max_length=100)
    gerentes: list[str] | None = Field(default=None, max_length=30)
    projetos: list[str] | None = Field(default=None, max_length=100)


class UsuarioPatch(BaseModel):
    nome: str | None = Field(default=None, min_length=2, max_length=100)
    perfil: str | None = Field(default=None, pattern="^(admin|gestor)$")
    gerentes: list[str] | None = Field(default=None, max_length=30)
    projetos: list[str] | None = Field(default=None, max_length=100)
    ativo: bool | None = None


# ---------------------------------------------------------------- sessão

def _publico(u: dict) -> dict:
    return {"id": u["id"], "login": u["login"], "nome": u["nome"], "perfil": u["perfil"],
            "gerente": u["gerente"], "trocar_senha": bool(u["trocar_senha"])}


@router.post("/login")
def login(dados: LoginIn, request: Request, response: Response, c: sqlite3.Connection = Depends(_conn)):
    chave = f"{request.client.host if request.client else '-'}|{dados.login.lower()}"
    espera = security.bloqueado(chave)
    if espera:
        raise HTTPException(429, f"Muitas tentativas. Tente de novo em {espera // 60 + 1} minuto(s).")
    row = c.execute("SELECT * FROM users WHERE login=? AND ativo=1", (dados.login.strip(),)).fetchone()
    if not row or not security.verify_password(dados.senha, row["senha_hash"]):
        security.registrar_falha(chave)
        raise HTTPException(401, "Usuário ou senha incorretos.")
    security.limpar_falhas(chave)
    response.set_cookie(config.COOKIE_NAME, security.make_session(row["id"]), max_age=config.SESSION_MAX_AGE,
                        httponly=True, samesite="lax", secure=config.COOKIE_SECURE, path="/")
    return _publico(dict(row))


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(config.COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me")
def me(u: dict = Depends(usuario_atual)):
    return _publico(u)


@router.post("/me/senha")
def trocar_senha(dados: SenhaIn, u: dict = Depends(usuario_atual)):
    if not security.verify_password(dados.atual, u["senha_hash"]):
        raise HTTPException(400, "A senha atual não confere.")
    erro = security.senha_valida(dados.nova)
    if erro:
        raise HTTPException(400, erro)
    if dados.nova == dados.atual:
        raise HTTPException(400, "A nova senha deve ser diferente da atual.")
    with tx() as c:
        c.execute("UPDATE users SET senha_hash=?, trocar_senha=0 WHERE id=?", (security.hash_password(dados.nova), u["id"]))
        audit(c, u["login"], "trocou a própria senha")
    return {"ok": True}


# ---------------------------------------------------------------- referência

@router.get("/contas")
def contas(_: dict = Depends(usuario_liberado), c: sqlite3.Connection = Depends(_conn)):
    return [dict(r) for r in c.execute("SELECT codigo, descricao, grupo FROM contas ORDER BY grupo, descricao")]


@router.get("/premissas")
def ler_premissas(_: dict = Depends(usuario_liberado), c: sqlite3.Connection = Depends(_conn)):
    return {r["chave"]: {"valor": r["valor"], "descricao": r["descricao"]} for r in c.execute("SELECT * FROM premissas")}


@router.put("/premissas")
def gravar_premissas(dados: PremissasIn, u: dict = Depends(exige_admin)):
    with tx() as c:
        enviados = dados.model_dump(exclude_none=True)
        for chave, valor in enviados.items():
            c.execute("UPDATE premissas SET valor=? WHERE chave=?", (valor, chave))
        audit(c, u["login"], "alterou premissas", detalhe=str(enviados))
    return {"ok": True}


def _fator(grupo: str, prem: dict[str, float]) -> float:
    return 1 + (prem["reajuste_pessoal"] if grupo == "Pessoal" else prem["reajuste_geral"]) / 100


@router.post("/premissas/aplicar")
def aplicar_premissas(dados: AplicarIn, u: dict = Depends(exige_admin)):
    """Recalcula as linhas de 2027 a partir do 2026 aprovado com os reajustes. Por padrão só simula."""
    with tx() as c:
        prem = {r["chave"]: r["valor"] for r in c.execute("SELECT chave, valor FROM premissas")}
        sql = (f"SELECT l.id, l.orcamento, l.editada, k.grupo, {', '.join('l.' + m for m in MESES)}, "
               f"{', '.join('b.' + m + ' AS b_' + m for m in MESES)} "
               "FROM linhas l JOIN linhas b ON b.id = l.base_id JOIN contas k ON k.codigo = l.conta_codigo "
               "WHERE l.ciclo = ? AND l.fonte <> 'viagens'")
        antes = depois = 0.0
        afetadas = ignoradas_editadas = 0
        for r in c.execute(sql, (config.CICLO_PLANO,)).fetchall():
            if dados.orcamentos and r["orcamento"] not in dados.orcamentos:
                continue
            if r["editada"] and not dados.sobrescrever_editadas:
                ignoradas_editadas += 1
                continue
            novos = [_arred(r["b_" + m] * _fator(r["grupo"], prem)) for m in MESES]
            antes += sum(r[m] for m in MESES)
            depois += sum(novos)
            afetadas += 1
            if not dados.simular:
                c.execute(f"UPDATE linhas SET {', '.join(m + '=?' for m in MESES)}, editada=0, "
                          "atualizado_por=?, atualizado_em=datetime('now') WHERE id=?", (*novos, u["login"], r["id"]))
        if not dados.simular:
            audit(c, u["login"], "aplicou premissas", detalhe=f"{afetadas} linhas; {prem}")
    return {"simulacao": dados.simular, "linhas_afetadas": afetadas, "linhas_editadas_preservadas": ignoradas_editadas,
            "total_antes": _arred(antes), "total_depois": _arred(depois)}


# ---------------------------------------------------------------- projetos e linhas

def _linha(r: sqlite3.Row) -> dict:
    meses = [_arred(r[m]) for m in MESES]
    total = _arred(sum(meses))
    ref = None
    if r["base_id"] is not None:
        rm = [_arred(r["b_" + m]) for m in MESES]
        ref = {"meses": rm, "total": _arred(sum(rm))}
    realizado, empenhado = _arred(r["realizado"] or 0), _arred(r["empenhado"] or 0)
    executado = _arred(realizado + empenhado)
    if r["fonte"] == "viagens":
        status = "viagens"
    elif ref is None:
        status = "nova"
    elif meses == ref["meses"]:
        status = "mantida"
    else:
        status = "ajustada"
    alertas = []
    if ref and ref["total"] > 0:
        if executado > ref["total"] + 0.5:
            alertas.append("executado acima do aprovado")
        elif executado < ref["total"] * 0.5 and ref["total"] >= 1000:
            alertas.append("executado abaixo de 50% do aprovado")
        if total == 0:
            alertas.append("zerada em 2027")
    return {"id": r["id"], "edt": r["edt"], "tarefa": r["tarefa"], "conta_codigo": r["conta_codigo"],
            "conta_desc": r["conta_desc"], "grupo": r["grupo"], "meses": meses, "total": total,
            "obs": r["obs"], "editada": bool(r["editada"]), "fonte": r["fonte"], "base_id": r["base_id"], "status": status, "ref": ref,
            "realizado": realizado, "empenhado": empenhado, "executado": executado, "alertas": alertas,
            "atualizado_por": r["atualizado_por"], "atualizado_em": r["atualizado_em"]}


@router.get("/projetos")
def projetos(u: dict = Depends(usuario_liberado), c: sqlite3.Connection = Depends(_conn)):
    ids = sorted(permitidos(c, u))
    if not ids:
        return []
    marks = ",".join("?" for _ in ids)
    rows = c.execute(
        f"""SELECT p.*,
            (SELECT COALESCE(SUM({SOMA_MESES}),0) FROM linhas WHERE ciclo={config.CICLO_BASE} AND orcamento=p.orcamento) AS t_base,
            (SELECT COALESCE(SUM({SOMA_MESES}),0) FROM linhas WHERE ciclo={config.CICLO_PLANO} AND orcamento=p.orcamento) AS t_plano,
            (SELECT COUNT(*) FROM linhas WHERE ciclo={config.CICLO_PLANO} AND orcamento=p.orcamento) AS n_linhas,
            (SELECT COALESCE(SUM(realizado),0) FROM execucao WHERE orcamento=p.orcamento) AS realizado,
            (SELECT COALESCE(SUM(empenhado),0) FROM execucao WHERE orcamento=p.orcamento) AS empenhado
            FROM projetos p WHERE p.orcamento IN ({marks}) ORDER BY p.novo DESC, {ORIGEM_27}, p.descricao""", ids).fetchall()
    return [{**{k: r[k] for k in ("orcamento", "n_projeto", "descricao", "gerente", "n_linhas")}, "novo": bool(r["novo"]),
             "origem": r["origem_2027"] or r["origem"], "origem_2026": r["origem"],
             "original_2026": _arred(r["original_2026"]), "total_2026": _arred(r["t_base"]),
             "total_2027": _arred(r["t_plano"]), "realizado_2026": _arred(r["realizado"]),
             "empenhado_2026": _arred(r["empenhado"]),
             "pendencias": (["Nº do Projeto"] if not r["n_projeto"] and r["n_linhas"] else [])} for r in rows]


@router.get("/listas")
def listas(_: dict = Depends(usuario_liberado)):
    """Origens de recurso e gerentes aceitos pelo template do PMO."""
    d = export_xlsx._listas_template()
    return {"origens": d["origens"], "gerentes": d["gerentes"]}


@router.post("/projetos", status_code=201)
def criar_projeto(dados: ProjetoNovo, u: dict = Depends(usuario_liberado)):
    """Cria um orçamento novo, sem número de orçamento ainda (a chave interna é N27-001, N27-002...)."""
    ld = export_xlsx._listas_template()
    if dados.origem not in ld["origens"]:
        raise HTTPException(422, "Origem de recurso fora da lista do template.")
    if dados.gerente not in ld["gerentes"]:
        raise HTTPException(422, "Gerente fora da lista do template.")
    with tx() as c:
        n = 1 + max([int(r[0][4:]) for r in c.execute("SELECT orcamento FROM projetos WHERE orcamento LIKE 'N27-%'")
                     if r[0][4:].isdigit()] or [0])
        chave = f"N27-{n:03d}"
        c.execute("INSERT INTO projetos (orcamento, n_projeto, descricao, origem, origem_2027, gerente, novo) VALUES (?,?,?,?,?,?,1)",
                  (chave, "", dados.descricao.strip(), dados.origem, dados.origem, dados.gerente))
        if u["perfil"] != "admin":     # quem cria enxerga o que criou, mesmo sem acompanhar aquele gerente
            c.execute("INSERT OR IGNORE INTO user_projetos (user_id, orcamento) VALUES (?,?)", (u["id"], chave))
        audit(c, u["login"], "criou orçamento novo", chave, detalhe=f"{dados.descricao} | {dados.origem} | {dados.gerente}")
    return {"orcamento": chave}


@router.patch("/projetos/{orcamento}")
def editar_projeto(orcamento: str, dados: ProjetoPatch, u: dict = Depends(usuario_liberado)):
    with tx() as c:
        p = exige_acesso(c, u, orcamento)
        campos = dados.model_dump(exclude_none=True)
        if u["perfil"] != "admin" and ("n_projeto" in campos or "gerente" in campos
                                       or ("descricao" in campos and not p["novo"])):
            raise HTTPException(403, "Apenas o administrador altera o Nº do Projeto, o gerente e o nome de orçamentos existentes.")
        if "origem" in campos or "gerente" in campos:
            ld = export_xlsx._listas_template()
            if "origem" in campos and campos["origem"] not in ld["origens"]:
                raise HTTPException(422, "Origem de recurso fora da lista do template.")
            if "gerente" in campos and campos["gerente"] not in ld["gerentes"]:
                raise HTTPException(422, "Gerente fora da lista do template.")
        if "descricao" in campos:
            campos["descricao"] = campos["descricao"].strip()
        if "origem" in campos:      # a mudança vale só para 2027; a origem de 2026 fica como está (exceto em orçamento novo, que não tem 2026)
            campos["origem_2027"] = campos.pop("origem")
            if p["novo"]:
                campos["origem"] = campos["origem_2027"]
        if campos:
            c.execute(f"UPDATE projetos SET {', '.join(k + '=?' for k in campos)} WHERE orcamento=?", (*campos.values(), orcamento))
            antes = {k: p[k] for k in campos if k in p.keys()}
            audit(c, u["login"], "editou projeto", orcamento, detalhe=f"{antes} para {campos}")
    return {"ok": True}


_SQL_LINHAS = f"""
SELECT l.*, k.descricao AS conta_desc, k.grupo,
       {', '.join('b.' + m + ' AS b_' + m for m in MESES)},
       e.realizado, e.empenhado
FROM linhas l
JOIN contas k ON k.codigo = l.conta_codigo
LEFT JOIN linhas b ON b.id = l.base_id
LEFT JOIN execucao e ON l.base_id IS NOT NULL AND e.orcamento = l.orcamento
     AND e.edt = b.edt AND e.tarefa = b.tarefa AND e.conta_codigo = b.conta_codigo
WHERE l.ciclo = {config.CICLO_PLANO}"""


@router.get("/projetos/{orcamento}")
def detalhe_projeto(orcamento: str, u: dict = Depends(usuario_liberado), c: sqlite3.Connection = Depends(_conn)):
    p = exige_acesso(c, u, orcamento)
    rows = c.execute(_SQL_LINHAS + " AND l.orcamento=? ORDER BY l.edt, l.tarefa, l.conta_codigo, l.id", (orcamento,)).fetchall()
    linhas = [_linha(r) for r in rows]
    ex = c.execute("SELECT COALESCE(SUM(realizado),0), COALESCE(SUM(empenhado),0) FROM execucao WHERE orcamento=?",
                   (orcamento,)).fetchone()
    # visão de 2026: o que foi aprovado, o que foi executado e o que aconteceu com a linha em 2027
    passado = []
    for r in c.execute(
            f"""SELECT b.id, b.edt, b.tarefa, b.conta_codigo, k.descricao AS conta_desc, k.grupo,
                       {', '.join('b.' + m for m in MESES)}, e.realizado, e.empenhado,
                       (SELECT COUNT(*) FROM linhas p WHERE p.base_id = b.id) AS n27,
                       (SELECT COALESCE(SUM({SOMA_MESES.replace('m', 'p.m')}),0) FROM linhas p WHERE p.base_id = b.id) AS t27
                FROM linhas b JOIN contas k ON k.codigo = b.conta_codigo
                LEFT JOIN execucao e ON e.orcamento = b.orcamento AND e.edt = b.edt AND e.tarefa = b.tarefa
                     AND e.conta_codigo = b.conta_codigo
                WHERE b.ciclo = ? AND b.orcamento = ? ORDER BY b.edt, b.tarefa, b.conta_codigo""",
            (config.CICLO_BASE, orcamento)):
        meses = [_arred(r[m]) for m in MESES]
        aprovado = _arred(sum(meses))
        real, emp = _arred(r["realizado"] or 0), _arred(r["empenhado"] or 0)
        passado.append({"id": r["id"], "edt": r["edt"], "tarefa": r["tarefa"], "conta_codigo": r["conta_codigo"],
                        "conta_desc": r["conta_desc"], "grupo": r["grupo"], "meses": meses, "aprovado": aprovado,
                        "realizado": real, "empenhado": emp, "executado": _arred(real + emp),
                        "saldo": _arred(aprovado - real - emp),
                        "pct": round((real + emp) / aprovado * 100, 1) if aprovado > 0 else None,
                        "plano_2027": _arred(r["t27"]), "removida": r["n27"] == 0})
    casado_r = sum(x["realizado"] for x in linhas)
    casado_e = sum(x["empenhado"] for x in linhas)
    contagem = {k: sum(1 for x in linhas if x["status"] == k) for k in ("mantida", "ajustada", "nova", "viagens")}
    return {
        "projeto": {k: p[k] for k in ("orcamento", "n_projeto", "descricao", "gerente", "diretoria")}
                   | {"novo": bool(p["novo"]), "origem": p["origem_2027"] or p["origem"], "origem_2026": p["origem"]}
                   | {"original_2026": _arred(p["original_2026"])},
        "linhas": linhas, "passado": passado,
        "totais": {"plano": _arred(sum(x["total"] for x in linhas)),
                   "base": _arred(sum(x["aprovado"] for x in passado)),
                   "realizado": _arred(ex[0]), "empenhado": _arred(ex[1]),
                   "realizado_sem_linha": _arred(ex[0] - casado_r), "empenhado_sem_linha": _arred(ex[1] - casado_e),
                   "removidas": sum(1 for x in passado if x["removida"]), "status": contagem,
                   "alertas": sum(1 for x in linhas if x["alertas"])},
    }


def _checar_conta(c: sqlite3.Connection, codigo: str) -> None:
    if not c.execute("SELECT 1 FROM contas WHERE codigo=?", (codigo,)).fetchone():
        raise HTTPException(422, "Conta contábil fora da lista do template.")


@router.post("/projetos/{orcamento}/linhas", status_code=201)
def criar_linha(orcamento: str, dados: LinhaIn, u: dict = Depends(usuario_liberado)):
    with tx() as c:
        exige_acesso(c, u, orcamento)
        _checar_conta(c, dados.conta_codigo)
        cur = c.execute(
            f"INSERT INTO linhas (ciclo, orcamento, edt, tarefa, conta_codigo, {', '.join(MESES)}, editada, obs, atualizado_por) "
            f"VALUES (?,?,?,?,?,{', '.join('?' for _ in MESES)},1,?,?)",
            (config.CICLO_PLANO, orcamento, dados.edt.strip(), dados.tarefa.strip(), dados.conta_codigo,
             *dados.meses, dados.obs.strip(), u["login"]))
        audit(c, u["login"], "criou linha", orcamento, cur.lastrowid, f"{dados.tarefa} / {dados.conta_codigo} / {_arred(sum(dados.meses))}")
        row = c.execute(_SQL_LINHAS + " AND l.id=?", (cur.lastrowid,)).fetchone()
    return _linha(row)


def _linha_do_usuario(c: sqlite3.Connection, u: dict, linha_id: int) -> sqlite3.Row:
    r = c.execute("SELECT * FROM linhas WHERE id=? AND ciclo=?", (linha_id, config.CICLO_PLANO)).fetchone()
    if not r:
        raise HTTPException(404, "Linha não encontrada.")
    exige_acesso(c, u, r["orcamento"])
    return r


def _trava_viagens(linha: sqlite3.Row, altera_valor: bool) -> None:
    if linha["fonte"] == "viagens" and altera_valor:
        raise HTTPException(409, "Esta linha vem do plano de viagens. Altere o plano na aba Viagens e aplique de novo ao orçamento.")


@router.put("/linhas/{linha_id}")
def editar_linha(linha_id: int, dados: LinhaPatch, u: dict = Depends(usuario_liberado)):
    with tx() as c:
        atual = _linha_do_usuario(c, u, linha_id)
        _trava_viagens(atual, dados.meses is not None or dados.conta_codigo is not None or dados.edt is not None
                       or dados.tarefa is not None)
        novo = dados.model_dump(exclude_none=True)
        if "conta_codigo" in novo:
            _checar_conta(c, novo["conta_codigo"])
        sets, vals = [], []
        for campo in ("edt", "tarefa", "conta_codigo", "obs"):
            if campo in novo:
                sets.append(f"{campo}=?")
                vals.append(novo[campo].strip())
        if "meses" in novo:
            sets += [f"{m}=?" for m in MESES]
            vals += novo["meses"]
        if not sets:
            raise HTTPException(422, "Nada para alterar.")
        antes = _arred(sum(atual[m] for m in MESES))
        c.execute(f"UPDATE linhas SET {', '.join(sets)}, editada=1, atualizado_por=?, atualizado_em=datetime('now') WHERE id=?",
                  (*vals, u["login"], linha_id))
        depois = _arred(sum(novo["meses"])) if "meses" in novo else antes
        audit(c, u["login"], "editou linha", atual["orcamento"], linha_id, f"total {antes} para {depois}")
        row = c.execute(_SQL_LINHAS + " AND l.id=?", (linha_id,)).fetchone()
    return _linha(row)


@router.delete("/linhas/{linha_id}")
def excluir_linha(linha_id: int, u: dict = Depends(usuario_liberado)):
    with tx() as c:
        atual = _linha_do_usuario(c, u, linha_id)
        _trava_viagens(atual, True)
        c.execute("DELETE FROM linhas WHERE id=?", (linha_id,))
        audit(c, u["login"], "excluiu linha", atual["orcamento"], linha_id,
              f"{atual['tarefa']} / {atual['conta_codigo']} / {_arred(sum(atual[m] for m in MESES))}")
    return {"ok": True}


@router.delete("/projetos/{orcamento}/linhas")
def excluir_grupo(orcamento: str, edt: str, tarefa: str | None = None, u: dict = Depends(usuario_liberado)):
    """Exclui do plano de 2027 todas as linhas de uma Meta/EDT (ou só de uma Ação/Tarefa dela)."""
    with tx() as c:
        exige_acesso(c, u, orcamento)
        filtro, args = "ciclo=? AND orcamento=? AND edt=?", [config.CICLO_PLANO, orcamento, edt]
        if tarefa is not None:
            filtro += " AND tarefa=?"; args.append(tarefa)
        alvo = c.execute(f"SELECT * FROM linhas WHERE {filtro}", args).fetchall()
        if not alvo:
            raise HTTPException(404, "Nenhuma linha encontrada nesse grupo.")
        if any(r["fonte"] == "viagens" for r in alvo):
            raise HTTPException(409, "O grupo tem linhas do plano de viagens. Altere o plano na aba Viagens ou exclua as outras linhas uma a uma.")
        total = _arred(sum(sum(r[m] for m in MESES) for r in alvo))
        c.execute(f"DELETE FROM linhas WHERE {filtro}", args)
        audit(c, u["login"], "excluiu grupo de linhas", orcamento, None,
              f"{edt}{' / ' + tarefa if tarefa is not None else ''}: {len(alvo)} linhas, {total}")
    return {"ok": True, "linhas": len(alvo), "total": total}


@router.post("/projetos/{orcamento}/linhas/restaurar")
def restaurar_grupo(orcamento: str, edt: str, tarefa: str | None = None, u: dict = Depends(usuario_liberado)):
    """Traz de volta ao plano de 2027 as linhas de 2026 de uma Meta/EDT (ou Ação/Tarefa) que foram excluídas."""
    with tx() as c:
        exige_acesso(c, u, orcamento)
        filtro, args = "b.ciclo=? AND b.orcamento=? AND b.edt=?", [config.CICLO_BASE, orcamento, edt]
        if tarefa is not None:
            filtro += " AND b.tarefa=?"; args.append(tarefa)
        faltam = c.execute(f"SELECT b.* FROM linhas b WHERE {filtro} AND NOT EXISTS "
                           f"(SELECT 1 FROM linhas p WHERE p.base_id=b.id AND p.ciclo=?)", (*args, config.CICLO_PLANO)).fetchall()
        for b in faltam:
            c.execute(
                f"INSERT INTO linhas (ciclo, orcamento, edt, tarefa, conta_codigo, {', '.join(MESES)}, base_id, atualizado_por) "
                f"VALUES (?,?,?,?,?,{', '.join('?' for _ in MESES)},?,?)",
                (config.CICLO_PLANO, b["orcamento"], b["edt"], b["tarefa"], b["conta_codigo"], *[b[m] for m in MESES], b["id"], u["login"]))
        if faltam:
            audit(c, u["login"], "restaurou grupo de 2026", orcamento, None,
                  f"{edt}{' / ' + tarefa if tarefa is not None else ''}: {len(faltam)} linhas")
    return {"ok": True, "linhas": len(faltam)}


@router.post("/linhas/{base_id}/restaurar", status_code=201)
def restaurar_linha(base_id: int, u: dict = Depends(usuario_liberado)):
    """Traz de volta para 2027 uma linha aprovada em 2026 que foi excluída do plano."""
    with tx() as c:
        b = c.execute("SELECT * FROM linhas WHERE id=? AND ciclo=?", (base_id, config.CICLO_BASE)).fetchone()
        if not b:
            raise HTTPException(404, "Linha de 2026 não encontrada.")
        exige_acesso(c, u, b["orcamento"])
        if c.execute("SELECT 1 FROM linhas WHERE base_id=? AND ciclo=?", (base_id, config.CICLO_PLANO)).fetchone():
            raise HTTPException(409, "Esta linha já está no plano de 2027.")
        cur = c.execute(
            f"INSERT INTO linhas (ciclo, orcamento, edt, tarefa, conta_codigo, {', '.join(MESES)}, base_id, atualizado_por) "
            f"VALUES (?,?,?,?,?,{', '.join('?' for _ in MESES)},?,?)",
            (config.CICLO_PLANO, b["orcamento"], b["edt"], b["tarefa"], b["conta_codigo"], *[b[m] for m in MESES], base_id, u["login"]))
        audit(c, u["login"], "restaurou linha de 2026", b["orcamento"], cur.lastrowid, f"{b['tarefa']} / {b['conta_codigo']}")
    return {"ok": True, "id": cur.lastrowid}


# ---------------------------------------------------------------- realizado e empenhado de 2026 (admin)

@router.post("/execucao/importar")
async def importar_execucao(simular: bool = True, arquivo: UploadFile = File(...), u: dict = Depends(exige_admin)):
    """Substitui o realizado e o empenhado de 2026 pelos da planilha (base do Protheus). Não toca no aprovado nem no plano."""
    import tempfile
    from pathlib import Path
    dados = await arquivo.read()
    if len(dados) > 30 * 1024 * 1024:
        raise HTTPException(413, "Arquivo grande demais (limite de 30 MB).")
    if dados[:2] != b"PK":
        raise HTTPException(422, "Envie a planilha em formato .xlsx.")
    with tempfile.TemporaryDirectory() as tmp:
        caminho = Path(tmp) / "protheus.xlsx"
        caminho.write_bytes(dados)
        try:
            novos = importers.build_execucao(importers.load_protheus(caminho))
        except Exception:
            raise HTTPException(422, "Não encontrei a aba BASE ESR com as colunas do Protheus (Tipo de Lançamento, Valor, Mês...).")
    with tx() as c:
        projetos = {r[0] for r in c.execute("SELECT orcamento FROM projetos")}
        validos = [x for x in novos if x["orcamento"] in projetos]
        ignorados = sorted({x["orcamento"] for x in novos if x["orcamento"] not in projetos})
        antes = c.execute("SELECT COALESCE(SUM(realizado),0), COALESCE(SUM(empenhado),0), COUNT(*) FROM execucao").fetchone()
        por_projeto = {}
        for x in validos:
            d = por_projeto.setdefault(x["orcamento"], {"realizado": 0.0, "empenhado": 0.0})
            d["realizado"] += x["realizado"]; d["empenhado"] += x["empenhado"]
        atual = {r["orcamento"]: (r["r"], r["e"]) for r in c.execute(
            "SELECT orcamento, SUM(realizado) r, SUM(empenhado) e FROM execucao GROUP BY orcamento")}
        diff = [{"orcamento": o, "realizado_antes": _arred(atual.get(o, (0, 0))[0]), "realizado_depois": _arred(v["realizado"]),
                 "empenhado_antes": _arred(atual.get(o, (0, 0))[1]), "empenhado_depois": _arred(v["empenhado"])}
                for o, v in sorted(por_projeto.items())]
        resumo = {"simulacao": simular, "linhas": len(validos), "linhas_antes": antes[2],
                  "realizado_antes": _arred(antes[0]), "empenhado_antes": _arred(antes[1]),
                  "realizado_depois": _arred(sum(x["realizado"] for x in validos)),
                  "empenhado_depois": _arred(sum(x["empenhado"] for x in validos)),
                  "orcamentos_ignorados": ignorados, "projetos": diff}
        if not validos:
            raise HTTPException(422, "A planilha não trouxe realizado nem empenhado de orçamentos conhecidos.")
        if not simular:
            c.execute("DELETE FROM execucao")
            c.executemany("INSERT OR REPLACE INTO execucao (orcamento, edt, tarefa, conta_codigo, realizado, empenhado) "
                          "VALUES (:orcamento,:edt,:tarefa,:conta_codigo,:realizado,:empenhado)", validos)
            audit(c, u["login"], "importou realizado e empenhado 2026",
                  detalhe=f"{arquivo.filename}: realizado {resumo['realizado_depois']}, empenhado {resumo['empenhado_depois']}")
    return resumo


# ---------------------------------------------------------------- resumo

@router.get("/resumo")
def resumo(u: dict = Depends(usuario_liberado), c: sqlite3.Connection = Depends(_conn)):
    ids = sorted(permitidos(c, u))
    marks = ",".join("?" for _ in ids) or "''"
    por_origem = c.execute(
        f"""SELECT CASE WHEN l.ciclo = {config.CICLO_BASE} THEN p.origem ELSE {ORIGEM_27} END AS origem, l.ciclo, SUM({SOMA_MESES}) t
            FROM linhas l JOIN projetos p USING (orcamento)
            WHERE l.orcamento IN ({marks}) GROUP BY 1, l.ciclo""", ids).fetchall()
    por_grupo = c.execute(
        f"""SELECT k.grupo, l.ciclo, SUM({SOMA_MESES}) t FROM linhas l JOIN contas k ON k.codigo=l.conta_codigo
            WHERE l.orcamento IN ({marks}) GROUP BY k.grupo, l.ciclo""", ids).fetchall()
    mensal = c.execute(
        f"SELECT {', '.join(f'SUM({m}) {m}' for m in MESES)} FROM linhas WHERE ciclo=? AND orcamento IN ({marks})",
        (config.CICLO_PLANO, *ids)).fetchone()

    exec_origem = c.execute(
        f"""SELECT p.origem AS nome, SUM(e.realizado) r, SUM(e.empenhado) em FROM execucao e JOIN projetos p USING (orcamento)
            WHERE e.orcamento IN ({marks}) GROUP BY p.origem""", ids).fetchall()
    exec_grupo = c.execute(
        f"""SELECT COALESCE(k.grupo, 'Sem conta contábil (folha e outros)') AS nome, SUM(e.realizado) r, SUM(e.empenhado) em
            FROM execucao e LEFT JOIN contas k ON k.codigo = e.conta_codigo
            WHERE e.orcamento IN ({marks}) GROUP BY nome""", ids).fetchall()

    def agrupar(rows, chave, execucao):
        out: dict[str, dict] = {}
        for r in rows:
            d = out.setdefault(r[chave], {"nome": r[chave], "base": 0.0, "plano": 0.0, "realizado": 0.0, "empenhado": 0.0})
            d["base" if r["ciclo"] == config.CICLO_BASE else "plano"] = _arred(r["t"])
        for r in execucao:
            d = out.setdefault(r["nome"], {"nome": r["nome"], "base": 0.0, "plano": 0.0, "realizado": 0.0, "empenhado": 0.0})
            d["realizado"], d["empenhado"] = _arred(r["r"] or 0), _arred(r["em"] or 0)
        for d in out.values():
            d["executado"] = _arred(d["realizado"] + d["empenhado"])
        return sorted(out.values(), key=lambda d: -max(d["plano"], d["base"]))

    origens, grupos = agrupar(por_origem, "origem", exec_origem), agrupar(por_grupo, "grupo", exec_grupo)
    tot = lambda lista, k: _arred(sum(x[k] for x in lista)) if lista else 0.0
    status = {"mantida": 0, "ajustada": 0, "nova": 0, "viagens": 0}
    for r in c.execute(
            f"SELECT l.fonte, l.base_id, {', '.join('l.' + m for m in MESES)}, {', '.join('b.' + m + ' AS b_' + m for m in MESES)} "
            f"FROM linhas l LEFT JOIN linhas b ON b.id = l.base_id WHERE l.ciclo=? AND l.orcamento IN ({marks})",
            (config.CICLO_PLANO, *ids)):
        if r["fonte"] == "viagens":
            status["viagens"] += 1
        elif r["base_id"] is None:
            status["nova"] += 1
        elif all(abs(r[m] - r["b_" + m]) < 0.005 for m in MESES):
            status["mantida"] += 1
        else:
            status["ajustada"] += 1
    return {"ciclo_base": config.CICLO_BASE, "ciclo_plano": config.CICLO_PLANO,
            "total_base": tot(origens, "base"), "total_plano": tot(origens, "plano"),
            "total_realizado": tot(origens, "realizado"), "total_empenhado": tot(origens, "empenhado"),
            "total_executado": tot(origens, "executado") if origens else 0.0,
            "linhas_status": status,
            "por_origem": origens, "por_grupo": grupos,
            "mensal_plano": [{"mes": NOMES_MESES[i], "valor": _arred(mensal[m] or 0)} for i, m in enumerate(MESES)]}


# ---------------------------------------------------------------- usuários (admin)

def _usuario_row(r: sqlite3.Row, c: sqlite3.Connection | None = None) -> dict:
    out = {"id": r["id"], "login": r["login"], "nome": r["nome"], "perfil": r["perfil"], "gerente": r["gerente"],
           "ativo": bool(r["ativo"]), "trocar_senha": bool(r["trocar_senha"]), "gerentes": [], "projetos": []}
    if c is not None:
        out["gerentes"] = [x[0] for x in c.execute("SELECT gerente FROM user_gerentes WHERE user_id=? ORDER BY gerente", (r["id"],))]
        out["projetos"] = [x[0] for x in c.execute("SELECT orcamento FROM user_projetos WHERE user_id=? ORDER BY orcamento", (r["id"],))]
        out["gerente"] = ", ".join(out["gerentes"])
    return out


@router.get("/usuarios")
def listar_usuarios(_: dict = Depends(exige_admin), c: sqlite3.Connection = Depends(_conn)):
    gerentes = [r[0] for r in c.execute("SELECT DISTINCT gerente FROM projetos ORDER BY gerente")]
    projetos = [{"orcamento": r["orcamento"], "descricao": r["descricao"], "gerente": r["gerente"]}
                for r in c.execute("SELECT orcamento, descricao, gerente FROM projetos ORDER BY orcamento")]
    return {"usuarios": [_usuario_row(r, c) for r in c.execute("SELECT * FROM users ORDER BY perfil, nome")],
            "gerentes": gerentes, "projetos": projetos}


def _grava_acessos(c: sqlite3.Connection, uid: int, gerentes: list[str] | None, projetos: list[str] | None) -> None:
    if gerentes is not None:
        gerentes = sorted({g.strip() for g in gerentes if g.strip()})
        c.execute("DELETE FROM user_gerentes WHERE user_id=?", (uid,))
        c.executemany("INSERT INTO user_gerentes (user_id, gerente) VALUES (?,?)", [(uid, g) for g in gerentes])
        c.execute("UPDATE users SET gerente=? WHERE id=?", (gerentes[0] if gerentes else None, uid))
    if projetos is not None:
        existentes = {r[0] for r in c.execute("SELECT orcamento FROM projetos")}
        c.execute("DELETE FROM user_projetos WHERE user_id=?", (uid,))
        c.executemany("INSERT INTO user_projetos (user_id, orcamento) VALUES (?,?)",
                      [(uid, o) for o in sorted(set(projetos) & existentes)])


@router.post("/usuarios", status_code=201)
def criar_usuario(dados: UsuarioIn, u: dict = Depends(exige_admin)):
    gerentes = dados.gerentes if dados.gerentes is not None else ([dados.gerente] if dados.gerente else [])
    if dados.perfil == "gestor" and not (gerentes or dados.projetos):
        raise HTTPException(422, "Informe ao menos um gerente de projetos ou um projeto que este gestor acompanha.")
    temp = security.senha_temporaria()
    with tx() as c:
        if c.execute("SELECT 1 FROM users WHERE login=?", (dados.login,)).fetchone():
            raise HTTPException(409, "Já existe um usuário com esse login.")
        cur = c.execute("INSERT INTO users (login, nome, senha_hash, perfil, trocar_senha) VALUES (?,?,?,?,1)",
                        (dados.login, dados.nome, security.hash_password(temp), dados.perfil))
        _grava_acessos(c, cur.lastrowid, gerentes, dados.projetos or [])
        audit(c, u["login"], "criou usuário", detalhe=f"{dados.login} ({dados.perfil})")
        row = c.execute("SELECT * FROM users WHERE id=?", (cur.lastrowid,)).fetchone()
        return {**_usuario_row(row, c), "senha_temporaria": temp}


@router.patch("/usuarios/{uid}")
def editar_usuario(uid: int, dados: UsuarioPatch, u: dict = Depends(exige_admin)):
    with tx() as c:
        alvo = c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        if not alvo:
            raise HTTPException(404, "Usuário não encontrado.")
        if uid == u["id"] and (dados.ativo is False or dados.perfil == "gestor"):
            raise HTTPException(400, "Você não pode desativar nem rebaixar o próprio acesso.")
        campos = dados.model_dump(exclude_none=True)
        gerentes, projetos = campos.pop("gerentes", None), campos.pop("projetos", None)
        if "ativo" in campos:
            campos["ativo"] = int(campos["ativo"])
        if campos:
            c.execute(f"UPDATE users SET {', '.join(k + '=?' for k in campos)} WHERE id=?", (*campos.values(), uid))
        _grava_acessos(c, uid, gerentes, projetos)
        perfil = campos.get("perfil", alvo["perfil"])
        if perfil == "gestor":
            tem = c.execute("SELECT (SELECT COUNT(*) FROM user_gerentes WHERE user_id=?) + "
                            "(SELECT COUNT(*) FROM user_projetos WHERE user_id=?)", (uid, uid)).fetchone()[0]
            if not tem:
                raise HTTPException(422, "Um gestor precisa acompanhar ao menos um gerente ou projeto.")
        audit(c, u["login"], "editou usuário", detalhe=f"{alvo['login']}: {dados.model_dump(exclude_none=True)}")
        return _usuario_row(c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone(), c)


@router.post("/usuarios/{uid}/reset-senha")
def resetar_senha(uid: int, u: dict = Depends(exige_admin)):
    temp = security.senha_temporaria()
    with tx() as c:
        alvo = c.execute("SELECT login FROM users WHERE id=?", (uid,)).fetchone()
        if not alvo:
            raise HTTPException(404, "Usuário não encontrado.")
        c.execute("UPDATE users SET senha_hash=?, trocar_senha=1 WHERE id=?", (security.hash_password(temp), uid))
        audit(c, u["login"], "redefiniu senha", detalhe=alvo["login"])
    return {"senha_temporaria": temp}


# ---------------------------------------------------------------- exportação e auditoria (admin)

def _aviso(a: export_xlsx.Aviso) -> dict:
    return {"nivel": a.nivel, "mensagem": a.mensagem, "orcamento": a.orcamento}


@router.get("/export/preflight")
def preflight(_: dict = Depends(exige_admin), c: sqlite3.Connection = Depends(_conn)):
    r = export_xlsx.preparar(c)
    return {"bloqueado": r.bloqueado, "linhas": len(r.linhas),
            "total": _arred(sum(sum(x["meses"]) for x in r.linhas)), "avisos": [_aviso(a) for a in r.avisos]}


@router.get("/export/xlsx")
def exportar(u: dict = Depends(exige_admin)):
    with tx() as c:
        r = export_xlsx.preparar(c)
        if r.bloqueado:
            raise HTTPException(409, "Há pendências que impedem a exportação. Veja a lista de conferência.")
        conteudo = export_xlsx.gerar(r.linhas)
        audit(c, u["login"], "exportou template", detalhe=f"{len(r.linhas)} linhas")
    nome = f"Planejamento_Anual_{config.CICLO_PLANO}_ESR_{datetime.now():%Y%m%d_%H%M}.xlsx"
    return StreamingResponse(iter([conteudo]),
                             media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f'attachment; filename="{nome}"'})


@router.get("/auditoria")
def ver_auditoria(limite: int = 200, _: dict = Depends(exige_admin), c: sqlite3.Connection = Depends(_conn)):
    rows = c.execute("SELECT * FROM auditoria ORDER BY id DESC LIMIT ?", (max(1, min(limite, 1000)),)).fetchall()
    return [dict(r) for r in rows]
