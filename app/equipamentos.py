"""Catálogo de Hardware Homologado (Computação Pessoal, atualizado em 29/09/2026): valores de referência por equipamento.

O gestor escolhe, em cada posição de headcount, o computador, o monitor e o periférico. O custo é pontual: entra no mês
de início da posição, na conta Hardware, multiplicado pela quantidade de posições.
"""
from __future__ import annotations

import json

from . import config

CONTA_HARDWARE = "13010102"      # grupo Hardware ("Despesas de hardware HW / SJ" no chamado de aquisição)
ATUALIZADO_EM = "29/09/2026"

PADRAO = [
    {"codigo": "D1", "tipo": "computador", "nome": "Desktop Mini Intel Core i7 / 16GB / SSD 256GB / Win 11", "perfil": "Usuário Regular", "valor": 5320.00},
    {"codigo": "N2.A", "tipo": "computador", "nome": 'Notebook 14" Intel Core Ultra 7 / 16GB / SSD 512GB / Win 11', "perfil": "Usuário Intermediário", "valor": 6530.00},
    {"codigo": "N2.B", "tipo": "computador", "nome": 'Notebook 14" Intel Core Ultra 7 / 16GB / SSD 1TB / Win 11', "perfil": "Usuário Intermediário", "valor": 7203.00},
    {"codigo": "N3.A", "tipo": "computador", "nome": 'Notebook 14" Intel Core Ultra 7 / 32GB / SSD 1TB / Win 11', "perfil": "Usuário Avançado", "valor": 7520.00},
    {"codigo": "N3.B", "tipo": "computador", "nome": 'Notebook 15" Intel Core i7 / 32GB / SSD 1TB / RTX 3050 6GB / Win 11', "perfil": "Usuário Avançado", "valor": 8550.00},
    {"codigo": "N4", "tipo": "computador", "nome": "Apple MacBook Pro", "perfil": "Comunicação / Pesquisa (aprovado pela DE)", "valor": 26758.00},
    {"codigo": "N5.a", "tipo": "computador", "nome": "Dell Premium Pro", "perfil": "Diretor / Gerente de Equipe (aprovado pela DE)", "valor": 19244.00},
    {"codigo": "N5.b", "tipo": "computador", "nome": "Apple MacBook Air", "perfil": "Diretor (aprovado pela DE)", "valor": 21700.00},
    {"codigo": "M1", "tipo": "monitor", "nome": 'Monitor 23,8" Full HD', "perfil": "", "valor": 630.00},
    {"codigo": "M2", "tipo": "monitor", "nome": 'Monitor 27" Full HD', "perfil": "", "valor": 850.00},
    {"codigo": "DS1", "tipo": "periferico", "nome": "Dock Station USB-C", "perfil": "", "valor": 1219.00},
]
ARQUIVO = "catalogo_equipamentos.json"      # gravado em DATA_DIR quando o administrador importa um catálogo novo
_cache: dict = {"mtime": None, "dados": None}


def _arquivo():
    return config.DATA_DIR / ARQUIVO


def carregar() -> dict:
    """Catálogo vigente: o importado pelo administrador ou, se não houver, o padrão do sistema."""
    f = _arquivo()
    mtime = f.stat().st_mtime_ns if f.exists() else None
    if _cache["dados"] is None or _cache["mtime"] != mtime or _cache.get("pasta") != str(f):
        dados = json.loads(f.read_text(encoding="utf-8")) if mtime else {"atualizado_em": ATUALIZADO_EM, "itens": PADRAO, "origem": "padrão do sistema"}
        _cache.update(mtime=mtime, dados=dados, pasta=str(f))
    return _cache["dados"]


def gravar(itens: list[dict], atualizado_em: str, origem: str) -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    _arquivo().write_text(json.dumps({"atualizado_em": atualizado_em, "itens": itens, "origem": origem}, ensure_ascii=False, indent=1), encoding="utf-8")
    _cache["dados"] = None


def catalogo() -> list[dict]:
    return carregar()["itens"]


def item(codigo: str, tipo: str) -> dict | None:
    i = next((x for x in catalogo() if x["codigo"] == (codigo or "")), None)
    return i if i and i["tipo"] == tipo else None


def custo(computador: str, monitor: str, periferico: str) -> dict:
    itens = {t: item(c, t) for t, c in (("computador", computador), ("monitor", monitor), ("periferico", periferico))}
    por_tipo = {t: (i["valor"] if i else 0.0) for t, i in itens.items()}
    return {"itens": itens, "por_tipo": por_tipo, "total": round(sum(por_tipo.values()), 2)}
