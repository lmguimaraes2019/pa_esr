import React, { useEffect, useState } from "react";
import { api, fmt } from "./api.js";
import { Delta, pct, Selo, FINALIDADES, nomeFinalidade, classeFinalidade } from "./ui.jsx";

function NovoOrcamento({ listas, onCriar, onFechar }) {
  const [f, setF] = useState({ tipo: "despesa", finalidade: "caixa", descricao: "", origem: "", gerente: "" });
  const [erro, setErro] = useState("");
  const salvar = async (e) => {
    e.preventDefault(); setErro("");
    try { await onCriar(f); } catch (x) { setErro(x.message); }
  };
  return (
    <form className="cartao" onSubmit={salvar}>
      <h3>Novo orçamento 2027</h3>
      <div className="passos" role="tablist" style={{ marginTop: 0 }}>
        {[["despesa", "Orçamento de despesa"], ["receita", "Orçamento de receita"]].map(([k, t]) => <button type="button" key={k} role="tab" aria-selected={f.tipo === k} className={f.tipo === k ? "on" : ""} onClick={() => setF({ ...f, tipo: k })}>{t}</button>)}</div>
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

export default function Projetos({ abrir, semEntregas, limparFiltro }) {
  const [todos, setPs] = useState(null);
  const [fFin, setFFin] = useState("");
  const [erro, setErro] = useState("");
  const [novo, setNovo] = useState(false);
  const [listas, setListas] = useState(null);
  const [fechado, setFechado] = useState({});      // grupos recolhidos (hook antes dos retornos antecipados)
  useEffect(() => { api("/projetos").then(setPs).catch((e) => setErro(e.message)); api("/listas").then(setListas).catch(() => {}); }, []);
  if (erro) return <p className="erro">{erro}</p>;
  if (!todos) return <p>Carregando…</p>;
  const ps = todos.filter((p) => (!fFin || p.finalidade === fFin) && (!semEntregas || semEntregas.includes(p.orcamento)));
  const soma = (k) => ps.filter((p) => p.tipo !== "receita").reduce((a, p) => a + p[k], 0);
  const somaT = (k) => ps.reduce((a, p) => a + p[k], 0);
  const alterna = (k) => setFechado((f) => ({ ...f, [k]: !f[k] }));
  const ordem = (a, b) => a.localeCompare(b, "pt-BR");
  const gm = {};
  ps.forEach((p) => { const g = p.gerencia || "Sem gerência definida", o = p.origem || "Sem origem"; ((gm[g] ||= {})[o] ||= []).push(p); });
  const grupos = Object.keys(gm).sort((a, b) => (a === "Diretoria Adjunta" ? -1 : b === "Diretoria Adjunta" ? 1 : a === "Sem gerência definida" ? 1 : b === "Sem gerência definida" ? -1 : ordem(a, b))).map((g) => {
    const origens = Object.keys(gm[g]).sort(ordem).map((o) => ({ chave: g + "|" + o, nome: o, ps: gm[g][o] }));
    return { chave: g, nome: g, origens, ps: origens.flatMap((o) => o.ps) };
  });
  const todasChaves = grupos.flatMap((g) => [g.chave, ...g.origens.map((o) => o.chave)]);
  const subtotal = (lista) => {
    const d = lista.filter((p) => p.tipo !== "receita");
    const s = (k, l = d) => l.reduce((a, p) => a + p[k], 0);
    const t26 = s("total_2026"), em = s("empenhado_2026"), re = s("realizado_2026"), rec = s("receitas_2027", lista), res = s("resultado_2027", lista);
    return <><td className="n">{fmt(t26)}</td><td className="n">{fmt(em)}</td><td className="n">{fmt(re)}</td><td className="n">{fmt(t26 - re - em)}</td><td className="n">{pct(re, t26)}</td>
      <td className="n">{fmt(s("total_2027"))}</td><td className="n"><Delta de={t26} para={s("total_2027")} /></td><td className="n">{rec ? <span className="res-pos">+{fmt(rec)}</span> : <span className="mudo">-</span>}</td><td className="n"><strong className={res > 0 ? "res-pos" : res < 0 ? "res-neg" : ""}>{fmt(res)}</strong></td></>;
  };
  const linhaProjeto = (p) => (
          <tr key={p.orcamento} className={"proj " + (p.planejamento_concluido ? "concluido" : "")} title={p.planejamento_concluido ? "O gestor marcou o planejamento como concluído" : undefined} onClick={() => abrir(p.orcamento)} tabIndex={0} onKeyDown={(e) => e.key === "Enter" && abrir(p.orcamento)}>
            <td>{p.novo ? <span className="tag ok">novo</span> : p.orcamento}</td>
            <td>{p.descricao} {p.tipo === "receita" && <span className="tag ok">receita</span>} <span className={"tag " + classeFinalidade(p.finalidade)} title="Finalidade do orçamento">{nomeFinalidade(p.finalidade)}</span> {p.contingenciado && <span className="tag aviso">contingenciado</span>} {p.extinto && <span className="tag aviso" title="Não existirá no PA 2027">extinta</span>} {p.replicado_para && <span className="tag ok" title={`${p.replicado_nome} | origem ${p.replicado_origem}`}>migrado para {p.replicado_para}</span>} {p.replicado_de && <span className="tag ok" title={`Replicado de ${p.replicado_de}`}>replicado de {p.replicado_de}</span>} {p.pendencias.length > 0 && <span className="tag aviso">sem Nº do Projeto</span>}</td>
            <td>{p.gerente}</td>
            <td className="n">{fmt(p.total_2026)}</td><td className="n">{fmt(p.empenhado_2026)}</td><td className="n">{fmt(p.realizado_2026)}</td><td className={"n " + (p.total_2026 - p.realizado_2026 - p.empenhado_2026 < -0.5 ? "res-neg" : "")}>{fmt(p.total_2026 - p.realizado_2026 - p.empenhado_2026)}</td><td className="n">{pct(p.realizado_2026, p.total_2026)}</td>
            {p.tipo === "receita"
              ? <><td className="n mudo">-</td><td className="n mudo">receita</td></>
              : <><td className="n"><strong>{fmt(p.total_2027)}</strong></td><td className="n"><Delta de={p.total_2026} para={p.total_2027} /></td></>}
            <td className="n">{p.receitas_2027 ? <span className="res-pos">+{fmt(p.receitas_2027)}</span> : <span className="mudo">-</span>}</td>
            <td className="n"><strong className={p.resultado_2027 > 0 ? "res-pos" : p.resultado_2027 < 0 ? "res-neg" : ""}>{fmt(p.resultado_2027)}</strong></td>
          </tr>
  );
  return (
    <>
      <div className="cab"><div><h2>PA 2027 por projeto</h2>
        <p className="mudo">Abra um projeto para ver o que foi aprovado e executado em 2026 e ajustar o plano de 2027. As receitas lançadas na página Receitas entram no projeto de destino.</p></div>
        <div className="acoes"><button type="button" onClick={() => setFechado({})}>Expandir tudo</button><button type="button" onClick={() => setFechado(Object.fromEntries(todasChaves.filter((k) => !k.includes("|")).map((k) => [k, true])))}>Recolher gerências</button><button type="button" onClick={() => setFechado(Object.fromEntries(todasChaves.filter((k) => k.includes("|")).map((k) => [k, true])))}>Recolher origens</button></div>
        {listas && <button className="destaque" onClick={() => setNovo(true)}>+ Novo orçamento</button>}</div>
      {novo && listas && <NovoOrcamento listas={listas} onFechar={() => setNovo(false)} onCriar={async (b) => { const r = await api("/projetos", { method: "POST", body: b }); abrir(r.orcamento); }} />}
      {semEntregas && <div className="nota" style={{ display: "flex", gap: 12, alignItems: "center", justifyContent: "space-between" }}>
        <span>{ps.length ? <>Mostrando só os <strong>{ps.length}</strong> projeto(s) que ainda não têm entregas informadas. Abra cada um e use a aba "Entregas 2027". Projetos de gestão da área e de headcount não precisam de entregas.</> : "Todos os projetos já têm entregas informadas."}</span>
        <button type="button" onClick={limparFiltro}>Ver todos os projetos</button></div>}
      <div className="filtros" style={{ margin: "8px 0" }}>
        <select value={fFin} onChange={(e) => setFFin(e.target.value)} aria-label="Filtrar por finalidade"><option value="">Todas as finalidades</option>{FINALIDADES.map(([k, t]) => <option key={k} value={k}>{t}</option>)}</select>
      </div>
      {!ps.length && <p className="mudo">{todos.length ? "Nenhum projeto neste filtro." : "Nenhum projeto associado ao seu usuário. Crie um novo orçamento acima."}</p>}
      <div className="rolagem"><table className="tab clic pa">
        <thead>
          <tr className="grupos"><th colSpan={3} style={{ background: "#fff" }} /><th colSpan={5} className="g26"><Selo ano={2026} /></th><th colSpan={4} className="g27"><Selo ano={2027} /></th></tr>
          <tr><th>Orçamento</th><th>Projeto</th><th>Gerente</th><th className="n g26" title="Valor aprovado em 2026">Planejado</th><th className="n g26" title="Valor já empenhado, ainda não realizado">Empenhado</th><th className="n g26" title="Valor realizado em 2026, sem o empenhado">Executado</th><th className="n g26" title="Planejado menos executado e empenhado">Saldo</th><th className="n g26" title="Executado dividido pelo planejado">% exec.</th><th className="n g27">Plano 2027</th><th className="n g27">Δ vs aprovado</th><th className="n g27" title="Receitas lançadas no projeto (previsão, transferências intercompany e orçamentos de receita)">Receitas 2027</th><th className="n g27" title="Receitas menos despesas do plano 2027">Resultado</th></tr>
        </thead>
        <tbody>{grupos.map((g) => (
          <React.Fragment key={g.chave}>
            <tr className="grupo-ger" onClick={() => alterna(g.chave)} tabIndex={0} onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), alterna(g.chave))} aria-expanded={!fechado[g.chave]}>
              <td colSpan={3}><span className="seta">{fechado[g.chave] ? "▸" : "▾"}</span> <strong>{g.nome}</strong> <span className="contagem">{g.ps.length} {g.ps.length === 1 ? "projeto" : "projetos"}</span></td>{subtotal(g.ps)}</tr>
            {!fechado[g.chave] && g.origens.map((o) => (
              <React.Fragment key={o.chave}>
                <tr className="grupo-org" onClick={() => alterna(o.chave)} tabIndex={0} onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), alterna(o.chave))} aria-expanded={!fechado[o.chave]}>
                  <td colSpan={3}><span className="seta">{fechado[o.chave] ? "▸" : "▾"}</span> {o.nome} <span className="contagem">{o.ps.length} {o.ps.length === 1 ? "projeto" : "projetos"}</span></td>{subtotal(o.ps)}</tr>
                {!fechado[o.chave] && o.ps.map(linhaProjeto)}
              </React.Fragment>))}
          </React.Fragment>))}</tbody>
        <tfoot><tr><td colSpan={3}>Total</td><td className="n">{fmt(soma("total_2026"))}</td><td className="n">{fmt(soma("empenhado_2026"))}</td><td className="n">{fmt(soma("realizado_2026"))}</td><td className="n">{fmt(soma("total_2026") - soma("realizado_2026") - soma("empenhado_2026"))}</td><td className="n">{pct(soma("realizado_2026"), soma("total_2026"))}</td><td className="n">{fmt(soma("total_2027"))}</td><td className="n"><Delta de={soma("total_2026")} para={soma("total_2027")} /></td><td className="n"><span className="res-pos">+{fmt(somaT("receitas_2027"))}</span></td><td className="n"><strong className={somaT("resultado_2027") < 0 ? "res-neg" : "res-pos"}>{fmt(somaT("resultado_2027"))}</strong></td></tr></tfoot>
      </table></div>
    </>
  );
}
