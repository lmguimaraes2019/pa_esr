"""Carga inicial: contas, projetos, base 2026, cópia para 2027, execução e usuários.

Uso:
    python -m app.seed --protheus Base.xlsx --template Template.xlsx --pa projetos_pa.xlsx [--reset]

As senhas iniciais são gravadas em data/senhas_iniciais.txt (somente leitura do dono) e nunca impressas.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import config, importers
from .db import MESES, init_db, tx, audit
from .security import hash_password, senha_temporaria


def seed(protheus: Path, template: Path, pa: Path, admin_login: str = "leandro",
         admin_nome: str = "Leandro Guimarães", admin_gerente: str = "Leandro Guimaraes",
         admin_senha: str | None = None, reset: bool = False) -> dict:
    init_db()
    df = importers.load_protheus(protheus)
    contas = importers.load_contas_template(template)
    contas_map = {c: d for c, d, _ in contas}
    projetos = importers.build_projetos(df, importers.load_projetos_pa(pa))
    base = importers.build_linhas_base(df, contas_map)
    execucao = importers.build_execucao(df)

    cols = ", ".join(MESES)
    marks = ", ".join("?" for _ in MESES)
    credenciais: list[tuple[str, str, str]] = []

    with tx() as c:
        if c.execute("SELECT COUNT(*) FROM projetos").fetchone()[0]:
            if not reset:
                raise SystemExit("O banco já tem dados. Use --reset para recarregar (apaga linhas e usuários).")
            for t in ("auditoria", "user_gerentes", "user_projetos", "linhas", "execucao", "projetos", "contas", "users"):
                c.execute(f"DELETE FROM {t}")

        c.executemany("INSERT INTO contas (codigo, descricao, grupo) VALUES (?,?,?)", contas)
        for p in projetos:
            c.execute("INSERT INTO projetos (orcamento, n_projeto, descricao, origem, gerente, original_2026) "
                      "VALUES (?,?,?,?,?,?)",
                      (p["orcamento"], p["n_projeto"], p["descricao"], p["origem"], p["gerente"], p["original_2026"]))

        for ln in base:
            cur = c.execute(
                f"INSERT INTO linhas (ciclo, orcamento, edt, tarefa, conta_codigo, {cols}, atualizado_por) "
                f"VALUES (?,?,?,?,?,{marks},?)",
                (config.CICLO_BASE, ln["orcamento"], ln["edt"], ln["tarefa"], ln["conta_codigo"],
                 *[ln[m] for m in MESES], "carga inicial"))
            c.execute(
                f"INSERT INTO linhas (ciclo, orcamento, edt, tarefa, conta_codigo, {cols}, base_id, atualizado_por) "
                f"VALUES (?,?,?,?,?,{marks},?,?)",
                (config.CICLO_PLANO, ln["orcamento"], ln["edt"], ln["tarefa"], ln["conta_codigo"],
                 *[ln[m] for m in MESES], cur.lastrowid, "carga inicial"))

        c.executemany(
            "INSERT OR REPLACE INTO execucao (orcamento, edt, tarefa, conta_codigo, realizado, empenhado) "
            "VALUES (:orcamento,:edt,:tarefa,:conta_codigo,:realizado,:empenhado)", execucao)

        # usuários: administrador + um gestor para cada gerente de projeto
        senha_admin = admin_senha or os.environ.get("ORC_ADMIN_PASSWORD") or senha_temporaria()
        c.execute("INSERT INTO users (login, nome, senha_hash, perfil, gerente, trocar_senha) VALUES (?,?,?,?,?,?)",
                  (admin_login, admin_nome, hash_password(senha_admin), "admin", admin_gerente,
                   0 if (admin_senha or os.environ.get("ORC_ADMIN_PASSWORD")) else 1))
        credenciais.append((admin_login, senha_admin, "admin"))
        c.execute("INSERT INTO user_gerentes (user_id, gerente) SELECT id, gerente FROM users WHERE login=?", (admin_login,))
        for gerente in sorted({p["gerente"] for p in projetos} - {admin_gerente}):
            login, senha = importers.login_de(gerente), senha_temporaria()
            c.execute("INSERT INTO users (login, nome, senha_hash, perfil, gerente, trocar_senha) VALUES (?,?,?,?,?,1)",
                      (login, gerente, hash_password(senha), "gestor", gerente))
            c.execute("INSERT INTO user_gerentes (user_id, gerente) SELECT id, gerente FROM users WHERE login=?", (login,))
            credenciais.append((login, senha, "gestor"))
        audit(c, "carga inicial", "seed", detalhe=f"{len(projetos)} projetos, {len(base)} linhas base")

    arq = config.DATA_DIR / "senhas_iniciais.txt"
    arq.write_text("login\tsenha temporária\tperfil\n" + "\n".join("\t".join(x) for x in credenciais) + "\n")
    arq.chmod(0o600)
    return {"projetos": len(projetos), "linhas_base": len(base), "execucao": len(execucao),
            "contas": len(contas), "usuarios": len(credenciais), "senhas": str(arq)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--protheus", required=True, type=Path)
    ap.add_argument("--template", required=True, type=Path)
    ap.add_argument("--pa", required=True, type=Path)
    ap.add_argument("--admin-login", default="leandro")
    ap.add_argument("--reset", action="store_true")
    a = ap.parse_args()
    r = seed(a.protheus, a.template, a.pa, admin_login=a.admin_login, reset=a.reset)
    print("Carga concluída:", {k: v for k, v in r.items()})
    print(f"Senhas iniciais em {r['senhas']} (apague o arquivo depois de repassá-las).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
