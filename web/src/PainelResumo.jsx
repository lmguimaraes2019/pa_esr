import React, { useState } from "react";
import { fmt } from "./api.js";
import { Delta, pct, nomeFinalidade, classeFinalidade, celPrevisao, fmtV, semValor } from "./ui.jsx";

const vazio = "Sem gerência definida";
const soma = (l, k) => l.reduce((a, p) => a + p[k], 0);
const vp = (de, para) => (de ? (((para - de) / de) * 100).toFixed(0).replace(".", ",") + "%" : Math.abs(para) < 0.005 ? semValor : "novo");

/** Por gerência: o que foi aprovado e executado em 2026 e o que se planeja para 2027, com a situação do planejamento (admin). */
export function PorGerencia({ ps, status, nExtintos = 0, origens = [] }) {
  const [fechado, setFechado] = useState({});
  const g = {};
  ps.forEach((p) => { (g[p.gerencia || vazio] ||= []).push(p); });
  const nomes = Object.keys(g).sort((a, b) => (a === "Diretoria Adjunta" ? -1 : b === "Diretoria Adjunta" ? 1 : a === vazio ? 1 : b === vazio ? -1 : a.localeCompare(b, "pt-BR")));
  const tot27 = soma(ps, "total_2027");
  const sit = (n) => status && status[n];
  const celulas = (a, e, p27, n, rotulo, lp = null) => (
    <>{rotulo}<td className="n">{n || semValor}</td><td className="n">{fmtV(a)}</td><td className="n">{fmtV(e)}</td><td className="n">{a > 0 && e > 0 ? pct(e, a) : semValor}</td>{lp ? celPrevisao(lp) : <><td className="n">{semValor}</td><td className="n">{semValor}</td></>}
      <td className="n"><strong>{fmtV(p27)}</strong></td><td className="n"><Delta de={a} para={p27} /></td><td className="n">{vp(a, p27)}</td>
      <td>{p27 > 0 ? <span className="peso"><span className="peso-barra"><i style={{ width: Math.max(tot27 ? p27 / tot27 * 100 : 0, 2) + "%" }} /></span>{tot27 ? (p27 / tot27 * 100).toFixed(0) : 0}%</span> : <span className="peso">{semValor}</span>}</td></>);
  const linha = (nome, l, total) => {
    const a = soma(l, "total_2026"), e = soma(l, "realizado_2026"), p27 = soma(l, "total_2027");
    const s = !total && sit(nome);
    const ordem = [...origens, ...[...new Set(ps.map((p) => p.origem || "Sem origem"))].filter((o) => !origens.includes(o))];      // mesma ordem e mesmas origens em todas as gerências
    const aberto = !total && !fechado[nome];
    return (
      <React.Fragment key={nome}>
        <tr className={total ? "" : "ger-linha-res"} onClick={() => !total && setFechado((f) => ({ ...f, [nome]: !f[nome] }))} style={{ cursor: total ? "default" : "pointer" }}>
          {celulas(a, e, p27, l.length, <td style={{ whiteSpace: "nowrap" }}><span className="seta">{total ? "" : aberto ? "▾" : "▸"}</span> <strong>{nome}</strong></td>, l)}
          {status && <td>{total ? "" : s ? (s.concluida ? <span className="estado ok">concluída</span> : <span className={"estado " + (s.pendencias ? "pend" : "neutro")}>{s.pendencias ? `${s.pendencias} pendência(s)` : "em andamento"}</span>) : <span className="mudo">-</span>}</td>}
        </tr>
        {aberto && ordem.flatMap((o) => {
          const l2 = l.filter((p) => (p.origem || "Sem origem") === o);
          const hc = (k) => soma(l2, k);
          // headcount fica todo nos projetos da Diretoria Adjunta: só ali a linha separada aparece, e só nas origens que têm lançamento
          const temHc = nome === "Diretoria Adjunta" && hc("pessoal_2026") + hc("pessoal_2027") + hc("pessoal_realizado_2026") > 0;
          const nHc = l2.filter((p) => p.pessoal_2026 + p.pessoal_2027 + p.pessoal_realizado_2026 > 0).length;
          const tira = (k, kp) => soma(l2, k) - (temHc ? hc(kp) : 0);
          // a previsão é por projeto: o projeto de headcount (pessoal é a maior parte) leva a previsão para a linha de headcount
          const ehHc = (p) => p.pessoal_2026 > 0 && p.pessoal_2026 >= p.total_2026 * 0.5;
          const lpHc = temHc ? l2.filter(ehHc) : [], lpOrg = temHc ? l2.filter((p) => !ehHc(p)) : l2;
          const linhas = [
            <tr key={nome + "|" + o} className="ger-origem">
              {celulas(tira("total_2026", "pessoal_2026"), tira("realizado_2026", "pessoal_realizado_2026"), tira("total_2027", "pessoal_2027"), temHc ? lpOrg.length : l2.length, <td style={{ paddingLeft: 34, whiteSpace: "nowrap" }}>{o}</td>, lpOrg)}
              {status && <td />}
            </tr>];
          if (temHc) linhas.push(
            <tr key={nome + "|" + o + "|hc"} className="ger-origem ger-hc">
              {celulas(hc("pessoal_2026"), hc("pessoal_realizado_2026"), hc("pessoal_2027"), nHc, <td style={{ paddingLeft: 56, whiteSpace: "nowrap" }}>{o} Headcount</td>, lpHc)}
              {status && <td />}
            </tr>);
          return linhas;
        })}
      </React.Fragment>);
  };
  return (
    <section className="cartao">
      <h3>Por gerência e origem do recurso: 2026 e plano 2027</h3>
      <p className="mudo" style={{ margin: "0 0 8px", fontSize: ".85rem" }}>Cada gerência traz todas as origens de recurso. O headcount fica todo nos projetos da Diretoria Adjunta e aparece em linha separada ("Fomento Headcount"), sem somar na linha da origem. A previsão de execução é informada por projeto; os projetos de headcount levam a previsão para a linha de headcount. Clique na gerência para recolher ou abrir.{nExtintos > 0 && <> Inclui {nExtintos} ação(ões) extinta(s), que mantêm o aprovado e o executado de 2026 e têm plano 2027 zerado.</>}</p>
      <div className="rolagem" style={{ margin: 0 }}><table className="tab tab-grande">
        <thead><tr><th>Gerência</th><th className="n">Projetos</th><th className="n">Aprovado 2026</th><th className="n">Executado 2026</th><th className="n">% exec.</th><th className="n" title="Quanto os gestores preveem ter executado até 31/12/2026 (soma dos projetos que já informaram)">Previsão 31/12</th><th className="n" title="Previsão sobre o aprovado de 2026, só dos projetos que informaram">% prev.</th><th className="n">Plano 2027</th><th className="n">Variação</th><th className="n">Var. %</th><th style={{ width: 120 }}>Peso</th>{status && <th>Planejamento</th>}</tr></thead>
        <tbody>{nomes.map((n) => linha(n, g[n], false))}</tbody>
        <tfoot>{linha("Total", ps, true)}</tfoot>
      </table></div>
    </section>);
}

