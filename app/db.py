"""Banco SQLite: esquema, conexão e transações."""
import sqlite3
from contextlib import contextmanager

from . import config

MESES = [f"m{i:02d}" for i in range(1, 13)]
NOMES_MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho",
               "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]

_COLS_MESES = ",\n    ".join(f"{m} REAL NOT NULL DEFAULT 0" for m in MESES)

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    login TEXT NOT NULL UNIQUE COLLATE NOCASE,
    nome TEXT NOT NULL,
    senha_hash TEXT NOT NULL,
    perfil TEXT NOT NULL CHECK (perfil IN ('admin','gestor')),
    gerente TEXT,
    ativo INTEGER NOT NULL DEFAULT 1,
    trocar_senha INTEGER NOT NULL DEFAULT 0,
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS projetos (
    orcamento TEXT PRIMARY KEY,
    n_projeto TEXT NOT NULL DEFAULT '',
    descricao TEXT NOT NULL,
    origem TEXT NOT NULL,
    gerente TEXT NOT NULL,
    diretoria TEXT NOT NULL DEFAULT 'ESR',
    original_2026 REAL NOT NULL DEFAULT 0,
    novo INTEGER NOT NULL DEFAULT 0,
    tipo TEXT NOT NULL DEFAULT 'despesa',
    origem_2027 TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS user_gerentes (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    gerente TEXT NOT NULL,
    PRIMARY KEY (user_id, gerente)
);

CREATE TABLE IF NOT EXISTS user_projetos (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    orcamento TEXT NOT NULL REFERENCES projetos(orcamento) ON DELETE CASCADE,
    PRIMARY KEY (user_id, orcamento)
);

CREATE TABLE IF NOT EXISTS contas (
    codigo TEXT PRIMARY KEY,
    descricao TEXT NOT NULL,
    grupo TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS linhas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ciclo INTEGER NOT NULL,
    orcamento TEXT NOT NULL REFERENCES projetos(orcamento),
    edt TEXT NOT NULL,
    tarefa TEXT NOT NULL,
    conta_codigo TEXT NOT NULL REFERENCES contas(codigo),
    {_COLS_MESES},
    base_id INTEGER,
    editada INTEGER NOT NULL DEFAULT 0,
    obs TEXT NOT NULL DEFAULT '',
    atualizado_por TEXT NOT NULL DEFAULT '',
    atualizado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_linhas_ciclo_orc ON linhas (ciclo, orcamento);

CREATE TABLE IF NOT EXISTS receitas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ciclo INTEGER NOT NULL,
    orcamento TEXT NOT NULL REFERENCES projetos(orcamento),
    fonte TEXT NOT NULL,
    descricao TEXT NOT NULL DEFAULT '',
    {_COLS_MESES},
    base_id INTEGER,
    obs TEXT NOT NULL DEFAULT '',
    tipo TEXT NOT NULL DEFAULT 'receita',
    ano INTEGER NOT NULL DEFAULT 2027,
    cliente TEXT NOT NULL DEFAULT '',
    origem_cliente TEXT NOT NULL DEFAULT '',
    gestor_cliente TEXT NOT NULL DEFAULT '',
    atualizado_por TEXT NOT NULL DEFAULT '',
    atualizado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_receitas_ciclo_orc ON receitas (ciclo, orcamento);

CREATE TABLE IF NOT EXISTS eventos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    orcamento TEXT NOT NULL REFERENCES projetos(orcamento),
    nome TEXT NOT NULL DEFAULT '',
    local TEXT NOT NULL DEFAULT '',
    tipo TEXT NOT NULL DEFAULT 'nac' CHECK (tipo IN ('nac','int')),
    mes INTEGER NOT NULL DEFAULT 1,
    n_pessoas INTEGER NOT NULL DEFAULT 1,
    dias INTEGER NOT NULL DEFAULT 1,
    pernoites INTEGER,
    inscricao REAL,
    moeda TEXT NOT NULL DEFAULT 'BRL' CHECK (moeda IN ('BRL','USD')),
    origem TEXT NOT NULL DEFAULT '',
    destino TEXT NOT NULL DEFAULT '',
    pessoas TEXT NOT NULL DEFAULT '[]',
    justificativa TEXT NOT NULL DEFAULT '',
    edt TEXT NOT NULL DEFAULT '',
    tarefa TEXT NOT NULL DEFAULT '',
    atualizado_por TEXT NOT NULL DEFAULT '',
    atualizado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS headcount (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    orcamento TEXT NOT NULL REFERENCES projetos(orcamento),
    funcao TEXT NOT NULL DEFAULT '',
    cargo TEXT NOT NULL DEFAULT '',
    trajetoria TEXT NOT NULL,
    nivel TEXT NOT NULL,
    grupo TEXT NOT NULL,
    posicao REAL NOT NULL DEFAULT 50,
    mes_inicio INTEGER NOT NULL DEFAULT 1,
    quantidade INTEGER NOT NULL DEFAULT 1,
    justificativa TEXT NOT NULL DEFAULT '',
    edt TEXT NOT NULL DEFAULT '',
    tarefa TEXT NOT NULL DEFAULT '',
    criado_por TEXT NOT NULL DEFAULT '',
    atualizado_por TEXT NOT NULL DEFAULT '',
    atualizado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS hc_parametros (chave TEXT PRIMARY KEY, valor REAL NOT NULL);

CREATE TABLE IF NOT EXISTS conclusoes (
    login TEXT PRIMARY KEY,
    concluido_em TEXT NOT NULL DEFAULT (datetime('now')),
    obs TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS meta (chave TEXT PRIMARY KEY, valor TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS execucao (
    orcamento TEXT NOT NULL,
    edt TEXT NOT NULL,
    tarefa TEXT NOT NULL,
    conta_codigo TEXT NOT NULL DEFAULT '',
    realizado REAL NOT NULL DEFAULT 0,
    empenhado REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (orcamento, edt, tarefa, conta_codigo)
);

CREATE TABLE IF NOT EXISTS premissas (
    chave TEXT PRIMARY KEY,
    valor REAL NOT NULL,
    descricao TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS viagem_tarifas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo TEXT NOT NULL CHECK (tipo IN ('nac','int')),
    origem TEXT NOT NULL,
    destino TEXT NOT NULL,
    passagem REAL NOT NULL DEFAULT 0,        -- ida e volta, valor de 2027 (editável)
    hospedagem REAL NOT NULL DEFAULT 0,      -- por pernoite
    bagagem REAL NOT NULL DEFAULT 0,         -- por viagem (só nacionais)
    aux_transporte REAL NOT NULL DEFAULT 0,  -- por viagem
    ajuda_custo REAL NOT NULL DEFAULT 0,     -- por dia
    seguro REAL NOT NULL DEFAULT 0,          -- por viagem (só internacionais)
    ref_passagem REAL NOT NULL DEFAULT 0,    -- valores de 2026, apenas referência
    ref_hospedagem REAL NOT NULL DEFAULT 0,
    ref_bagagem REAL NOT NULL DEFAULT 0,
    ref_aux_transporte REAL NOT NULL DEFAULT 0,
    ref_ajuda_custo REAL NOT NULL DEFAULT 0,
    ref_seguro REAL NOT NULL DEFAULT 0,
    UNIQUE (tipo, origem, destino)
);

CREATE TABLE IF NOT EXISTS viagens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ciclo INTEGER NOT NULL,
    tipo TEXT NOT NULL CHECK (tipo IN ('nac','int')),
    mes INTEGER NOT NULL CHECK (mes BETWEEN 1 AND 12),
    origem TEXT NOT NULL,
    destino TEXT NOT NULL,
    n_viagens INTEGER NOT NULL DEFAULT 1,
    dias INTEGER NOT NULL DEFAULT 1,
    pernoites INTEGER,                       -- vazio = dias - 1
    objetivo TEXT NOT NULL DEFAULT '',
    area TEXT NOT NULL DEFAULT '',
    orcamento TEXT,                          -- projeto que paga a viagem
    edt TEXT,                                -- tarefa do orçamento que recebe o valor
    tarefa TEXT,
    base_id INTEGER,
    atualizado_por TEXT NOT NULL DEFAULT '',
    atualizado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_viagens_ciclo ON viagens (ciclo, tipo);

CREATE TABLE IF NOT EXISTS auditoria (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    em TEXT NOT NULL DEFAULT (datetime('now')),
    usuario TEXT NOT NULL,
    acao TEXT NOT NULL,
    orcamento TEXT,
    linha_id INTEGER,
    detalhe TEXT NOT NULL DEFAULT ''
);
"""

PREMISSAS_PADRAO = [
    ("reajuste_pessoal", 0.0, "Reajuste de 2027 sobre a folha de pessoal (percentual, ex.: 5 para 5%)"),
    ("reajuste_geral", 0.0, "Reajuste de 2027 sobre os demais grupos de despesa (percentual)"),
    ("viagens_bagagem_vezes", 1.0, "Quantas vezes a franquia de bagagem entra no custo da viagem (a planilha de 2026 contou 2 no consolidado)"),
    ("dolar", 5.5, "Câmbio USD/BRL usado nas calculadoras (a planilha de parcerias usa 5,50)"),
]


def connect() -> sqlite3.Connection:
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH, timeout=15, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def tx():
    """Transação: confirma ao sair sem erro, desfaz se houver exceção."""
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with tx() as c:
        nova = not c.execute("SELECT 1 FROM sqlite_master WHERE name='user_gerentes'").fetchone()
        c.executescript(SCHEMA)
        if nova:      # migração: o gerente único de cada usuário vira a primeira entrada da lista
            c.execute("INSERT OR IGNORE INTO user_gerentes (user_id, gerente) "
                      "SELECT id, gerente FROM users WHERE gerente IS NOT NULL AND gerente <> ''")
        if "novo" not in {r[1] for r in c.execute("PRAGMA table_info(projetos)")}:      # migração: orçamentos criados no app
            c.execute("ALTER TABLE projetos ADD COLUMN novo INTEGER NOT NULL DEFAULT 0")
        if "tipo" not in {r[1] for r in c.execute("PRAGMA table_info(projetos)")}:      # migração: orçamento de despesa ou de receita
            c.execute("ALTER TABLE projetos ADD COLUMN tipo TEXT NOT NULL DEFAULT 'despesa'")
        if "origem_2027" not in {r[1] for r in c.execute("PRAGMA table_info(projetos)")}:   # migração: origem de recursos só do plano 2027
            c.execute("ALTER TABLE projetos ADD COLUMN origem_2027 TEXT NOT NULL DEFAULT ''")
        cols = {r[1] for r in c.execute("PRAGMA table_info(linhas)")}
        if "fonte" not in cols:      # migração: origem da linha ('manual' ou 'viagens')
            c.execute("ALTER TABLE linhas ADD COLUMN fonte TEXT NOT NULL DEFAULT 'manual'")
        for tabela in ("eventos", "headcount"):      # migração: tarefa do orçamento que recebe o valor
            tc = {r[1] for r in c.execute(f"PRAGMA table_info({tabela})")}
            for col in ("edt", "tarefa"):
                if col not in tc:
                    c.execute(f"ALTER TABLE {tabela} ADD COLUMN {col} TEXT NOT NULL DEFAULT ''")
        rc = {r[1] for r in c.execute("PRAGMA table_info(receitas)")}      # migração: transferência intercompany
        for col, ddl in (("tipo", "TEXT NOT NULL DEFAULT 'receita'"), ("ano", "INTEGER NOT NULL DEFAULT 2027"), ("cliente", "TEXT NOT NULL DEFAULT ''"),
                         ("origem_cliente", "TEXT NOT NULL DEFAULT ''"), ("gestor_cliente", "TEXT NOT NULL DEFAULT ''")):
            if col not in rc:
                c.execute(f"ALTER TABLE receitas ADD COLUMN {col} {ddl}")
        if "criado_por" not in {r[1] for r in c.execute("PRAGMA table_info(headcount)")}:      # migração: quem lançou a posição
            c.execute("ALTER TABLE headcount ADD COLUMN criado_por TEXT NOT NULL DEFAULT ''")
            c.execute("UPDATE headcount SET criado_por = atualizado_por")
        uc = {r[1] for r in c.execute("PRAGMA table_info(users)")}      # migração: gerência e cargo do usuário
        for col in ("gerencia", "cargo"):
            if col not in uc:
                c.execute(f"ALTER TABLE users ADD COLUMN {col} TEXT NOT NULL DEFAULT ''")
        semear_receitas(c)
        for chave, valor, desc in PREMISSAS_PADRAO:
            c.execute("INSERT OR IGNORE INTO premissas (chave, valor, descricao) VALUES (?,?,?)",
                      (chave, valor, desc))


def semear_receitas(c: sqlite3.Connection) -> bool:
    """Previsão de receita 2026 do Growth (R$ 500 mil por mês, aba 'Previsão Receita 2026' do consolidado) e a cópia de 2027.
    Roda uma única vez, quando o projeto existe."""
    if c.execute("SELECT 1 FROM meta WHERE chave='receitas_semeadas'").fetchone():
        return False
    p = c.execute("SELECT orcamento FROM projetos WHERE descricao LIKE '%ASSOCIACAO-GROWTH%' ORDER BY orcamento LIMIT 1").fetchone()
    if not p:
        return False
    cols = ", ".join(MESES)
    marks = ", ".join("?" for _ in MESES)
    base = c.execute(
        f"INSERT INTO receitas (ciclo, orcamento, fonte, descricao, {cols}, atualizado_por) VALUES (2026,?,?,?,{marks},?)",
        (p[0], "Growth", "Previsão de receita 2026", *[500000.0] * 12, "carga inicial")).lastrowid
    c.execute(
        f"INSERT INTO receitas (ciclo, orcamento, fonte, descricao, {cols}, base_id, atualizado_por) VALUES (2027,?,?,?,{marks},?,?)",
        (p[0], "Growth", "Previsão de receita 2026", *[500000.0] * 12, base, "carga inicial"))
    c.execute("INSERT INTO meta (chave, valor) VALUES ('receitas_semeadas', '1')")
    return True


def audit(c: sqlite3.Connection, usuario: str, acao: str, orcamento: str | None = None,
          linha_id: int | None = None, detalhe: str = "") -> None:
    c.execute("INSERT INTO auditoria (usuario, acao, orcamento, linha_id, detalhe) VALUES (?,?,?,?,?)",
              (usuario, acao, orcamento, linha_id, detalhe))
