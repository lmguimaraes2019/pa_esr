import React, { Fragment, useEffect, useState } from "react";
import { api, fmt, fmtN } from "./api.js";
import { pct } from "./ui.jsx";

const quando = (s) => (s ? new Date(s.replace(" ", "T") + "Z").toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" }) : "");

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

export function MeuPlanejamento({ plano, recarregar, admin, ir }) {
  const [obs, setObs] = useState("");
  const [erro, setErro] = useState("");
  if (!plano) return <p>Carregando…</p>;
  const e = plano.etapas;
  const pend = plano.pendencias;
  const concluir = async (concluido) => {
    setErro("");
    try { await api("/planejamento/concluir", { method: "POST", body: { concluido, obs } }); recarregar(); } catch (x) { setErro(x.message); }
  };
  const itens = [
    ["projetos", "Despesas", e.despesas.ajustadas ? "ok" : "neutro", e.despesas.ajustadas ? "com ajustes" : "sem ajustes",
      `${e.despesas.projetos} projeto(s), ${e.despesas.projetos - e.despesas.sem_ajuste} com ajustes, novas ou excluídas`, e.despesas.plano, "Abrir despesas"],
    ["receitas", "Receitas", e.receitas.sem_receita ? "neutro" : "ok", e.receitas.sem_receita ? `${e.receitas.sem_receita} sem receita` : "lançadas",
      `${e.receitas.n} receita(s) lançada(s)`, e.receitas.total, "Abrir receitas"],
    ["viagens", "Viagens", e.viagens.pendentes ? "pend" : "ok", e.viagens.pendentes ? `${e.viagens.pendentes} pendente(s)` : "em dia",
      `${e.viagens.n} viagem(ns) planejada(s)`, e.viagens.total, e.viagens.pendentes ? "Resolver" : "Abrir viagens"],
    ["eventos", "Eventos", e.eventos.pendentes ? "pend" : "ok", e.eventos.pendentes ? `${e.eventos.pendentes} incompleto(s)` : e.eventos.n ? "em dia" : "nenhum",
      `${e.eventos.n} evento(s)`, e.eventos.total, e.eventos.pendentes ? "Completar" : "Abrir eventos"],
    ["headcount", "Headcount", e.headcount.pendentes ? "pend" : "ok", e.headcount.pendentes ? `${e.headcount.pendentes} incompleta(s)` : e.headcount.n ? "em dia" : "nenhuma",
      `${e.headcount.n} posição(ões) nova(s), custo em 2027`, e.headcount.total, e.headcount.pendentes ? "Completar" : "Abrir headcount"],
  ];
  const feitas = itens.filter((i) => i[2] !== "pend").length;
  return (
    <section className="cartao meu-plano">
      <div className="cab">
        <div><h3 style={{ margin: 0 }}>Etapas do plano 2027</h3>
          <p className="mudo">Percorra as cinco etapas em ordem. Os valores de Viagens, Eventos e Headcount entram sozinhos no orçamento de cada projeto.</p></div>
        <div className="progresso" title={`${feitas} de ${itens.length} etapas sem pendência`}><span style={{ width: (feitas / itens.length) * 100 + "%" }} /><small>{feitas} de {itens.length} em dia</small></div>
      </div>
      <ol className="etapas-lista">{itens.map(([k, t, tom, est, txt, val, ac], i) => <Etapa key={k} n={i + 1} titulo={t} tom={tom} estado={est} texto={txt} valor={val} acao={ac} onAcao={() => ir(k)} />)}</ol>
      <div className="concluir">
        {plano.concluido ? (
          <><p><Estado tom="ok">concluído</Estado> Você marcou o planejamento como concluído em {quando(plano.concluido.concluido_em)}.{plano.concluido.obs && ` Observação: ${plano.concluido.obs}`}</p>
            <button onClick={() => concluir(false)}>Reabrir para ajustar</button></>
        ) : (
          <><div><strong>Terminou?</strong> <span className="mudo">{pend ? `Resolva as ${pend} pendência(s) acima para poder concluir.` : "Avise o administrador de que o seu planejamento está pronto para ir ao PMO."}</span>
            <input className="obs-conc" value={obs} onChange={(x) => setObs(x.target.value)} placeholder="Observação para o administrador (opcional)" maxLength={500} /></div>
            <button className="primario" disabled={pend > 0} onClick={() => concluir(true)}>Concluir meu planejamento</button></>
        )}
        {erro && <p className="erro" role="alert">{erro}</p>}
      </div>
      {admin && plano.gerencias && (
        <>
          <h4 className="sub">Acompanhamento por gerência</h4>
          <div className="rolagem"><table className="tab ger"><thead><tr><th>Gerência / responsáveis</th><th className="n">Projetos</th><th className="n">Plano 2026</th><th className="n">Executado 2026</th><th className="n">% exec.</th><th className="n">Plano 2027</th><th className="n">Pendências</th><th>Situação</th></tr></thead>
            <tbody>{plano.gerencias.map((g) => (
              <Fragment key={g.gerencia || "_"}>
                <tr className="ger-linha"><td><strong>{g.gerencia || "Sem gerência definida"}</strong></td><td className="n">{g.projetos}</td><td className="n">{fmtN(g.aprovado)}</td><td className="n">{fmtN(g.executado)}</td>
                  <td className="n">{g.aprovado ? pct(g.executado, g.aprovado) : "-"}</td><td className="n">{fmtN(g.plano)}</td><td className="n">{g.pendencias || "-"}</td>
                  <td>{g.concluido ? <><Estado tom="ok">concluída</Estado> <span className="mudo">{quando(g.concluido_em)}</span></> : <Estado tom={g.pendencias ? "pend" : "neutro"}>{g.pendencias ? "com pendências" : "em andamento"}</Estado>}</td></tr>
                {g.pessoas.map((p) => (
                  <tr key={p.login} className={"ger-pessoa " + (p.cargo === "coordenador" ? "n2" : "n1")}>
                    <td><span className="ger-nome">{p.nome}</span> <span className="mudo">{p.cargo || "sem cargo"}</span></td>
                    <td className="n">{p.projetos}</td><td colSpan={2} /><td /><td className="n">{fmtN(p.plano)}</td><td className="n">{p.pendencias || "-"}</td>
                    <td>{p.concluido_em ? <><Estado tom="ok">concluído</Estado> <span className="mudo">{quando(p.concluido_em)}{p.obs && ` | ${p.obs}`}</span></> : <Estado tom={p.pendencias ? "pend" : "neutro"}>{p.pendencias ? "com pendências" : "em andamento"}</Estado>}</td></tr>))}
              </Fragment>))}
              {!plano.gerencias.length && <tr><td colSpan={8} className="mudo">Nenhum gestor cadastrado.</td></tr>}</tbody></table></div>
        </>
      )}
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
  ];
  return (
    <section className="cartao">
      <h3>Resumo do projeto no plano 2027</h3>
      <p className="mudo">{d.pendencias ? `${d.pendencias} pendência(s) neste projeto.` : "Sem pendências neste projeto."} Viagens, Eventos e Headcount já estão somados em Despesas.</p>
      <div className="resumo-cards">{cartoes.map(([k, t, v, s, p], i) => (
        <div key={k} className={"resumo-card " + (p ? "pend" : "")}>
          <span className="etapa-n">{i + 1}</span><strong>{t}</strong><b>{v}</b><small className="mudo">{s}</small>
          {p > 0 && <Estado tom="pend">{p} pendente(s)</Estado>}
          <button onClick={() => irEtapa(k)}>{k === "projetos" ? "Ver as linhas" : "Abrir"}</button>
        </div>))}</div>
    </section>
  );
}
