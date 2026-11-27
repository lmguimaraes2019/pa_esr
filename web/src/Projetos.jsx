import React, { useEffect, useState } from "react";
import { api, fmt } from "./api.js";
import OutrosProjetos from "./OutrosProjetos.jsx";
import { Delta, pct, Selo, Passos, FINALIDADES, nomeFinalidade, classeFinalidade, FiltroGerencia, celPrevisao, fmtV, semValor } from "./ui.jsx";

export function NovoOrcamento({ listas, onCriar, onFechar, tipoFixo }) {
  const [f, setF] = useState({ tipo: tipoFixo || "despesa", finalidade: "caixa", descricao: "", origem: "", gerente: "" });
  const [erro, setErro] = useState("");
  const salvar = async (e) => {
    e.preventDefault(); setErro("");
    try { await onCriar(f); } catch (x) { setErro(x.message); }
  };
  return (
    <form className="cartao" onSubmit={salvar}>
      <h3>{f.tipo === "receita" ? "Novo centro de receita 2027" : "Novo orçamento de despesa 2027"}</h3>
      <p className="mudo">{f.tipo === "receita" ? "O total deste orçamento entra como receita e gera resultado positivo. Ele não conta como despesa e não vai no Template de despesas do PMO." : "Orçamento de despesa: segue a jornada completa, com passado 2026, plano 2027, viagens, eventos e headcount."}</p>
      <p className="mudo">Não precisa de número agora: o orçamento nasce marcado como <span className="tag ok">novo</span>. Na exportação ao PMO ele segue como NOVO; depois do lançamento no PCO o administrador informa o Nº do Projeto.</p>
      <div className="grade">
        <label>Nome do orçamento<input value={f.descricao} onChange={(e) => setF({ ...f, descricao: e.target.value })} required minLength={3} placeholder="ex.: DSS-ESR-ASSOCIACAO-NOVO PROGRAMA" /></label>
        <label>Origem de recursos<select value={f.origem} onChange={(e) => setF({ ...f, origem: e.target.value })} required>
          <option value="">Selecione…</option>{listas.origens.map((o) => <option key={o}>{o}</option>)}</select></label>
        <label>Finalidade<select value={f.finalidade} onChange={(e) => setF({ ...f, finalidade: e.target.value })}>{FINALIDADES.map(([k, t]) => <option key={k} value={k}>{t}</option>)}</select></label>
        <label>Gerente do projeto<select value={f.gerente} onChange={(e) => setF({ ...f, gerente: e.target.value })} required>
          <option value="">Selecione…</option>{listas.gerentes.map((g) => <option key={g}>{g}</option>)}</select></label>
      </div>
      {erro && <p className="erro" role="alert">{erro}</p>}
      <div className="acoes"><button className="primario">Criar orçamento</button><button type="button" onClick={onFechar}>Cancelar</button></div>
    </form>
  );
}

