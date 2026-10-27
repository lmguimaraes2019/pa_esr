"""Catálogo de Hardware Homologado (Computação Pessoal, atualizado em 29/09/2026): valores de referência por equipamento.

O gestor escolhe, em cada posição de headcount, o computador, o monitor e o periférico. O custo é pontual: entra no mês
de início da posição, na conta Hardware, multiplicado pela quantidade de posições.
"""
from __future__ import annotations

CONTA_HARDWARE = "13010102"      # grupo Hardware ("Despesas de hardware HW / SJ" no chamado de aquisição)
ATUALIZADO_EM = "29/09/2026"

CATALOGO = [
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
_POR_CODIGO = {i["codigo"]: i for i in CATALOGO}


def item(codigo: str, tipo: str) -> dict | None:
    i = _POR_CODIGO.get(codigo or "")
    return i if i and i["tipo"] == tipo else None


def custo(computador: str, monitor: str, periferico: str) -> dict:
    itens = {t: item(c, t) for t, c in (("computador", computador), ("monitor", monitor), ("periferico", periferico))}
    por_tipo = {t: (i["valor"] if i else 0.0) for t, i in itens.items()}
    return {"itens": itens, "por_tipo": por_tipo, "total": round(sum(por_tipo.values()), 2)}
