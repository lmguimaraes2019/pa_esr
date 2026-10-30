"""Lança no plano 2027 o orçamento 7016 (DSS-ESR-FNDCT-IA PARA TODOS), a partir da planilha do programa.

Uso (na VPS):  docker compose exec app python -m app.lancar_7016            (mostra o que seria lançado)
               docker compose exec app python -m app.lancar_7016 --gravar   (grava)
               docker compose exec app python -m app.lancar_7016 --gravar --refazer   (apaga a carga anterior e regrava)

Critérios:
- vale o valor "Estimativa de custo" de 36 meses; sem a taxa de reserva da RNP (16%);
- 2027 recebe 1/3 do total de cada item, distribuído por igual nos 12 meses;
- headcounts (inclusive a execução das aulas) ficam de fora, serão lançados depois pela página Headcount.
"""
from __future__ import annotations

import sys

from . import config
from .db import MESES, audit, tx

ORC = "7016"
AUTOR = "carga 7016"
ANOS = 3

# (meta, ação, item da planilha, conta contábil, estimativa de 36 meses)
ITENS = [
    ("01-GOVERNANCA", "01.01-MARKETING E COMUNICACAO", "Serviço de redes sociais", "51030703", 472000.00),
    ("01-GOVERNANCA", "01.01-MARKETING E COMUNICACAO", "Branding (marca, brandbook, universo visual e verbal)", "51030703", 120000.00),
    ("01-GOVERNANCA", "01.01-MARKETING E COMUNICACAO", "Landing page", "51040149", 15000.00),
    ("01-GOVERNANCA", "01.01-MARKETING E COMUNICACAO", "Materiais gráficos (design)", "51030701", 30000.00),
    ("01-GOVERNANCA", "01.01-MARKETING E COMUNICACAO", "Vídeo institucional", "51030704", 120000.00),
    ("01-GOVERNANCA", "01.02-CRM E MIDIA PAGA", "CRM (RD Station)", "51030603", 442000.00),
    ("01-GOVERNANCA", "01.02-CRM E MIDIA PAGA", "Mídia paga: plano e peças", "51030703", 48000.00),
    ("01-GOVERNANCA", "01.02-CRM E MIDIA PAGA", "Mídia paga: investimento", "51030703", 115000.00),
    ("01-GOVERNANCA", "01.03-VIAGENS", "Viagens nacionais", "51030504", 150000.00),
    ("01-GOVERNANCA", "01.03-VIAGENS", "Viagens internacionais", "51030513", 150000.00),

    ("02-CAPACITACAO", "02.01-CONTEUDO EM IA", "Desenvolvimento de conteúdo em IA (trilhas assíncronas e práticas)", "51040145", 6082000.00),

    ("03-INFRAESTRUTURA", "03.01-NUVEM E LABORATORIOS", "Contratação de HPC na nuvem", "51030603", 8523162.04),
    ("03-INFRAESTRUTURA", "03.01-NUVEM E LABORATORIOS", "Laboratório virtualizado", "51030603", 2860428.65),
    ("03-INFRAESTRUTURA", "03.01-NUVEM E LABORATORIOS", "Infraestrutura em nuvem para P&D", "51030603", 1200000.00),
    ("03-INFRAESTRUTURA", "03.02-EQUIPES E FABRICA DE SOFTWARE", "Equipe de projeto", "51040149", 4990901.98),
    ("03-INFRAESTRUTURA", "03.02-EQUIPES E FABRICA DE SOFTWARE", "Equipe de sustentação", "51040149", 921974.61),
    ("03-INFRAESTRUTURA", "03.02-EQUIPES E FABRICA DE SOFTWARE", "Equipe de segurança da informação", "51040149", 889046.94),
    ("03-INFRAESTRUTURA", "03.02-EQUIPES E FABRICA DE SOFTWARE", "Serviços de fábrica de software", "51040149", 3938737.26),
    ("03-INFRAESTRUTURA", "03.03-SEGURANCA E SERVICOS", "Serviços de segurança da informação e privacidade", "51040149", 330750.00),
    ("03-INFRAESTRUTURA", "03.03-SEGURANCA E SERVICOS", "Serviços de nuvem", "51030603", 5471250.00),
    ("03-INFRAESTRUTURA", "03.03-SEGURANCA E SERVICOS", "Outros serviços", "51040145", 171396.00),

    ("05-P&D", "05.01-HACKATHONS TEMATICOS", "Hackathons temáticos (1 por ano, R$ 235.641,00 cada)", "51040135", 706923.00),
    ("05-P&D", "05.02-PROGRAMAS DE P&D", "Programa P&D externo (soluções de IA para ensino de IA)", "51040138", 12026111.84),
    ("05-P&D", "05.02-PROGRAMAS DE P&D", "Programa P&D híbrido (middleware de capacidades de IA)", "51040138", 7794490.31),
    ("05-P&D", "05.03-WORKSHOPS SOBRE FORMACAO EM IA", "Workshops sobre formação em IA (1 por ano, R$ 237.342,00 cada)", "51040135", 712026.00),

    ("06-RESIDENCIA", "06.01-INFRAESTRUTURA", "Contratação de HPC na nuvem", "51030603", 1721850.92),
    ("06-RESIDENCIA", "06.01-INFRAESTRUTURA", "Laboratório virtualizado", "51030603", 156821.75),
    ("06-RESIDENCIA", "06.02-BOLSAS", "Bolsas para os residentes (1.000 bolsas)", "51010601", 12000000.00),
    ("06-RESIDENCIA", "06.02-BOLSAS", "Bolsas para os mentores (250 bolsas)", "51010601", 3000000.00),
    ("06-RESIDENCIA", "06.03-NOTEBOOKS", "Notebooks para os residentes (1.000 unidades)", "13010102", 8000000.00),
]


