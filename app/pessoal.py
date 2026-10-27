"""Custo de uma contratação (headcount): faixas salariais (Tabela Salarial 2025) e fórmulas da planilha CUSTO_PESSOAL."""
from __future__ import annotations

import json
import sqlite3
from functools import lru_cache

from . import config

# Parâmetros da planilha CUSTO_PESSOAL - ESR - Agosto 2026 (aba Agosto_26, linha modelo). Editáveis pelo administrador.
PARAMETROS = {
    "rat": (2.4044, "RAT ajustado (%) somado a 20% de INSS patronal e 4,5% de terceiros. A planilha usa 2,4044% (total 26,9044%); o alternativo é 1%"),
    "fgts": (8.0, "FGTS (% do salário)"),
    "pis": (1.0, "PIS (% do salário)"),
    "vr_dia": (35.0, "VR/VA por dia (R$)"),
    "vr_dias": (22.0, "Dias de VR/VA no mês"),
    "vr_extra": (299.77, "Complemento fixo do VR/VA (R$)"),
    "vt": (0.0, "Vale-transporte (R$ por mês)"),
    "plano_saude": (1208.5158888888889, "Plano de saúde e odontológico, média (R$ por mês)"),
    "seguro_vida": (0.5811, "Seguro de vida (% do salário)"),
    "internet": (100.0, "Ajuda de custo de internet (R$ por mês)"),
}


ARQUIVO_TABELA = "tabela_salarial.json"      # gravado em DATA_DIR quando o administrador importa uma tabela nova
_tab: dict = {"chave": None, "dados": None}


def _meta_tabela() -> dict:
    f = config.DATA_DIR / ARQUIVO_TABELA
    if f.exists():
        d = json.loads(f.read_text(encoding="utf-8"))
        return {"faixas": d["faixas"], "nome": d.get("nome", "Tabela Salarial importada"), "origem": "importada"}
    return {"faixas": json.loads((config.ASSETS_DIR / "tabela_salarial_2025.json").read_text(encoding="utf-8")),
            "nome": "Tabela Salarial 2025", "origem": "padrão do sistema"}


def tabela_info() -> dict:
    f = config.DATA_DIR / ARQUIVO_TABELA
    chave = (str(f), f.stat().st_mtime_ns if f.exists() else None)
    if _tab["chave"] != chave:
        _tab.update(chave=chave, dados=_meta_tabela())
    return _tab["dados"]


def tabela_salarial() -> list[dict]:
    return tabela_info()["faixas"]


def gravar_tabela(faixas: list[dict], nome: str) -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    (config.DATA_DIR / ARQUIVO_TABELA).write_text(json.dumps({"nome": nome, "faixas": faixas}, ensure_ascii=False, indent=1), encoding="utf-8")
    _tab["chave"] = None


def faixa(trajetoria: str, nivel: str, grupo: str) -> dict | None:
    for f in tabela_salarial():
        if (f["trajetoria"], f["nivel"], f["grupo"]) == (trajetoria, nivel, grupo):
            return f
    return None


def parametros(c: sqlite3.Connection) -> dict[str, float]:
    p = {k: v[0] for k, v in PARAMETROS.items()}
    for r in c.execute("SELECT chave, valor FROM hc_parametros"):
        if r["chave"] in p:
            p[r["chave"]] = float(r["valor"])
    return p


def salario_na_faixa(f: dict, posicao: float) -> float:
    """posicao 0 = início da faixa (80%), 100 = fim da faixa (120%), 50 = ponto médio."""
    pos = min(max(float(posicao), 0.0), 100.0)
    return round(f["inicio"] + (f["fim"] - f["inicio"]) * pos / 100.0, 2)


def custo_mensal(salario: float, p: dict[str, float]) -> dict[str, float]:
    """As mesmas fórmulas das colunas K a Y da planilha."""
    j = salario
    inss = j * (20.0 + 4.5 + p["rat"]) / 100
    fgts = j * p["fgts"] / 100
    pis = j * p["pis"] / 100
    encargos = j + inss + fgts + pis                                     # N
    vr = p["vr_dia"] * p["vr_dias"] + p["vr_extra"]                      # O
    seguro = j * p["seguro_vida"] / 100                                  # R
    beneficios = vr + p["vt"] + p["plano_saude"] + seguro + p["internet"]  # T
    abono = (j / 30 * 10) / 12                                           # U
    ferias = ((j / 12) + abono) / 3                                      # V
    decimo = j / 12                                                      # W
    provisoes = abono + ferias + decimo                                  # X
    total = beneficios + encargos + provisoes                            # Y
    return {"salario": round(j, 2), "inss": round(inss, 2), "fgts": round(fgts, 2), "pis": round(pis, 2),
            "vr": round(vr, 2), "vt": round(p["vt"], 2), "plano_saude": round(p["plano_saude"], 2), "seguro_vida": round(seguro, 2),
            "internet": round(p["internet"], 2), "provisao_ferias": round(abono + ferias, 2), "provisao_13": round(decimo, 2),
            "salario_encargos": round(encargos, 2), "beneficios": round(beneficios, 2), "provisoes": round(provisoes, 2),
            "mensal": round(total, 2), "anual": round(total * 12, 2)}
