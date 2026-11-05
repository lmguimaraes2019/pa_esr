"""Mostra, projeto a projeto, o que o app considera pendência para um usuário.

Uso na VPS:  docker compose exec app python -m app.diagnostico_pendencias sandro
"""
from __future__ import annotations

import sys

from . import api, api_planejamento as pl
from .db import connect


def main(login: str) -> int:
    c = connect()
    u = c.execute("SELECT * FROM users WHERE login=?", (login,)).fetchone()
    if not u:
        print(f"Usuário {login!r} não existe.")
        return 1
    u = dict(u)
    ids = sorted(api.permitidos(c, u))
    via_gerente = [r[0] for r in c.execute("SELECT gerente FROM user_gerentes WHERE user_id=?", (u["id"],))]
    via_projeto = [r[0] for r in c.execute("SELECT orcamento FROM user_projetos WHERE user_id=?", (u["id"],))]
    print(f"{u['nome']} | cargo {u['cargo']} | enxerga {len(ids)} projeto(s)")
    print(f"  por gerente : {', '.join(via_gerente) or '-'}")
    print(f"  por projeto : {', '.join(via_projeto) or '-'}")
    print()
    total = 0
    for p in pl._situacao(c, u)["projetos"]:
        motivos = []
        for k in ("viagens", "eventos", "headcount"):
            if p[k]["pendentes"]:
                motivos.append(f"{p[k]['pendentes']} item(ns) de {k} incompleto(s)")
        if p["entregas"]["pendentes"]:
            motivos.append(f"entregas: {p['entregas']['motivo']}")
        total += p["pendencias"]
        print(f"{p['orcamento']:>8} | gerente {p['gerente']:<24} | plano {p['despesas']['plano']:>14,.2f} | "
              f"{'; '.join(motivos) or 'sem pendência'}")
    print(f"\nTotal de pendências na visão de {login}: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else ""))
