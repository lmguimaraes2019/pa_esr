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
ORIGENS_DIRETRIZ = {
    "fomento": "CG/Fomento Ordinários (001)", "fndct": "CG/Fomento Ordinários (001)",
    "ra": "CG/Fomento Extraordinários (003)",
    "associacao": "AsRNP (020)", "conv": "AsRNP CONV (010)",
}


def origem_diretriz(origem: str, conv: bool = False) -> str:
    """Origem segundo as Diretrizes 2027. O template do PMO segue com as origens antigas; Associação é AsRNP, salvo marcação CONV."""
    o = (origem or "").strip().lower().replace("ç", "c").replace("ã", "a")
    if o.startswith("associa"):
        return ORIGENS_DIRETRIZ["conv" if conv else "associacao"]
    return ORIGENS_DIRETRIZ.get(o, origem or "")


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


def lista_fontes(c) -> list[dict]:
    """Fontes cadastradas (as quatro de base e as criadas pelo administrador), em ordem."""
    return [{"codigo": r[0], "nome": r[1], "sistema": bool(r[2])} for r in c.execute("SELECT codigo, nome, sistema FROM fontes_financiamento ORDER BY ordem, codigo")]


ORDEM = ["fomento", "intercompany", "receita", "tbd", ""]


def efetivo(origem: str, financiamento: str) -> str:
    """Fonte considerada para o projeto: a informada pelo gestor ou, se não houver, fomento quando a origem é de fomento."""
    if financiamento:
        return financiamento
    return "fomento" if (origem or "").strip().lower() in FOMENTO_ORIGENS else ""
