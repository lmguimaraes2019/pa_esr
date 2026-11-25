import React, { useEffect, useState } from "react";
import { api, fmt, mi } from "./api.js";
import { Kpi, Delta, pct, Selo, FiltroGerencia } from "./ui.jsx";
import { MeuPlanejamento } from "./Planejamento.jsx";
import OutrosProjetos from "./OutrosProjetos.jsx";
import useFluxo, { OrigemDosRecursos } from "./FluxoRecursos.jsx";
import { PorGerencia, ProjetosDoPlano } from "./PainelResumo.jsx";

function Quadro({ itens, rotulo, aninhado }) {
  const [fechado, setFechado] = useState({});
  const varp = (de, para) => (de ? ((para - de) / de) * 100 : null);
  const Vp = ({ de, para }) => { const v = varp(de, para); return v == null ? <span className="mudo">-</span> : <span className={v > 0 ? "up" : v < 0 ? "down" : "mudo"}>{(v > 0 ? "+" : "") + v.toFixed(0)}%</span>; };
  const linha = (i, filho, tem) => (
    <tr key={(filho ? "f-" : "") + i.nome + (filho || "")} className={filho ? "filho" : tem ? "pai" : ""} onClick={tem ? () => setFechado({ ...fechado, [i.nome]: !fechado[i.nome] }) : undefined} style={tem ? { cursor: "pointer" } : undefined}>
      <td style={filho ? { paddingLeft: 28 } : undefined}>{tem && <span className="mudo" style={{ marginRight: 6 }}>{fechado[i.nome] ? "▸" : "▾"}</span>}{filho ? <span className="mudo">{i.nome}</span> : i.nome}</td>
      <td className="n">{fmt(i.base)}</td><td className="n">{fmt(i.executado)}</td><td className="n">{pct(i.executado, i.base)}</td>
      <td className="n"><strong>{fmt(i.plano)}</strong></td><td className="n"><Delta de={i.base} para={i.plano} /></td>
      <td className="n"><Vp de={i.base} para={i.plano} /></td>
    </tr>);
  return (
    <table className="tab">
      <thead>
        <tr className="grupos"><th style={{ background: "#fff" }} />
          <th colSpan={3} className="g26"><Selo ano={2026} /></th><th colSpan={3} className="g27"><Selo ano={2027} /></th></tr>
        <tr><th>{rotulo}</th><th className="n g26">Aprovado 2026</th><th className="n g26">Executado</th><th className="n g26">% exec.</th><th className="n g27">Plano 2027</th><th className="n g27">Δ R$</th><th className="n g27">Δ %</th></tr>
      </thead>
      <tbody>{itens.map((i) => {
        const fs = aninhado ? i.finalidades || [] : [];
        return [linha(i, null, fs.length > 0), ...(fechado[i.nome] ? [] : fs.map((f) => linha(f, i.nome, false)))];
      })}</tbody>
      <tfoot><tr><td>Total</td><td className="n">{fmt(itens.reduce((a, i) => a + i.base, 0))}</td><td className="n">{fmt(itens.reduce((a, i) => a + i.executado, 0))}</td><td />
        <td className="n">{fmt(itens.reduce((a, i) => a + i.plano, 0))}</td><td className="n"><Delta de={itens.reduce((a, i) => a + i.base, 0)} para={itens.reduce((a, i) => a + i.plano, 0)} /></td><td className="n"><Vp de={itens.reduce((a, i) => a + i.base, 0)} para={itens.reduce((a, i) => a + i.plano, 0)} /></td></tr></tfoot>
    </table>
  );
}

