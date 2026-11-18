"""Fontes de financiamento dos projetos (sem dependências, para uso no api.py e no financiamento.py)."""
from __future__ import annotations

FOMENTO_ORIGENS = {"fomento", "fndct"}
FONTES = {
    "fomento": "Fomento",
    "intercompany": "Transferência intercompany",
    "receita": "Receita própria (externa)",
    "tbd": "A definir (TBD)",
    "": "Fonte não informada",
}
RESERVA = 0.05      # fundo de reserva (Diretrizes 2027)
ADMIN = 0.11        # operacional administrativo (Diretrizes 2027)


def retem_taxas(origem: str) -> bool:
    """Receitas plurianuais de RA e Associação têm 5% de fundo de reserva e 11% operacional administrativo."""
    o = (origem or "").strip().lower()
    return o.startswith("ra") or "associa" in o or "asrnp" in o


def liquida(total: float, origem: str) -> dict:
    if not retem_taxas(origem):
        return {"liquida": total, "reserva": 0.0, "admin": 0.0}
    return {"liquida": round(total * (1 - RESERVA - ADMIN), 2), "reserva": round(total * RESERVA, 2), "admin": round(total * ADMIN, 2)}


ORDEM = ["fomento", "intercompany", "receita", "tbd", ""]


def efetivo(origem: str, financiamento: str) -> str:
    """Fonte considerada para o projeto: a informada pelo gestor ou, se não houver, fomento quando a origem é de fomento."""
    if financiamento:
        return financiamento
    return "fomento" if (origem or "").strip().lower() in FOMENTO_ORIGENS else ""