// Visão para lançar os centros de custo no PCO (ERP da RNP): o que precisa ser criado, o que já tem Nº e o que ainda falta preencher
function LancamentoPCO({ ps, abrir }) {
  const [filtro, setFiltro] = useState("lancar");
  const [copiado, setCopiado] = useState(false);
  const base = ps.filter((p) => p.tipo !== "receita" && !p.extinto && !p.contingenciado && (p.total_2027 > 0 || p.novo));
  const semNum = (p) => p.novo || !p.n_projeto;
  const falta = (p) => p.pendencias.filter((x) => x !== "Nº do Projeto");
  const lista = base.filter((p) => filtro === "todos" || (filtro === "lancar" ? semNum(p) : !semNum(p)));
  const grupos = {};
  lista.forEach((p) => { (grupos[p.gerencia || "Sem gerência definida"] ||= []).push(p); });
  const nomes = Object.keys(grupos).sort((a, b) => (a === "Diretoria Adjunta" ? -1 : b === "Diretoria Adjunta" ? 1 : a.localeCompare(b, "pt-BR")));
  const total = lista.reduce((a, p) => a + p.total_2027, 0);
  const copiar = async () => {
    const linhas = [["Orçamento", "Nº do Projeto", "Centro de custo", "Projeto", "Gerente", "Origem", "Finalidade", "Plano 2027", "Situação"].join("\t"),
      ...lista.map((p) => [p.novo ? "novo" : p.orcamento, p.n_projeto || "", p.centro_custo || "", p.descricao, p.gerente, p.origem, nomeFinalidade(p.finalidade), String(p.total_2027).replace(".", ","), falta(p).length ? "Falta: " + falta(p).join(", ") : "Pronto"].join("\t"))];
    try { await navigator.clipboard.writeText(linhas.join("\n")); setCopiado(true); setTimeout(() => setCopiado(false), 2500); } catch { /* sem permissão de área de transferência */ }
  };
  const n = (f) => base.filter((p) => (f === "lancar" ? semNum(p) : !semNum(p))).length;
  return (
    <>
      <div className="nota">Cada projeto é um centro de custo a ser lançado no PCO. Aqui ficam os que ainda <strong>precisam de Nº do Projeto</strong>, com tudo o que o lançamento pede (nome, gerente, origem, finalidade e valor de 2027). Quando faltar algo, a coluna Situação diz o quê. Depois de lançar, o administrador informa o Nº na página do projeto.</div>
      <div className="filtros" style={{ margin: "8px 0", display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
        {[["lancar", `A lançar (${n("lancar")})`], ["lancados", `Já com Nº (${n("lancados")})`], ["todos", `Todos (${base.length})`]].map(([k, t]) => <button type="button" key={k} className={filtro === k ? "destaque" : ""} onClick={() => setFiltro(k)}>{t}</button>)}
        <span style={{ flex: 1 }} /><button type="button" onClick={copiar} disabled={!lista.length}>{copiado ? "Copiado" : "Copiar para planilha"}</button>
      </div>
      {!lista.length && <p className="mudo">Nenhum projeto neste filtro.</p>}
      {nomes.map((g) => (
        <section className="cartao" key={g} style={{ padding: "10px 14px" }}>
          <h3 style={{ margin: "0 0 6px" }}>{g} <span className="contagem">{grupos[g].length} {grupos[g].length === 1 ? "projeto" : "projetos"}</span></h3>
          <div className="rolagem"><table className="tab clic">
            <thead><tr><th>Orçamento</th><th>Projeto</th><th>Gerente</th><th>Origem</th><th className="n">Plano 2027</th><th>Nº do Projeto (PCO)</th><th>Situação</th></tr></thead>
            <tbody>{grupos[g].map((p) => (
              <tr key={p.orcamento} className="proj" onClick={() => abrir(p.orcamento)} tabIndex={0} onKeyDown={(e) => e.key === "Enter" && abrir(p.orcamento)}>
                <td>{p.novo ? <span className="tag ok">novo</span> : p.orcamento}</td><td>{p.descricao}<div className="sub-proj"><span className={"tag " + classeFinalidade(p.finalidade)}>{nomeFinalidade(p.finalidade)}</span></div></td>
                <td>{p.gerente}</td><td>{p.origem}</td><td className="n"><strong>{fmt(p.total_2027)}</strong></td>
                <td>{p.n_projeto ? p.n_projeto : <span className="tag aviso">a lançar</span>}</td>
                <td>{falta(p).length ? <span className="tag aviso" title={falta(p).join(", ")}>Falta: {falta(p).join(", ")}</span> : <span className="tag ok">Pronto</span>}</td>
              </tr>))}</tbody>
          </table></div>
        </section>))}
      {lista.length > 0 && <p className="mudo">{lista.length} projeto(s), plano 2027 de {fmt(total)}.</p>}
    </>
  );
}

export default function Projetos({ abrir, semEntregas, semFonte, limparFiltro }) {
  const [todos, setPs] = useState(null);
  const [fFin, setFFin] = useState("");
  const [fGer, setFGer] = useState("");
  const [erro, setErro] = useState("");
  const [novo, setNovo] = useState(false);
  const [listas, setListas] = useState(null);
  const [aba, setAba] = useState("despesas");
  const [mais, setMais] = useState(false);       // colunas extras: empenhado e % executado
  const [abertos, setAbertos] = useState({});      // gerências abertas: por padrão todas vêm recolhidas
  const [fechado, setFechado] = useState({});      // origens recolhidas dentro de uma gerência aberta
  useEffect(() => { api("/projetos").then(setPs).catch((e) => setErro(e.message)); api("/listas").then(setListas).catch(() => {}); }, []);
  if (erro) return <p className="erro">{erro}</p>;
  if (!todos) return <p>Carregando…</p>;
  const ps = todos.filter((p) => p.tipo !== "receita" && (!fGer || (p.gerencia || "Sem gerência definida") === fGer) && (!fFin || p.finalidade === fFin) && (!semEntregas || semEntregas.includes(p.orcamento)) && (!semFonte || semFonte.includes(p.orcamento)));
  const alternaGer = (k) => setAbertos((f) => ({ ...f, [k]: !f[k] }));
  const alterna = (k) => setFechado((f) => ({ ...f, [k]: !f[k] }));
  const ordem = (a, b) => a.localeCompare(b, "pt-BR");
  const agrupa = (lista, pre) => {
    const gm = {};
    lista.forEach((p) => { const g = p.gerencia || "Sem gerência definida", o = p.origem || "Sem origem"; ((gm[g] ||= {})[o] ||= []).push(p); });
    return Object.keys(gm).sort((a, b) => (a === "Diretoria Adjunta" ? -1 : b === "Diretoria Adjunta" ? 1 : a === "Sem gerência definida" ? 1 : b === "Sem gerência definida" ? -1 : ordem(a, b))).map((g) => {
      const origens = Object.keys(gm[g]).sort(ordem).map((o) => ({ chave: pre + g + "|" + o, nome: o, ps: gm[g][o] }));
      return { chave: pre + g, nome: g, origens, ps: origens.flatMap((o) => o.ps) };
    });
  };
  // três grupos: planejados (seguem para 2027), contingenciados (aguardam liberação) e extintos (sem orçamento em 2027)
  const ativos = ps.filter((p) => !p.extinto && !p.contingenciado), conting = ps.filter((p) => p.contingenciado && !p.extinto), inativos = ps.filter((p) => p.extinto);
  const gAtivos = agrupa(ativos, ""), gConting = agrupa(conting, "c:"), gInativos = agrupa(inativos, "x:");
  const todasChaves = [...gAtivos, ...gConting, ...gInativos].flatMap((g) => [g.chave, ...g.origens.map((o) => o.chave)]);
  const chavesGer = todasChaves.filter((k) => !k.includes("|")), chavesOrigem = todasChaves.filter((k) => k.includes("|"));
  const subtotal = (lista) => {
    const s = (k) => lista.reduce((a, p) => a + p[k], 0);
    const t26 = s("total_2026"), re = s("realizado_2026");
    return <><td className="n">{fmtV(t26)}</td>{mais && <td className="n">{fmtV(s("empenhado_2026"))}</td>}<td className="n">{fmtV(re)}</td><td className="n">{fmtV(t26 - re)}</td>{mais && <td className="n">{pct(re, t26)}</td>}{celPrevisao(lista)}
      <td className="n"><strong>{fmtV(s("total_2027"))}</strong></td><td className="n"><Delta de={t26} para={s("total_2027")} /></td></>;
  };
  const estado = (p) => p.extinto ? <span className="tag aviso" title="Não existirá no PA 2027">extinta</span>
    : p.contingenciado ? <span className="tag aviso" title="Orçamento contingenciado, não liberado para execução">contingenciado</span>
    : p.pendencias.length > 0 ? <span className="tag aviso" title={p.pendencias.join(", ")}>{p.pendencias.length} {p.pendencias.length === 1 ? "pendência" : "pendências"}</span> : null;
  const linhaProjeto = (p) => (
    <tr key={p.orcamento} className={"proj " + (p.planejamento_concluido && !p.extinto ? "concluido " : "") + (p.extinto ? "extinta" : "")} title={p.planejamento_concluido ? "O gestor marcou o planejamento como concluído" : undefined} onClick={() => abrir(p.orcamento)} tabIndex={0} onKeyDown={(e) => e.key === "Enter" && abrir(p.orcamento)}>
      <td>{p.novo ? <span className="tag ok">novo</span> : p.orcamento}</td><td>{p.n_projeto || semValor}</td><td>{p.centro_custo || semValor}</td>
      <td>{p.descricao}<div className="sub-proj"><span className={"tag " + classeFinalidade(p.finalidade)} title="Finalidade do orçamento">{nomeFinalidade(p.finalidade)}</span>
        {estado(p)}{p.replicado_para && <span className="mudo"> migrado para {p.replicado_para}</span>}{p.replicado_de && <span className="mudo"> replicado de {p.replicado_de}</span>}</div></td>
      <td>{p.gerente}</td>
      <td className="n">{fmtV(p.total_2026)}</td>{mais && <td className="n">{fmtV(p.empenhado_2026)}</td>}<td className="n">{fmtV(p.realizado_2026)}</td>
      <td className={"n " + (p.total_2026 - p.realizado_2026 < -0.5 ? "res-neg" : "")}>{fmt(p.total_2026 - p.realizado_2026)}</td>{mais && <td className="n">{pct(p.realizado_2026, p.total_2026)}</td>}{celPrevisao([p])}
      <td className="n"><strong>{fmtV(p.total_2027)}</strong></td><td className="n"><Delta de={p.total_2026} para={p.total_2027} /></td>
    </tr>
  );
  const tabela = (lista, grupos) => {
    const soma = (l, k) => l.reduce((a, p) => a + p[k], 0);
    return (
      <div className="rolagem"><table className="tab clic pa">
        <thead>
          <tr className="grupos"><th colSpan={5} style={{ background: "#fff" }} /><th colSpan={mais ? 7 : 5} className="g26"><Selo ano={2026} /></th><th colSpan={2} className="g27"><Selo ano={2027} /></th></tr>
          <tr><th>Orçamento</th><th title="Número do projeto no PCO">Nº projeto</th><th title="Centro de custo no PCO">Centro de custo</th><th>Projeto</th><th>Gerente</th><th className="n g26" title="Valor aprovado em 2026">Aprovado</th>{mais && <th className="n g26" title="Empenhado, ainda não realizado. Só informativo: não entra no saldo">Empenhado</th>}<th className="n g26">Realizado</th><th className="n g26" title="Aprovado menos realizado">Saldo</th>{mais && <th className="n g26">% real.</th>}<th className="n g26" title="Quanto o gestor prevê ter executado até 31/12/2026">Previsão 31/12</th><th className="n g26" title="Previsão de execução sobre o aprovado de 2026">% prev.</th><th className="n g27">Plano</th><th className="n g27" title="Diferença do plano 2027 para o aprovado de 2026">Δ vs 2026</th></tr>
        </thead>
        <tbody>{grupos.map((g) => (
          <React.Fragment key={g.chave}>
            <tr className="grupo-ger" onClick={() => alternaGer(g.chave)} tabIndex={0} onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), alternaGer(g.chave))} aria-expanded={!!abertos[g.chave]}>
              <td colSpan={5}><span className="seta">{abertos[g.chave] ? "▾" : "▸"}</span> <strong>{g.nome}</strong> <span className="contagem">{g.ps.length} {g.ps.length === 1 ? "projeto" : "projetos"}</span></td>{subtotal(g.ps)}</tr>
            {abertos[g.chave] && g.origens.map((o) => (
              <React.Fragment key={o.chave}>
                <tr className="grupo-org" onClick={() => alterna(o.chave)} tabIndex={0} onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), alterna(o.chave))} aria-expanded={!fechado[o.chave]}>
                  <td colSpan={5}><span className="seta">{fechado[o.chave] ? "▸" : "▾"}</span> {o.nome} <span className="contagem">{o.ps.length} {o.ps.length === 1 ? "projeto" : "projetos"}</span></td>{subtotal(o.ps)}</tr>
                {!fechado[o.chave] && o.ps.map(linhaProjeto)}
              </React.Fragment>))}
          </React.Fragment>))}</tbody>
        <tfoot><tr><td colSpan={5}>Total</td><td className="n">{fmtV(soma(lista, "total_2026"))}</td>{mais && <td className="n">{fmtV(soma(lista, "empenhado_2026"))}</td>}<td className="n">{fmtV(soma(lista, "realizado_2026"))}</td><td className="n">{fmtV(soma(lista, "total_2026") - soma(lista, "realizado_2026"))}</td>{mais && <td className="n">{pct(soma(lista, "realizado_2026"), soma(lista, "total_2026"))}</td>}{celPrevisao(lista)}<td className="n"><strong>{fmtV(soma(lista, "total_2027"))}</strong></td><td className="n"><Delta de={soma(lista, "total_2026")} para={soma(lista, "total_2027")} /></td></tr></tfoot>
      </table></div>
    );
  };
  return (
    <>
      <div className="cab"><div><h2>PA 2027 por projeto</h2>
        <p className="mudo">Abra um projeto para ver o que foi aprovado e executado em 2026 e ajustar o plano de 2027. Os projetos são centros de custo; as receitas ficam na página Receitas.</p></div>
        <div className="acoes"><a className="botao" href="/api/export/orcamento">Exportar planilha</a><button type="button" onClick={() => { setAbertos(Object.fromEntries(chavesGer.map((k) => [k, true]))); setFechado({}); }}>Expandir tudo</button><button type="button" onClick={() => setAbertos({})}>Recolher gerências</button><button type="button" onClick={() => { setAbertos(Object.fromEntries(chavesGer.map((k) => [k, true]))); setFechado(Object.fromEntries(chavesOrigem.map((k) => [k, true]))); }}>Recolher origens</button></div>
        {listas && <button className="destaque" onClick={() => setNovo(true)}>+ Novo orçamento</button>}</div>
      <Passos ativo={aba} onMudar={setAba} itens={[["despesas", "Planejamento de despesas"], ["pco", "Para lançar no PCO"]]} />
      {aba === "pco" ? <LancamentoPCO ps={todos} abrir={abrir} /> : <>
      {novo && listas && <NovoOrcamento listas={listas} onFechar={() => setNovo(false)} onCriar={async (b) => { const r = await api("/projetos", { method: "POST", body: b }); abrir(r.orcamento); }} />}
      {semEntregas && <div className="nota" style={{ display: "flex", gap: 12, alignItems: "center", justifyContent: "space-between" }}>
        <span>{ps.length ? <>Mostrando só os <strong>{ps.length}</strong> projeto(s) que ainda não têm entregas informadas. Abra cada um e use a aba "Entregas 2027". Projetos de gestão da área e de headcount não precisam de entregas.</> : "Todos os projetos já têm entregas informadas."}</span>
        <button type="button" onClick={limparFiltro}>Ver todos os projetos</button></div>}
      {semFonte && <div className="nota" style={{ display: "flex", gap: 12, alignItems: "center", justifyContent: "space-between" }}>
        <span>{ps.length ? <>Mostrando só os <strong>{ps.length}</strong> projeto(s) sem fonte de financiamento indicada. Abra cada um e escolha a fonte (intercompany, receita própria) ou A definir (TBD). Projetos de fomento já têm fonte.</> : "Todos os projetos já indicaram a fonte de financiamento."}</span>
        <button type="button" onClick={limparFiltro}>Ver todos os projetos</button></div>}
      <div className="filtros" style={{ margin: "8px 0" }}>
        <label className="ent-check" style={{ margin: "0 12px 0 0" }}><input type="checkbox" checked={mais} onChange={(e) => setMais(e.target.checked)} /> Mais colunas (empenhado e % realizado)</label>
        <FiltroGerencia valor={fGer} onChange={setFGer} opcoes={todos.filter((p) => p.tipo !== "receita").map((p) => p.gerencia || "Sem gerência definida")} />
        <select value={fFin} onChange={(e) => setFFin(e.target.value)} aria-label="Filtrar por finalidade"><option value="">Todas as finalidades</option>{FINALIDADES.map(([k, t]) => <option key={k} value={k}>{t}</option>)}</select>
      </div>
      {!ps.length && <p className="mudo">{todos.length ? "Nenhum projeto neste filtro." : "Nenhum projeto associado ao seu usuário. Crie um novo orçamento acima."}</p>}
      {ps.length > 0 && <div className="plano-resumo">
        {[["planejados", "Planejados", "plano", ativos, "Seguem para 2027"], ["contingenciados", "Contingenciados", "cont", conting, "Aguardam liberação"], ["extintos", "Extintos", "ext", inativos, "Sem orçamento em 2027"]].map(([id, nome, cor, l, sub]) => (
          <button type="button" key={id} className={cor} disabled={!l.length} onClick={() => document.getElementById("plano-" + id)?.scrollIntoView({ behavior: "smooth", block: "start" })}>
            <span>{nome} <b>{l.length}</b></span><strong>{fmtV(l.reduce((a, p) => a + p.total_2027, 0))}</strong><small>{sub} · aprovado 2026 {fmtV(l.reduce((a, p) => a + p.total_2026, 0))}</small></button>))}
      </div>}
      {[["planejados", "Projetos planejados", "plano", ativos, gAtivos, "Seguem para o plano de 2027."],
        ["contingenciados", "Projetos contingenciados", "cont", conting, gConting, "Orçamentos ainda não liberados para execução: ficam fora da exportação para o PCO e dos números do Resumo."],
        ["extintos", "Projetos extintos", "ext", inativos, gInativos, "Sem previsão de execução em 2027: as ações extintas migram suas entregas para outros projetos."]]
        .filter(([, , , l]) => l.length > 0).map(([id, titulo, cor, l, g, nota]) => {
          const t = (k) => l.reduce((a, p) => a + p[k], 0);
          return (
            <section key={id} id={"plano-" + id} className={"plano-sec " + cor}>
              <div className="plano-sec-cab">
                <div><h3>{titulo} <span className="contagem">{l.length}</span></h3><p className="mudo">{nota}</p></div>
                <div className="plano-sec-tot"><span>Aprovado 2026<strong>{fmtV(t("total_2026"))}</strong></span><span>Plano 2027<strong>{fmtV(t("total_2027"))}</strong></span><span>Variação<strong><Delta de={t("total_2026")} para={t("total_2027")} /></strong></span></div>
              </div>
              {tabela(l, g)}
            </section>);
        })}
      </>}
      <OutrosProjetos />
    </>
  );
}