function Cobertura({ admin }) {
  const [c, setC] = useState(null);
  const [aberto, setAberto] = useState(null);
  const [exp, setExp] = useState(new Set());      // diretrizes e REs abertos: tudo começa recolhido
  const alterna = (id) => setExp((x) => { const n = new Set(x); n.has(id) ? n.delete(id) : n.add(id); return n; });
  useEffect(() => { api("/estrategia/cobertura").then(setC).catch(() => setC(false)); }, []);
  if (!c) return null;
  const desassocia = async (i, p) => {
    const abaixo = i.tipo === "po" ? "" : " (e dos itens abaixo dele)";
    if (!window.confirm(`Desassociar o projeto "${p.projeto || p.orcamento}" de ${rot(i)}${abaixo}?`)) return;
    try { await api(`/estrategia/cobertura/${encodeURIComponent(p.orcamento)}/${i.id}`, { method: "DELETE" }); setC(await api("/estrategia/cobertura")); }
    catch (e) { window.alert(e.message || "Não foi possível desassociar."); }
  };
  const rot = (i) => (/^\d/.test(i.codigo) ? ({ diretriz: "Diretriz", re: "RE", po: "RO", cg: "CG" }[i.tipo] + " " + i.codigo) : i.codigo);
  const nivel = { diretriz: 0, re: 1, po: 2, cg: 0 };
  const filhos = {};      // itens da hierarquia vêm em ordem: diretriz, seus REs, os ROs de cada RE
  { let dir = null, re = null; c.itens.filter((x) => x.tipo !== "cg").forEach((x) => {
    if (x.tipo === "diretriz") { dir = x.id; re = null; } else if (x.tipo === "re") { x.pai = dir; re = x.id; } else x.pai = re || dir;
    if (x.pai != null) (filhos[x.pai] = filhos[x.pai] || []).push(x.id); }); }
  const visivel = (i) => i.tipo === "cg" || i.tipo === "diretriz" || (i.pai != null && exp.has(i.pai) && (i.tipo === "re" || visivel(c.itens.find((x) => x.id === i.pai))));
  const tem = (i) => (filhos[i.id] || []).length > 0;
  const linha = (i) => !visivel(i) ? null : (
    <React.Fragment key={i.id}>
      <tr className={"cob n" + nivel[i.tipo] + " " + i.tipo + (i.projetos ? "" : " sem-cobertura")} onClick={() => tem(i) ? alterna(i.id) : i.projetos && setAberto(aberto === i.id ? null : i.id)} style={{ cursor: tem(i) || i.projetos ? "pointer" : "default" }}>
        <td>{tem(i) && <span className="mudo" style={{ marginRight: 6 }}>{exp.has(i.id) ? "▾" : "▸"}</span>}<b>{rot(i)}</b> {i.descricao}{tem(i) && <span className="mudo"> ({filhos[i.id].length} {i.tipo === "diretriz" ? "itens" : "ROs"})</span>}{tem(i) && i.projetos > 0 && <button type="button" className="link" style={{ marginLeft: 8 }} onClick={(e) => { e.stopPropagation(); setAberto(aberto === i.id ? null : i.id); }}>{aberto === i.id ? "ocultar projetos" : "ver projetos"}</button>}{i.tipo === "po" && i.responsavel && <span className="chip">{i.responsavel}</span>}{i.tipo === "po" && i.conclusao && <span className="chip mes">{i.conclusao}</span>}</td>
        <td className="n">{i.entregas || <span className="mudo">0</span>}</td><td className="n">{i.projetos || <strong className="aviso-txt">nenhum</strong>}</td><td className="n">{i.projetos ? fmt(i.plano_projetos) : <span className="mudo">-</span>}</td>
      </tr>
      {aberto === i.id && <tr className="cob-det"><td colSpan={4}>{i.lista_projetos.map((p) => <span key={p.orcamento} className="chip">{p.projeto} <span className="mudo">{fmt(p.plano)}</span> <button type="button" className="chip-x" title="Desassociar este projeto" aria-label="Desassociar" onClick={() => desassocia(i, p)}>×</button></span>)}</td></tr>}
    </React.Fragment>);
  const hier = c.itens.filter((i) => i.tipo !== "cg"), cg = c.itens.filter((i) => i.tipo === "cg");
  return (
    <section className="cartao"><h3>Conexão estratégica</h3>
      <p className="mudo">Do direcionador ao indicador do Contrato de Gestão: quais projetos e entregas sustentam cada item e quanto do plano 2027 está ligado a ele. Tudo começa recolhido: clique numa diretriz para abrir os REs, e num RE para ver os ROs. Num RO (ou em "ver projetos") aparecem os projetos. Um projeto pode servir a mais de um item, então os valores não se somam.</p>
      {c.catalogo_vazio ? <p className="mudo">Cadastre os itens em Administração, Tabelas de referência, "Estratégia".</p> : (<>
        <div className="acoes" style={{ margin: "4px 0" }}><button type="button" onClick={() => setExp(new Set(c.itens.filter((x) => x.tipo !== "cg" && (filhos[x.id] || []).length).map((x) => x.id)))}>Expandir tudo</button><button type="button" onClick={() => { setExp(new Set()); setAberto(null); }}>Recolher tudo</button></div>
        <div className="rolagem"><table className="tab"><thead><tr><th>Item</th><th className="n">Entregas</th><th className="n">Projetos</th><th className="n">Plano 2027 dos projetos</th></tr></thead>
          <tbody>{hier.map(linha)}{cg.length > 0 && <tr><td colSpan={4}><strong>Indicadores do Contrato de Gestão</strong></td></tr>}{cg.map(linha)}</tbody></table></div></>)}
      {admin && !c.catalogo_vazio && c.sem_vinculo.length > 0 && (
        <div className="nota aviso"><strong>{c.sem_vinculo.length}</strong> projeto(s) com plano 2027 de <strong>{fmt(c.plano_sem_vinculo)}</strong> sem nenhum vínculo estratégico (de {fmt(c.plano_total)} no total):{" "}
          {c.sem_vinculo.slice(0, 15).map((p) => p.projeto || p.orcamento).join("; ")}{c.sem_vinculo.length > 15 ? "…" : ""}</div>)}
    </section>
  );
}