/** Os projetos do plano: nome, gerência, origem do recurso, finalidade (propósito) e os valores de 2026 e 2027. */
export function ProjetosDoPlano({ ps, abrir, verTodos }) {
  const [todos, setTodos] = useState(false);
  const lista = [...ps].sort((a, b) => b.total_2027 - a.total_2027);
  const mostra = todos ? lista : lista.slice(0, 12);
  const conting = ps.filter((p) => p.contingenciado);
  return (
    <section className="cartao">
      <h3>Projetos do plano 2027 <span className="contagem">{ps.length}</span></h3>
      <p className="mudo" style={{ marginTop: 0 }}>Do maior para o menor valor em 2027. {conting.length > 0 && <>Em laranja, os {conting.length} contingenciados ({fmt(soma(conting, "total_2027"))} em 2027), não liberados para execução. </>}Clique em um projeto para abrir.</p>
      <div className="rolagem" style={{ margin: 0 }}><table className="tab tab-grande tab-proj">
        <thead><tr><th className="cod" title="Número do orçamento">Orçamento</th><th className="cod" title="Número do projeto no PCO">Nº projeto</th><th className="cod" title="Centro de custo no PCO">Centro de custo</th><th className="nome">Projeto</th><th>Gerência</th><th>Origem</th><th>Finalidade</th><th className="n">Aprovado 2026</th><th className="n">Executado 2026</th><th className="n">% exec.</th><th className="n" title="Quanto o gestor prevê ter executado até 31/12/2026">Previsão 31/12</th><th className="n" title="Previsão sobre o aprovado de 2026">% prev.</th><th className="n">Plano 2027</th><th className="n">Variação</th></tr></thead>
        <tbody>{mostra.map((p) => (
          <tr key={p.orcamento} className={"proj " + (p.contingenciado ? "conting" : "")} onClick={() => abrir(p.orcamento)} style={{ cursor: "pointer" }}>
            <td className="cod">{p.novo ? <span className="tag ok">novo</span> : p.orcamento}</td><td className="cod">{p.n_projeto || semValor}</td><td className="cod">{p.centro_custo || semValor}</td>
            <td className="nome"><strong>{p.descricao}</strong>{p.contingenciado && <div className="mudo" style={{ fontSize: ".78rem" }}>contingenciado</div>}</td>
            <td>{p.gerencia || vazio}</td><td>{p.origem}</td>
            <td><span className={"tag " + classeFinalidade(p.finalidade)}>{nomeFinalidade(p.finalidade)}</span></td>
            <td className="n">{fmtV(p.total_2026)}</td><td className="n">{fmtV(p.realizado_2026)}</td><td className="n">{p.total_2026 > 0 && p.realizado_2026 > 0 ? pct(p.realizado_2026, p.total_2026) : semValor}</td>{celPrevisao([p])}
            <td className="n"><strong>{fmtV(p.total_2027)}</strong></td><td className="n"><Delta de={p.total_2026} para={p.total_2027} /></td></tr>))}</tbody>
        <tfoot><tr><td colSpan={7}>Total ({ps.length})</td><td className="n">{fmt(soma(ps, "total_2026"))}</td><td className="n">{fmt(soma(ps, "realizado_2026"))}</td><td className="n">{pct(soma(ps, "realizado_2026"), soma(ps, "total_2026"))}</td>{celPrevisao(ps)}<td className="n">{fmt(soma(ps, "total_2027"))}</td><td className="n"><Delta de={soma(ps, "total_2026")} para={soma(ps, "total_2027")} /></td></tr></tfoot>
      </table></div>
      <div style={{ marginTop: 10, display: "flex", gap: 10 }}>
        {lista.length > 12 && <button type="button" onClick={() => setTodos(!todos)}>{todos ? "Mostrar só os 12 maiores" : `Mostrar todos os ${lista.length} projetos`}</button>}
        <button type="button" onClick={verTodos}>Abrir a página de projetos</button>
      </div>
    </section>);
}
