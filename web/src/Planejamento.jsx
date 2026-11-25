import React, { useEffect, useState } from "react";
import { api, fmt } from "./api.js";

const quando = (s) => (s ? new Date(s.replace(" ", "T") + "Z").toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" }) : "");

export const CARGOS = { gerente: "Gerente", coordenador: "Coordenador", diretor_adjunto: "Diretor Adjunto", diretor_executivo: "Diretor Executivo", pmo: "PMO" };

function Estado({ tom, children }) {
  return <span className={"estado " + tom}>{children}</span>;
}

/** Linha de cada etapa do plano 2027, na tela inicial. */
function Etapa({ n, titulo, tom, estado, texto, valor, acao, onAcao }) {
  return (
    <li className={"etapa-card " + tom}>
      <span className="etapa-n">{n}</span>
      <div className="etapa-corpo"><strong>{titulo}</strong><span className="mudo">{texto}</span></div>
      <div className="etapa-valor">{valor != null && <strong>{fmt(valor)}</strong>}<Estado tom={tom}>{estado}</Estado></div>
      <button className={tom === "pend" ? "destaque" : ""} onClick={onAcao}>{acao}</button>
    </li>
  );
}

export function MeuPlanejamento({ plano, recarregar, admin, ir, erro: erroCarga }) {
  const [obs, setObs] = useState("");
  const [erro, setErro] = useState("");
  if (!plano) return erroCarga ? <p className="erro">Não foi possível carregar o acompanhamento do planejamento ({erroCarga}). <button type="button" className="link" onClick={recarregar}>Tentar de novo</button></p> : <p>Carregando…</p>;
  const e = plano.etapas;
  const pend = plano.pendencias;
  const concluir = async (concluido) => {
    setErro("");
    try { await api("/planejamento/concluir", { method: "POST", body: { concluido, obs } }); recarregar(); } catch (x) { setErro(x.message); }
  };
  return (
    <section className="cartao meu-plano">
      <h3 style={{ margin: "0 0 6px" }}>Status do planejamento 2027</h3>
      <div className="concluir">
        {plano.concluido ? (
          <><p><Estado tom="ok">concluído</Estado> Você marcou o planejamento como concluído em {quando(plano.concluido.concluido_em)}.{plano.concluido.obs && ` Observação: ${plano.concluido.obs}`}</p>
            <button onClick={() => concluir(false)}>Reabrir para ajustar</button></>
        ) : plano.dispensado ? (
          <p><Estado tom="neutro">dispensado</Estado> {plano.dispensado}</p>
        ) : (
          <><div><strong>Terminou?</strong> <span className="mudo">{pend ? `Resolva as ${pend} pendência(s) acima para poder concluir.` : "Avise o administrador de que o seu planejamento está pronto para ir ao PMO."}</span>
            <input className="obs-conc" value={obs} onChange={(x) => setObs(x.target.value)} placeholder="Observação para o administrador (opcional)" maxLength={500} /></div>
            <button className="primario" disabled={pend > 0} onClick={() => concluir(true)}>Concluir meu planejamento</button></>
        )}
        {erro && <p className="erro" role="alert">{erro}</p>}
      </div>
    </section>
  );
}

/** Aba "Resumo" dentro do projeto: o que há nas cinco etapas e o que falta. */
export function ResumoProjeto({ orcamento, irEtapa }) {
  const [d, setD] = useState(null);
  useEffect(() => { api(`/planejamento/projeto/${orcamento}`).then(setD).catch(() => setD(false)); }, [orcamento]);
  if (d === false) return <p className="erro">Não foi possível carregar o resumo.</p>;
  if (!d) return <p>Carregando…</p>;
  const x = d.despesas;
  const cartoes = [
    ["projetos", "Despesas", fmt(x.plano), `${x.linhas} linha(s) | ${x.ajustadas} ajustada(s), ${x.novas} nova(s), ${x.excluidas} excluída(s), ${x.bloqueadas} bloqueada(s)`, 0],
    ["receitas", "Receitas", fmt(d.receitas.total), d.receitas.n ? `${d.receitas.n} receita(s)` : "Nenhuma receita lançada", 0],
    ["viagens", "Viagens", fmt(d.viagens.total), `${d.viagens.n} viagem(ns)`, d.viagens.pendentes],
    ["eventos", "Eventos", fmt(d.eventos.total), `${d.eventos.n} evento(s)`, d.eventos.pendentes],
    ["headcount", "Headcount", fmt(d.headcount.total), `${d.headcount.n} posição(ões) | custo em 2027`, d.headcount.pendentes],
    ["financiamento", "Fonte de financiamento", d.financiamento.fonte ? (d.financiamento.nome || d.financiamento.fonte) : "Não informada", d.financiamento.fonte === "intercompany" ? "Custeado pelas transferências intercompany" : d.financiamento.fonte ? "Estratégia de financiamento" : "Indique a fonte do recurso", d.financiamento.pendentes],
    ["entregas", "Entregas", `${d.entregas.n}`, d.entregas.motivo === "sem vínculo estratégico" ? "Falta vincular o orçamento ao PO e ao CG" : d.entregas.n ? `${d.entregas.n - d.entregas.sem_conexao} com KPI ou conexão estratégica` : "Nenhuma entrega informada", d.entregas.pendentes],
  ];
  return (
    <section className="cartao">
      <h3>Resumo do projeto no plano 2027</h3>
      <p className="mudo">{d.pendencias ? `${d.pendencias} pendência(s) neste projeto.` : "Sem pendências neste projeto."} Viagens, Eventos e Headcount já estão somados em Despesas.</p>
      <div className="resumo-cards">{cartoes.map(([k, t, v, s, p], i) => (
        <div key={k} className={"resumo-card " + (p ? "pend" : "")}>
          <span className="etapa-n">{i + 1}</span><strong>{t}</strong><b>{v}</b><small className="mudo">{s}</small>
          {p > 0 && <Estado tom="pend">{k === "entregas" ? "pendente" : `${p} pendente(s)`}</Estado>}
          <button onClick={() => irEtapa(k)}>{k === "projetos" ? "Ver as linhas" : k === "entregas" ? (d.entregas.motivo === "sem vínculo estratégico" ? "Vincular" : "Informar entregas") : "Abrir"}</button>
        </div>))}</div>
    </section>
  );
}