function EstrategiaFinanciamento() {
  const [q, setQ] = useState(null);
  useEffect(() => { api("/financiamento").then(setQ).catch(() => setQ(false)); }, []);
  if (!q || !q.total) return null;
  const inter = q.grupos.find((g) => g.fonte === "intercompany");
  return (
    <section className="cartao">
      <h3>Estratégia de financiamento (despesas de 2027)</h3>
      <div className="rolagem"><table className="tab">
        <thead><tr><th>Fonte</th><th className="n">Projetos</th><th className="n">Despesa 2027</th><th className="n">% do total</th></tr></thead>
        <tbody>{q.grupos.filter((g) => g.n).map((g) => <tr key={g.fonte || "x"} className={g.fonte === "" ? "extinta" : ""}><td>{g.nome}</td><td className="n">{g.n}</td><td className="n">{fmt(g.valor)}</td><td className="n">{(g.valor / q.total * 100).toFixed(1).replace(".", ",")}%</td></tr>)}</tbody>
        <tfoot><tr><td>Total</td><td className="n">{q.grupos.reduce((a, g) => a + g.n, 0)}</td><td className="n">{fmt(q.total)}</td><td className="n">100,0%</td></tr></tfoot></table></div>
      {inter && inter.n > 0 && <p className="mudo" style={{ marginBottom: 0 }}>Projetos custeados por transferência intercompany: {inter.projetos.map((x) => `${x.projeto} (${fmt(x.valor)})`).join("; ")}. A receita intercompany lançada é de {fmt(q.intercompany_receita)}, {q.intercompany_saldo >= 0 ? `com sobra de ${fmt(q.intercompany_saldo)}` : `faltando ${fmt(-q.intercompany_saldo)} para cobrir`}.</p>}
      {q.pendentes > 0 && <p className="mudo" style={{ marginBottom: 0 }}>{q.pendentes} projeto(s) ainda sem fonte indicada (linha em vermelho claro).</p>}
    </section>);
}

