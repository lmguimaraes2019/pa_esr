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
ORDEM = ["fomento", "intercompany", "receita", "tbd", ""]


def efetivo(origem: str, financiamento: str) -> str:
    """Fonte considerada para o projeto: a informada pelo gestor ou, se não houver, fomento quando a origem é de fomento."""
    if financiamento:
        return financiamento
    return "fomento" if (origem or "").strip().lower() in FOMENTO_ORIGENS else ""
