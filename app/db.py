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
    original_2026 REAL NOT NULL DEFAULT 0
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
        c.executescript(SCHEMA)
        for chave, valor, desc in PREMISSAS_PADRAO:
            c.execute("INSERT OR IGNORE INTO premissas (chave, valor, descricao) VALUES (?,?,?)",
                      (chave, valor, desc))


def audit(c: sqlite3.Connection, usuario: str, acao: str, orcamento: str | None = None,
          linha_id: int | None = None, detalhe: str = "") -> None:
    c.execute("INSERT INTO auditoria (usuario, acao, orcamento, linha_id, detalhe) VALUES (?,?,?,?,?)",
              (usuario, acao, orcamento, linha_id, detalhe))
