"""Conexão estratégica: hierarquia Diretriz > Resultado Estratégico (RE) > Resultado Operacional (RO, do Plano de Operação)
e os indicadores do Contrato de Gestão (CG/QIM).

Os códigos carregam a hierarquia: RO 7.1.1 pertence ao RE 7.1, que pertence à Diretriz 7. Cada RO aponta para o indicador do CG
que ele move (campo `indicador`, o código do item 'cg'). Vincular um orçamento a um item vincula também a tudo o que está acima dele.
"""
from __future__ import annotations

import re
import sqlite3

CAMPOS_EXTRA = ("objetivo", "indicador", "conclusao", "responsavel", "fomento", "lider")
ROTULO_TIPO = {"diretriz": "Diretriz", "re": "RE", "po": "RO", "cg": "CG"}
ORDEM_TIPO = {"diretriz": 0, "re": 1, "po": 2, "cg": 3}


def numero(codigo: str) -> str:
    """Parte numérica do código ('RC 6.1.2' e '6.1.2' dão '6.1.2')."""
    m = re.search(r"\d+(?:\.\d+)*", codigo or "")
    return m.group(0) if m else ""


def gravar(c: sqlite3.Connection, itens: list[dict]) -> dict:
    """Insere ou atualiza (pela chave tipo+código). Campos opcionais vazios não apagam o que já está gravado."""
    atuais = {(r["tipo"], r["codigo"].upper()): r for r in c.execute("SELECT * FROM estrategia")}
    novos = alterados = 0
    for x in itens:
        a = atuais.get((x["tipo"], x["codigo"].upper()))
        extras = {k: (x.get(k) or "").strip()[:1000] for k in CAMPOS_EXTRA}
        if a:
            campos = {"codigo": x["codigo"], "descricao": x["descricao"], "meta": x.get("meta") or a["meta"]}
            campos.update({k: v or a[k] for k, v in extras.items()})
            if any(campos[k] != a[k] for k in campos):
                c.execute(f"UPDATE estrategia SET {', '.join(k + '=?' for k in campos)} WHERE id=?", (*campos.values(), a["id"]))
                alterados += 1
        else:
            c.execute(f"INSERT INTO estrategia (tipo, codigo, descricao, meta, {', '.join(CAMPOS_EXTRA)}) VALUES (?,?,?,?,{','.join('?' for _ in CAMPOS_EXTRA)})",
                      (x["tipo"], x["codigo"], x["descricao"], x.get("meta") or "", *extras.values()))
            novos += 1
    return {"novos": novos, "alterados": alterados}


def arvore(c: sqlite3.Connection) -> list[dict]:
    """Catálogo completo, em ordem de leitura (diretriz, RE, RO, depois os indicadores do CG), com os ids dos pais."""
    linhas = [dict(r) for r in c.execute("SELECT * FROM estrategia")]
    por_num = {(r["tipo"], numero(r["codigo"])): r["id"] for r in linhas}
    for r in linhas:
        partes = numero(r["codigo"]).split(".")
        pais = []
        if r["tipo"] == "po":
            if len(partes) >= 3 and ("re", ".".join(partes[:2])) in por_num:
                pais.append(por_num[("re", ".".join(partes[:2]))])
        if r["tipo"] in ("po", "re") and ("diretriz", partes[0]) in por_num and (r["tipo"] == "re" or len(partes) >= 2):
            pais.append(por_num[("diretriz", partes[0])])
        if r["tipo"] == "po" and numero(r["indicador"]) and ("cg", numero(r["indicador"])) in por_num:
            pais.append(por_num[("cg", numero(r["indicador"]))])
        r["pais"] = pais       # tudo o que fica "coberto" quando este item é vinculado
    def chave(r):
        nums = tuple(int(x) for x in numero(r["codigo"]).split(".") if x)
        return (r["tipo"] == "cg", nums or (9999,), r["codigo"])
    return sorted(linhas, key=chave)


def fecho(catalogo: list[dict], ids: set[int]) -> set[int]:
    """Os itens vinculados e todos os que estão acima deles na hierarquia (inclusive o indicador do CG do RO)."""
    por_id = {r["id"]: r for r in catalogo}
    out, fila = set(), list(ids & por_id.keys())
    while fila:
        i = fila.pop()
        if i in out:
            continue
        out.add(i)
        fila.extend(por_id[i]["pais"])
    return out


# ---------------------------------------------------------------- carga inicial: PO 2027 da ESR (Diretriz 7)

def _ro(cod, enun, obj, metrica, qim, concl, resp, fomento):
    return {"tipo": "po", "codigo": cod, "descricao": enun, "objetivo": obj, "meta": metrica, "indicador": qim, "conclusao": concl, "responsavel": resp, "fomento": fomento}


