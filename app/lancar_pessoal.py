"""Lança no plano 2027 as linhas de pessoal (headcount) da planilha ESR_ORÇAMENTO_PESSOAL_2027, aba PA2027_ESR.

Uso (na VPS):  docker compose exec app python -m app.lancar_pessoal            (confere e mostra o que seria lançado)
               docker compose exec app python -m app.lancar_pessoal --gravar   (grava)
               docker compose exec app python -m app.lancar_pessoal --gravar --refazer   (apaga só a carga anterior e regrava)

Critérios:
- cada linha da planilha vira uma linha do projeto, sem alterar nome (coluna "Linha de despesa"), conta contábil nem os 12 valores mensais;
- EDT = modalidade (CLT, ESTAGIARIO INT); tarefa = linha de despesa; observação = diretoria, gestor, centro de custo e descrição original;
- as linhas de DSS-ESR-ASSOCIACAO-PESSOAL da planilha entram no projeto DSS-ESR-RA-PESSOAL do app;
- só grava se os três projetos forem encontrados (pelo nome, sem acento, hífen ou espaço) e estiverem sem linhas;
- nada é gravado se qualquer conferência falhar.
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata

from . import config
from .db import MESES, audit, tx

AUTOR = "carga pessoal 2027"
ARQUIVO = config.ASSETS_DIR / "carga_pessoal_2027.json"
# descrição na planilha -> nome do projeto no app
DESTINO = {
    "DSS-ESR-FOMENTO-PESSOAL": "DSS-ESR-FOMENTO-PESSOAL",
    "DSS-ESR-ASSOCIACAO-PESSOAL": "DSS-ESR-RA-PESSOAL",
    "DSS-ESR-ASSOCIACAO-HACKER DO BEM PESSOAL": "DSS-ESR-ASSOCIACAO-HACKER DO BEM-PESSOAL",
}


def chave(txt: str) -> str:
    s = unicodedata.normalize("NFKD", txt or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Z0-9]", "", s.upper())


def carregar() -> list[dict]:
    return json.loads(ARQUIVO.read_text(encoding="utf-8"))


def executar(c, gravar: bool = False, refazer: bool = False, saida=print) -> int:
    itens = carregar()
    erros = []
    projetos = c.execute("SELECT orcamento, descricao, origem, gerente FROM projetos WHERE tipo='despesa'").fetchall()
    destino = {}
    for orig, nome_app in DESTINO.items():
        achados = [p for p in projetos if chave(p["descricao"]) == chave(nome_app)]
        if len(achados) != 1:
            erros.append(f"'{nome_app}' (planilha: {orig}): {len(achados)} projeto(s) encontrado(s) no app. Candidatos com PESSOAL no nome: "
                         + "; ".join(f"{p['orcamento']} {p['descricao']}" for p in projetos if "PESSOAL" in p["descricao"].upper()))
        else:
            destino[orig] = achados[0]
    for conta in {i["conta"] for i in itens}:
        if not c.execute("SELECT 1 FROM contas WHERE codigo=?", (conta,)).fetchone():
            erros.append(f"Conta {conta} fora da lista do template.")
    for i in itens:
        if abs(sum(i["meses"]) - i["total"]) > 0.01:
            erros.append(f"Linha {i['descricao']} / {i['linha']}: os meses não somam o total da planilha.")
    ja = {}
    for orig, p in destino.items():
        n, nossa = c.execute("SELECT COUNT(*), COALESCE(SUM(atualizado_por=?),0) FROM linhas WHERE ciclo=? AND orcamento=?",
                             (AUTOR, config.CICLO_PLANO, p["orcamento"])).fetchone()
        ja[orig] = (n, nossa)
        if n - nossa > 0:
            erros.append(f"{p['orcamento']} {p['descricao']} já tem {n - nossa} linha(s) lançada(s) por outros. Nada foi alterado.")
        if nossa and not refazer:
            erros.append(f"{p['orcamento']} já recebeu esta carga ({nossa} linhas). Use --refazer para apagar só essas linhas e lançar de novo.")
    total = sum(i["total"] for i in itens)
    for orig in DESTINO:
        sel = [i for i in itens if i["descricao"] == orig]
        p = destino.get(orig)
        saida(f"{orig} -> {p['orcamento'] + ' ' + p['descricao'] + ' (' + p['origem'] + ', ' + p['gerente'] + ')' if p else 'NÃO ENCONTRADO'}: "
              f"{len(sel)} linhas, R$ {sum(i['total'] for i in sel):,.2f}")
    saida(f"Total 2027: R$ {total:,.2f} em {len(itens)} linhas")
    sem = [i for i in itens if i["descricao"] not in DESTINO]
    if sem:
        erros.append(f"{len(sem)} linha(s) da planilha sem projeto de destino: {sorted({i['descricao'] for i in sem})}")
    if erros:
        for e in erros:
            saida("ERRO: " + e)
        return 1
    if not gravar:
        saida("Conferido. Nada gravado. Use --gravar para lançar.")
        return 0
    for orig, p in destino.items():
        if ja[orig][1]:
            c.execute("DELETE FROM linhas WHERE ciclo=? AND orcamento=? AND atualizado_por=?", (config.CICLO_PLANO, p["orcamento"], AUTOR))
    for i in itens:
        p = destino[i["descricao"]]
        obs = f"{i['diretoria']} | {i['gestor']} | Centro de custo {i['centro_custo']} | Planilha: {i['descricao']}"
        c.execute(f"INSERT INTO linhas (ciclo, orcamento, edt, tarefa, conta_codigo, {', '.join(MESES)}, editada, obs, atualizado_por) "
                  f"VALUES (?,?,?,?,?,{', '.join('?' for _ in MESES)},1,?,?)",
                  (config.CICLO_PLANO, p["orcamento"], i["modalidade"], i["linha"], i["conta"], *i["meses"], obs, AUTOR))
    for orig, p in destino.items():
        sel = [i for i in itens if i["descricao"] == orig]
        audit(c, AUTOR, "carga de pessoal 2027", p["orcamento"], detalhe=f"{len(sel)} linhas, R$ {sum(i['total'] for i in sel):,.2f}")
    saida("Gravado.")
    return 0


def main(argv: list[str]) -> int:
    with tx() as c:
        return executar(c, "--gravar" in argv, "--refazer" in argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
