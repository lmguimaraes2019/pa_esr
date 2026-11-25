import React from "react";

/** Relatórios do planejamento 2027: abertos a todos os usuários, cada um com os projetos que pode ver. */
export default function Relatorios() {
  return (
    <>
      <h2>Relatórios</h2>
      <p className="mudo">Os relatórios usam os dados de agora e mostram apenas o que o seu perfil de acesso permite ver. Cada geração fica registrada no histórico. O projeto da Diretoria Executiva (DSS-RA-GESTAO DA AREA) não entra na contabilidade nem nos relatórios.</p>
      <section className="cartao">
        <h3>Planilha do orçamento completo (PMO e diretores)</h3>
        <p>Pasta de trabalho do Excel com a visão holística do orçamento: aba Sumário com todas as ações (novo ou existente, tipo de projeto, origem de recursos, previsto 2026, empenhado, executado, saldo e previsto 2027, com resumos por origem e por gerência), uma aba para cada projeto lançado (os extintos aparecem só no Sumário), e abas de Viagens, Headcount, Eventos, Equipamentos de TIC e Receitas. Totais e saldos são fórmulas, e há filtros em todas as abas.</p>
        <div className="acoes"><a className="botao primario" href="/api/export/orcamento">Exportar planilha do orçamento</a></div>
        <p className="mudo">Mostra apenas o que o seu perfil de acesso permite ver. Cada geração fica registrada na auditoria.</p>
      </section>
      <section className="cartao">
        <h3>Relatório para o Diretor Executivo</h3>
        <p>Documento em Word, no modelo da RNP, que explica tudo o que foi gerado no planejamento. A primeira parte traz a visão geral: síntese, evolução de 2026 para 2027 por origem de recurso e grupo de despesa, receitas e resultado, headcount, viagens, eventos, conexão com o Plano Operacional e o Contrato de Gestão, acompanhamento por gerência e premissas. A segunda parte traz um capítulo por projeto, com números, relação estratégica, entregas e o detalhe de cada linha do orçamento.</p>
        <div className="acoes"><a className="botao primario" href="/api/export/relatorio">Gerar relatório (Word)</a></div>
        <p className="mudo">Ao abrir no Word, aceite a atualização dos campos para acertar a numeração do sumário.</p>
      </section>
      <section className="cartao">
        <h3>Apresentação executiva do orçamento</h3>
        <p>Apresentação em PowerPoint, no padrão visual da ESR (template 20 Anos), com a visão de alto nível: resumo dos números, evolução de 2026 para 2027 por origem de recurso, finalidade e grupo de despesa, orçamento por gerência, maiores projetos e os que mais mudam, receitas e resultado, conexão com o Plano Operacional e o Contrato de Gestão e pontos de atenção. Os gráficos e tabelas são editáveis no PowerPoint.</p>
        <div className="acoes"><a className="botao primario" href="/api/export/apresentacao">Gerar apresentação (PowerPoint)</a></div>
        <p className="mudo">Usa os dados de agora. Cada geração fica registrada na auditoria.</p>
      </section>
    </>
  );
}