export default function Resumo({ plano, planoErro, recarregarPlano, admin, ir }) {
  const [r, setR] = useState(null);
  const [erro, setErro] = useState("");
  const [ger, setGer] = useState("");
  const [gerencias, setGerencias] = useState([]);
  const [conting, setConting] = useState(true);
  const fluxo = useFluxo(ger, conting);
  const [projetos, setProjetos] = useState(null);
  useEffect(() => { api("/projetos").then(setProjetos).catch(() => setProjetos([])); }, []);
  useEffect(() => { api("/resumo?contingenciados=" + conting + (ger ? `&gerencia=${encodeURIComponent(ger)}` : "")).then((x) => { setR(x); if (!ger) setGerencias(x.gerencias || []); }).catch((e) => setErro(e.message)); }, [ger, conting]);
  if (erro) return <p className="erro">{erro}</p>;
  if (!r) return <p>Carregando…</p>;
  const max = Math.max(1, ...r.mensal_plano.map((m) => m.valor));
  const psVisiveis = (projetos || []).filter((p) => p.tipo !== "receita" && !p.extinto && (conting || !p.contingenciado) && (!ger || (p.gerencia || "Sem gerência definida") === ger));
  const statusGer = admin && plano && plano.gerencias ? Object.fromEntries(plano.gerencias.filter((g) => g.nivel === "gerencia").map((g) => [g.gerencia || "Sem gerência definida", { pendencias: g.pendencias, concluida: g.concluido }])) : null;
  const s = r.linhas_status;
  const delta = r.total_plano - r.total_base;
  const receitas = ger || !conting ? (fluxo ? fluxo.total_receita : 0) : (plano ? plano.etapas.receitas.total : 0);
  const resultado = receitas - r.total_plano;
  return (
    <>
      <h2>{admin ? "Planejamento 2027" : "Meu planejamento 2027"}</h2>
      <MeuPlanejamento plano={plano} erro={planoErro} recarregar={recarregarPlano} admin={admin} ir={ir} />
      <h3 className="secao">Visão executiva do orçamento{ger ? `: ${ger}` : ""}</h3>
      <div className="filtros" style={{ margin: "0 0 10px", display: "flex", gap: 14, alignItems: "center", flexWrap: "wrap" }}>
        {gerencias.length > 1 && <FiltroGerencia valor={ger} onChange={setGer} opcoes={gerencias} largura={300} />}
        <label className="ent-check" style={{ margin: 0 }}><input type="checkbox" checked={conting} onChange={(e) => setConting(e.target.checked)} /> Incluir projetos contingenciados</label>
        {(ger || !conting) && <span className="mudo">Os números abaixo {ger ? `são só dos projetos desta gerência` : "consideram todos os projetos"}{!conting ? ", sem os contingenciados" : ""}.</span>}
      </div>
      <div className="kpis">
        <Kpi rotulo="Aprovado 2026" valor={mi(r.total_base)} tom="f26" sub="orçamento do ano corrente" />
        <Kpi rotulo="Executado 2026" valor={mi(r.total_realizado)} tom="f26" sub={`${pct(r.total_realizado, r.total_base)} do aprovado`} />
        <Kpi rotulo="Despesa planejada 2027" valor={mi(r.total_plano)} tom="f27" sub={<>{r.total_base ? ((delta / r.total_base) * 100).toFixed(1).replace(".", ",") + "% sobre o aprovado de 2026" : ""}</>} />
        <Kpi rotulo="Receita prevista 2027" valor={mi(receitas)} tom="f27" sub={plano ? `${plano.etapas.receitas.n} lançamento(s)` : ""} />
        <Kpi rotulo="Resultado 2027" valor={mi(resultado)} sub="receita menos despesa" tom={resultado < 0 ? "rneg" : "rpos"} />
        {r.teto > 0 && <Kpi rotulo="Teto PRO-RNP" valor={mi(r.teto)} sub={(r.total_plano <= r.teto ? "Dentro do teto: folga de " : "Acima do teto em ") + mi(Math.abs(r.teto - r.total_plano))} tom={r.total_plano <= r.teto ? "rpos" : "rneg"} />}
      </div>
      {projetos && <PorGerencia ps={psVisiveis} status={statusGer} />}
      {projetos && fluxo && fluxo.origens.length > 0 && <OrigemDosRecursos d={fluxo} ps={psVisiveis} />}
      <section className="cartao"><h3>Calendarização mensal do plano 2027 <span className="mudo" style={{ fontSize: ".8rem", fontWeight: 400 }}>(R$ mi)</span></h3>
          <div className="meses compacto">{r.mensal_plano.map((m) => (
            <div key={m.mes} title={fmt(m.valor)}><small className="val">{(m.valor / 1e6).toFixed(2).replace(".", ",")}</small><div className="col"><span style={{ height: (m.valor / max) * 100 + "%" }} /></div><small>{m.mes.slice(0, 3)}</small></div>))}</div>
      </section>
      {projetos && <ProjetosDoPlano ps={psVisiveis} abrir={(o) => ir("projetos", o)} verTodos={() => ir("projetos")} />}
      <Cobertura admin={admin} />
      <EstrategiaFinanciamento />
      {r.extintos && r.extintos.n > 0 && (
        <section className="cartao" style={{ borderLeft: "4px solid #E87722" }}>
          <h3>Ações extintas ({r.extintos.n})</h3>
          <p className="mudo" style={{ marginTop: 0 }}>Não terão orçamento próprio em 2027: as entregas migram para outros projetos. O aprovado e o executado de 2026 continuam contando nos totais desta página, e o valor delas em 2027 é zero (já está previsto nos projetos que recebem as entregas).</p>
          <table className="tabela"><thead><tr><th>Ação</th><th>Gerente</th><th className="n">Aprovado 2026</th><th className="n">Executado</th><th className="n">Plano 2027</th></tr></thead>
            <tbody>{r.extintos.lista.map((x) => <tr key={x.orcamento}><td>{x.orcamento} | {x.descricao}</td><td>{x.gerente}</td><td className="n">{fmt(x.aprovado_2026)}</td><td className="n">{fmt(x.executado_2026)}</td><td className="n">{fmt(0)}</td></tr>)}</tbody>
            <tfoot><tr><td colSpan="2">Total</td><td className="n">{fmt(r.extintos.aprovado_2026)}</td><td className="n">{fmt(r.extintos.executado_2026)}</td><td className="n">{fmt(0)}</td></tr></tfoot></table>
        </section>)}
      <details className="cartao" style={{ padding: "12px 16px" }}>
        <summary style={{ cursor: "pointer", fontWeight: 700 }}>Detalhamento: 2026 e 2027 por origem, finalidade e grupo de despesa</summary>
        <h4>Por origem de recurso e finalidade</h4><Quadro itens={r.por_origem} rotulo="Origem / finalidade" aninhado />
        <h4>Por grupo de despesa</h4><Quadro itens={r.por_grupo} rotulo="Grupo" />
        <p className="mudo">{s.ajustada + s.nova} linhas ajustadas ou novas, {s.mantida} mantidas de 2026, {s.viagens} vindas de viagens, eventos e headcount.</p>
      </details>
      <OutrosProjetos />
    </>
  );
}