def meses_do_ano(total: float) -> list[float]:
    mensal = round(total / 12, 2)
    v = [mensal] * 11
    return v + [round(total - sum(v), 2)]


def main(argv: list[str]) -> int:
    gravar, refazer = "--gravar" in argv, "--refazer" in argv
    linhas = [(m, a, i, c, round(t / ANOS, 2)) for m, a, i, c, t in ITENS]
    total = sum(x[4] for x in linhas)
    with tx() as c:
        if not c.execute("SELECT 1 FROM projetos WHERE orcamento=?", (ORC,)).fetchone():
            print(f"Orçamento {ORC} não existe na base.")
            return 1
        for (conta,) in {(x[3],) for x in linhas}:
            if not c.execute("SELECT 1 FROM contas WHERE codigo=?", (conta,)).fetchone():
                print(f"Conta {conta} fora da lista do template.")
                return 1
        ja = c.execute("SELECT COUNT(*), SUM(atualizado_por=?) FROM linhas WHERE ciclo=? AND orcamento=?",
                       (AUTOR, config.CICLO_PLANO, ORC)).fetchone()
        for meta in dict.fromkeys(x[0] for x in linhas):
            print(f"{meta}: R$ {sum(x[4] for x in linhas if x[0] == meta):,.2f}")
        print(f"Total 2027: R$ {total:,.2f} em {len(linhas)} linhas")
        if not gravar:
            print("Nada gravado. Use --gravar para lançar.")
            return 0
        if ja[0] and not (refazer and ja[0] == ja[1]):
            print(f"O {ORC} já tem {ja[0]} linha(s) no plano 2027" +
                  ("" if not refazer else " e nem todas vieram desta carga") + ". Nada foi alterado.")
            return 1
        if ja[0]:
            c.execute("DELETE FROM linhas WHERE ciclo=? AND orcamento=? AND atualizado_por=?", (config.CICLO_PLANO, ORC, AUTOR))
        for meta, acao, item, conta, valor in linhas:
            c.execute(f"INSERT INTO linhas (ciclo, orcamento, edt, tarefa, conta_codigo, {', '.join(MESES)}, editada, obs, atualizado_por) "
                      f"VALUES (?,?,?,?,?,{', '.join('?' for _ in MESES)},1,?,?)",
                      (config.CICLO_PLANO, ORC, meta, acao, conta, *meses_do_ano(valor), item, AUTOR))
        audit(c, AUTOR, "carga do programa", ORC, detalhe=f"{len(linhas)} linhas, R$ {total:,.2f}")
    print("Gravado.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