PO_2027 = [
    {"tipo": "cg", "codigo": "10", "descricao": "Índice de Desenvolvimento da Capacitação", "meta": "Indicador QIM 10"},
    {"tipo": "diretriz", "codigo": "7", "descricao": "Desenvolver competências digitais no Sistema RNP",
     "objetivo": "Ajustar a atuação formativa da RNP ao momento dos programas estruturantes, equilibrando fomento ordinário, extraordinário e extra fomento; concluir o mapeamento de "
                 "competências, consolidar as trilhas em dados e IA e incorporar ao portfólio da ESR os produtos de programas próprios, como o Hackers do Bem."},
    {"tipo": "re", "codigo": "7.1", "descricao": "Atuação formativa da RNP dimensionada às demandas dos programas estruturantes",
     "lider": "Leandro Guimaraes (par: Luciana Santos) | Saleta: ESR e Hackers do Bem"},
    {"tipo": "re", "codigo": "7.2", "descricao": "Produtos e o modelo de oferta construídos pelo programa Hackers do Bem consolidados, compondo o portfólio da ESR de forma continuada e sustentável",
     "lider": "Leandro Guimaraes (par: Luciana Santos) | Saleta: ESR e Hackers do Bem"},
    _ro("7.1.1", "Mapeamento de competências das instituições participantes concluído no âmbito do CapacitaRH",
        "Utilização mais assertiva das vagas financiadas a partir do mapeamento de competências realizado pela consultoria educacional no programa CapacitaRH.",
        "Instituições participantes com mapeamento concluído, de 88 (final de 2026) para [a definir], até Q3 de 2027.", "10", "Q3", "ESR", "CG/Fomento Ordinário | termo aditivo a definir"),
    _ro("7.1.2", "Programa IA para Todos lançado, com jornada formativa síncrona e assíncrona ofertada em plataforma própria",
        "Ampliação do acesso a ações estruturadas de formação em inteligência artificial e dados.",
        "64 mil vagas ofertadas na jornada formativa do programa, até Q3 de 2027.", "10", "Q3", "ESR", "CG/Fomento Extraordinário | FNDCT | 36º TA"),
    _ro("7.1.3", "Capacitação em TIC avançadas ofertada por parcerias da ESR",
        "Ampliação da capacidade de oferta de capacitação em TIC avançadas com maior agilidade de entrada no mercado.",
        "Cursos de TIC avançadas ofertados por meio de parcerias, de [baseline a definir] para [target a definir].", "10", "Q3", "ESR", "CG/Fomento Ordinário | programa institucional AsRNP"),
    _ro("7.1.4", "Carreiras de Dados e Inteligência Artificial da ESR consolidadas, com trilhas em operação",
        "Ampliação e fortalecimento da oferta estruturada de formação em Dados e Inteligência Artificial no portfólio da ESR.",
        "Trilhas formativas em operação nas Carreiras de Dados e IA, de [baseline a definir] para [target a definir].", "10", "Q3", "ESR", "CG/Fomento Ordinário | programa institucional AsRNP"),
    _ro("7.1.5", "Trilha de desenvolvimento full-stack em operação",
        "Ampliação da oferta de formação estruturada em desenvolvimento full-stack.",
        "Trilhas de desenvolvimento full-stack em operação, de [baseline a definir] para [target a definir].", "10", "Q3", "ESR", "CG/Fomento Extraordinário | FNDCT | 36º TA"),
    _ro("7.1.6", "Trilhas de capacitação do SIG-PPSI operacionalizadas pela ESR, a partir das demandas da DACS, em parceria com o MGI",
        "Ampliar a capacidade de oferta formativa da RNP para atender às demandas de capacitação, apoiando o desenvolvimento de competências relacionadas ao PPSI.",
        "Vagas ofertadas nas trilhas de capacitação do SIG-PPSI, de [baseline a definir] para [target a definir], em 2027.", "10", "Q3", "ESR", "CG/Fomento Ordinário | programa institucional AsRNP"),
    _ro("7.2.1", "Hackers do Bem relançado e consolidado nacionalmente, com desafios regionais",
        "Sustentação perene do programa Hackers do Bem em alcance nacional.",
        "Desafios regionais realizados e modelo sustentável definido para execução perene do programa.", "", "Q3", "DPDI", "AsRNP | Lei de Informática PPI"),
    _ro("7.2.2", "Produtos do Hackers do Bem incorporados ao portfólio da ESR",
        "Ampliação e atualização do portfólio da ESR a partir dos conteúdos desenvolvidos no programa Hackers do Bem.",
        "Produtos do Hackers do Bem 2.0 incorporados ao portfólio da ESR, de [baseline a definir] para [target a definir].", "10", "Q3", "ESR", "AsRNP | Lei de Informática PPI"),
    _ro("7.2.3", "Modelo de negócio definido para a oferta sustentável dos produtos oriundos dos GTs do Hackers do Bem",
        "Viabilizar a oferta continuada e sustentável dos produtos oriundos dos GTs do Hackers do Bem no portfólio da ESR.",
        "Modelo de negócio para a oferta dos produtos dos GTs, de não definido para definido, até Q3 de 2027.", "", "Q3", "DPDI", "AsRNP | Lei de Informática PPI"),
]


def semear_po(c: sqlite3.Connection) -> bool:
    """Carrega uma única vez o PO 2027 da Diretriz 7 (ESR). O administrador atualiza e amplia depois pela importação."""
    if c.execute("SELECT 1 FROM meta WHERE chave='po2027_semeado'").fetchone():
        return False
    gravar(c, PO_2027)
    c.execute("INSERT INTO meta (chave, valor) VALUES ('po2027_semeado', '1')")
    return True
