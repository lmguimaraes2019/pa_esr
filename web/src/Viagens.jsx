import React, { useCallback, useEffect, useMemo, useState } from "react";
import { api, fmt, fmtN, lerNumero } from "./api.js";
import { Kpi, Delta, Passos, Selo } from "./ui.jsx";

const MESES_N = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];
const COMP = [["passagem", "passagens"], ["hospedagem", "hospedagem"], ["ajuda_custo", "diárias"], ["aux_transporte", "transporte"], ["seguro", "seguro"]];

// mesma regra do servidor (app/viagens.py), usada só para a prévia no formulário
function custo(tipo, t, n, dias, pern, bv) {
  if (!t || dias < 1 || n < 1) return 0;
  const p = pern === "" || pern == null ? Math.max(dias - 1, 0) : Math.max(Number(pern), 0);
  return t.passagem * n + t.bagagem * n * bv + p * t.hospedagem * n + t.ajuda_custo * dias * n + t.aux_transporte * n + (tipo === "int" ? t.seguro * n : 0);
}

function Formulario({ inicial, dados, tarifas, bv, onSalvar, onFechar }) {
  const [f, setF] = useState(inicial);
  const [erro, setErro] = useState("");
  const set = (k, v) => setF((x) => ({ ...x, [k]: v }));
  const opts = dados.opcoes;
  const origens = [...new Set(opts.tarifas.filter((t) => t.tipo === f.tipo).map((t) => t.origem))];
  const destinos = opts.tarifas.filter((t) => t.tipo === f.tipo && t.origem === f.origem).map((t) => t.destino);
  const projeto = opts.projetos.find((p) => p.orcamento === f.orcamento);
  const tarifa = tarifas.find((t) => t.tipo === f.tipo && t.origem === f.origem && t.destino === f.destino);
  const prev = custo(f.tipo, tarifa, Number(f.n_viagens), Number(f.dias), f.pernoites, bv);
  const trocarTipo = (tipo) => setF((x) => ({ ...x, tipo, origem: "", destino: "" }));
  const trocarProjeto = (o) => {
    const pr = opts.projetos.find((p) => p.orcamento === o);
    const sug = pr?.tarefas.filter((t) => /viage/i.test(t.tarefa));
    setF((x) => ({ ...x, orcamento: o, edt: sug?.length === 1 ? sug[0].edt : "", tarefa: sug?.length === 1 ? sug[0].tarefa : "" }));
  };
  const salvar = async (e) => {
    e.preventDefault(); setErro("");
    try {
      await onSalvar({ tipo: f.tipo, mes: Number(f.mes), origem: f.origem, destino: f.destino, n_viagens: Number(f.n_viagens), dias: Number(f.dias),
        pernoites: f.pernoites === "" || f.pernoites == null ? null : Number(f.pernoites), objetivo: f.objetivo, area: f.area,
        orcamento: f.orcamento || null, edt: f.edt || null, tarefa: f.tarefa || null });
    } catch (x) { setErro(x.message); }
  };
  return (
    <form className="cartao" id="form-viagem" onSubmit={salvar}>
      <h3>{f.id ? "Editar viagem" : "Nova viagem"}</h3>
      <div className="grade">
        <label>Tipo<select value={f.tipo} onChange={(e) => trocarTipo(e.target.value)}><option value="nac">Nacional</option><option value="int">Internacional</option></select></label>
        <label>Mês<select value={f.mes} onChange={(e) => set("mes", e.target.value)}>{MESES_N.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}</select></label>
        <label>Origem<select value={f.origem} onChange={(e) => setF((x) => ({ ...x, origem: e.target.value, destino: "" }))} required><option value="">Selecione…</option>{origens.map((o) => <option key={o}>{o}</option>)}</select></label>
        <label>Destino<select value={f.destino} onChange={(e) => set("destino", e.target.value)} required><option value="">Selecione…</option>{destinos.map((o) => <option key={o}>{o}</option>)}</select></label>
        <label>Nº de viagens (pessoas)<input type="number" min="1" value={f.n_viagens} onChange={(e) => set("n_viagens", e.target.value)} required /></label>
        <label>Dias<input type="number" min="1" value={f.dias} onChange={(e) => set("dias", e.target.value)} required /></label>
        <label>Pernoites<input type="number" min="0" value={f.pernoites ?? ""} placeholder={`padrão ${Math.max(Number(f.dias) - 1, 0)}`} onChange={(e) => set("pernoites", e.target.value)} /></label>
        <label>Área<input value={f.area} onChange={(e) => set("area", e.target.value)} placeholder="ex.: GADM" /></label>
      </div>
      <div className="grade">
        <label>Objetivo da viagem<input value={f.objetivo} onChange={(e) => set("objetivo", e.target.value)} /></label>
        <label>Projeto que paga<select value={f.orcamento || ""} onChange={(e) => trocarProjeto(e.target.value)}><option value="">Definir depois</option>{opts.projetos.map((p) => <option key={p.orcamento} value={p.orcamento}>{p.orcamento} | {p.nome}</option>)}</select></label>
        <label>Tarefa do orçamento<select disabled={!projeto} value={f.edt ? `${f.edt}||${f.tarefa}` : ""} onChange={(e) => { const [edt, tarefa] = e.target.value.split("||"); setF((x) => ({ ...x, edt, tarefa })); }}>
          <option value="">Selecione…</option>{projeto?.tarefas.map((t) => <option key={t.edt + t.tarefa} value={`${t.edt}||${t.tarefa}`}>{t.tarefa}</option>)}</select></label>
      </div>
      <p><strong>Custo estimado: {fmt(prev)}</strong> {!tarifa && f.origem && f.destino && <span className="erro">sem tarifa para esse trecho</span>}</p>
      {erro && <p className="erro" role="alert">{erro}</p>}
      <div className="acoes"><button className="primario">Salvar</button><button type="button" onClick={onFechar}>Cancelar</button></div>
    </form>
  );
}

function PlanoViagens({ dados, tarifas, recarregar }) {
  const [edit, setEdit] = useState(null);
  const abrir = (v) => { setEdit(v); setTimeout(() => document.getElementById("form-viagem")?.scrollIntoView({ behavior: "smooth", block: "center" }), 50); };
  const [tipo, setTipo] = useState("todas");
  const [proj, setProj] = useState("todos");
  const [soPend, setSoPend] = useState(false);
  const [erro, setErro] = useState("");
  const lista = dados.viagens.filter((v) => (tipo === "todas" || v.tipo === tipo) && (proj === "todos" || (v.orcamento || "") === proj)
    && (!soPend || !v.orcamento || !v.edt || !v.tem_tarifa));
  const novo = { tipo: "nac", mes: 1, origem: "", destino: "", n_viagens: 1, dias: 3, pernoites: null, objetivo: "", area: "", orcamento: "", edt: "", tarefa: "" };
  const salvar = async (corpo) => {
    if (edit.id) await api(`/viagens/${edit.id}`, { method: "PUT", body: corpo }); else await api("/viagens", { method: "POST", body: corpo });
    setEdit(null); recarregar();
  };
  const excluir = async (v) => {
    if (!window.confirm(`Excluir a viagem ${v.origem} para ${v.destino} (${fmt(v.custo.total)})?`)) return;
    try { await api(`/viagens/${v.id}`, { method: "DELETE" }); recarregar(); } catch (e) { setErro(e.message); }
  };
  const total = lista.reduce((a, v) => a + v.custo.total, 0);
  return (
    <>
      <div className="nota">Cada linha é uma viagem (ou um grupo de pessoas indo ao mesmo destino). O custo vem das <strong>tarifas</strong> da aba ao lado: passagem + bagagem, hospedagem por pernoite, diárias por dia, transporte e seguro. A linha cinza mostra o custo da mesma viagem na planilha de 2026.</div>
      {dados.totais.pendentes > 0 && <div className="nota aviso"><strong>{dados.totais.pendentes} viagem(ns) sem projeto, tarefa ou tarifa.</strong> Elas não entram no orçamento até serem completadas. <button className="link" onClick={() => setSoPend(true)}>Mostrar só as pendentes</button></div>}
      {edit && <Formulario inicial={edit} dados={dados} tarifas={tarifas} bv={dados.bagagem_vezes} onSalvar={salvar} onFechar={() => setEdit(null)} />}
      <div className="acoes" style={{ justifyContent: "space-between" }}>
        <div className="filtros" style={{ margin: 0 }}>
          {[["todas", "Todas"], ["nac", "Nacionais"], ["int", "Internacionais"]].map(([k, n]) => <button key={k} className={tipo === k ? "on" : ""} onClick={() => setTipo(k)}>{n}</button>)}
          <select style={{ width: 260 }} value={proj} onChange={(e) => setProj(e.target.value)}>
            <option value="todos">Todos os projetos</option>{dados.projetos.map((p) => <option key={p.orcamento} value={p.orcamento}>{p.orcamento ? `${p.orcamento} | ${p.projeto}` : "Sem projeto definido"}</option>)}</select>
          {soPend && <button className="on" onClick={() => setSoPend(false)}>Só pendentes ✕</button>}
        </div>
        <button className="destaque" onClick={() => abrir(novo)}>+ Nova viagem</button>
      </div>
      {erro && <p className="erro">{erro}</p>}
      <div className="rolagem">
        <table className="tab">
          <thead><tr><th>Mês</th><th>Trecho</th><th className="n">Viag.</th><th className="n">Dias</th><th>Objetivo</th><th>Projeto e tarefa</th><th>Composição do custo</th><th className="n">Custo 2027</th><th className="n">2026</th><th /></tr></thead>
          <tbody>
            {lista.length === 0 && <tr><td colSpan={10} className="mudo">Nenhuma viagem neste filtro.</td></tr>}
            {lista.map((v) => (
              <tr key={v.id}>
                <td>{MESES_N[v.mes - 1].slice(0, 3)}</td>
                <td>{v.origem} <span className="mudo">para</span> {v.destino} {v.tipo === "int" && <span className="tag nova">int.</span>}</td>
                <td className="n">{v.n_viagens}</td><td className="n">{v.dias}</td>
                <td style={{ maxWidth: 280 }}>{v.objetivo}{v.area && <span className="tag">{v.area}</span>}</td>
                <td>{v.orcamento ? <>{v.orcamento} | {v.projeto}<br /><span className="mudo">{v.tarefa || <span className="up">tarefa pendente</span>}</span></> : <span className="tag aviso">sem projeto</span>}</td>
                <td><div className="custos">{COMP.filter(([k]) => v.custo[k] > 0).map(([k, n]) => <span key={k}>{n} {fmtN(v.custo[k])}</span>)}</div>{!v.tem_tarifa && <span className="erro">sem tarifa</span>}</td>
                <td className="n"><strong>{fmtN(v.custo.total)}</strong></td>
                <td className="n mudo">{v.ref_2026 == null ? "nova" : fmtN(v.ref_2026)}</td>
                <td style={{ whiteSpace: "nowrap" }}><button className="link" onClick={() => abrir({ ...v, pernoites: v.pernoites })}>editar</button><button className="link" onClick={() => excluir(v)}>✕</button></td>
              </tr>))}
          </tbody>
          <tfoot><tr><td colSpan={7}>Total do filtro</td><td className="n">{fmtN(total)}</td><td className="n">{fmtN(lista.reduce((a, v) => a + (v.ref_2026 || 0), 0))}</td><td /></tr></tfoot>
        </table>
      </div>
    </>
  );
}

function Tarifas({ admin, tarifas, recarregar, premissas, recarregarPrem }) {
  const [vals, setVals] = useState({});
  const [msg, setMsg] = useState("");
  const [erro, setErro] = useState("");
  const [perc, setPerc] = useState("");
  const [bag, setBag] = useState(String(premissas?.viagens_bagagem_vezes?.valor ?? 1).replace(".", ","));
  const campos = [["passagem", "Passagem ida/volta"], ["hospedagem", "Hospedagem (pernoite)"], ["bagagem", "Bagagem"], ["aux_transporte", "Transporte"], ["ajuda_custo", "Diária"], ["seguro", "Seguro"]];
  const v = (t, k) => vals[t.id]?.[k] ?? String(t[k]).replace(".", ",");
  const salvar = async (t) => {
    setErro(""); setMsg("");
    const corpo = Object.fromEntries(campos.map(([k]) => [k, lerNumero(v(t, k))]));
    if (Object.values(corpo).some((x) => Number.isNaN(x) || x < 0)) return setErro("Use apenas números positivos nas tarifas.");
    try { await api(`/viagens/tarifas/${t.id}`, { method: "PUT", body: corpo }); setVals((x) => { const { [t.id]: _, ...r } = x; return r; }); setMsg(`Tarifa ${t.origem} para ${t.destino} salva.`); recarregar(); } catch (e) { setErro(e.message); }
  };
  const reajustar = async (simular) => {
    setErro(""); setMsg("");
    const p = lerNumero(perc);
    if (Number.isNaN(p)) return setErro("Informe o percentual, por exemplo 5 ou 4,5.");
    if (!simular && !window.confirm(`Substituir TODAS as tarifas pelos valores de 2026 acrescidos de ${perc}%? Ajustes manuais nas tarifas serão perdidos.`)) return;
    try { const r = await api("/viagens/tarifas/reajuste", { method: "POST", body: { percentual: p, simular } }); setMsg(simular ? `O reajuste atingiria ${r.tarifas_afetadas} tarifas.` : `${r.tarifas_afetadas} tarifas reajustadas em ${perc}% sobre 2026.`); if (!simular) recarregar(); } catch (e) { setErro(e.message); }
  };
  const salvarBag = async () => {
    setErro("");
    const b = lerNumero(bag);
    if (Number.isNaN(b) || b < 0 || b > 4) return setErro("A bagagem deve ficar entre 0 e 4 vezes.");
    try { await api("/premissas", { method: "PUT", body: { reajuste_pessoal: premissas.reajuste_pessoal.valor, reajuste_geral: premissas.reajuste_geral.valor, dolar: premissas.dolar.valor, viagens_bagagem_vezes: b } }); setMsg("Premissa da bagagem salva."); recarregarPrem(); recarregar(); } catch (e) { setErro(e.message); }
  };
  const bloco = (tipo, titulo) => (
    <section className="cartao"><h3>{titulo}</h3>
      <div className="rolagem"><table className="tab">
        <thead><tr><th>Origem</th><th>Destino</th>{campos.filter(([k]) => tipo === "int" || k !== "seguro").map(([k, n]) => <th key={k} className="n">{n}</th>)}<th>2026 (passagem)</th>{admin && <th />}</tr></thead>
        <tbody>{tarifas.filter((t) => t.tipo === tipo).map((t) => (
          <tr key={t.id}><td>{t.origem}</td><td>{t.destino}</td>
            {campos.filter(([k]) => tipo === "int" || k !== "seguro").map(([k]) => (
              <td key={k} className="n">{admin ? <input className="mini cel" style={{ borderColor: "var(--bd)" }} value={v(t, k)} inputMode="decimal" onChange={(e) => setVals((x) => ({ ...x, [t.id]: { ...x[t.id], [k]: e.target.value } }))} /> : fmtN(t[k])}</td>))}
            <td className="n mudo">{fmtN(t.ref_passagem)}</td>
            {admin && <td><button className="link" disabled={!vals[t.id]} onClick={() => salvar(t)}>salvar</button></td>}</tr>))}</tbody>
      </table></div></section>
  );
  return (
    <>
      <div className="nota">Tarifas médias por trecho, vindas da aba APOIO da planilha de viagens. Os valores de 2027 começam iguais aos de 2026. {admin ? "Edite uma tarifa ou aplique um reajuste geral." : "Apenas o administrador altera tarifas."}</div>
      {msg && <p className="ok">{msg}</p>}{erro && <p className="erro">{erro}</p>}
      {admin && (
        <div className="duas">
          <section className="cartao" style={{ margin: 0 }}><h3>Reajuste geral das tarifas</h3>
            <p className="mudo">Aplica o percentual sobre os valores de 2026 e substitui os de 2027.</p>
            <div className="acoes"><div className="com-sufixo"><input style={{ width: 90 }} value={perc} onChange={(e) => setPerc(e.target.value)} placeholder="5,0" inputMode="decimal" /><em>%</em></div>
              <button onClick={() => reajustar(true)}>Simular</button><button className="primario" onClick={() => reajustar(false)} disabled={!perc}>Aplicar</button></div></section>
          <section className="cartao" style={{ margin: 0 }}><h3>Bagagem: quantas vezes entra no custo</h3>
            <p className="mudo">No consolidado de 2026 a bagagem foi somada duas vezes (já estava dentro da passagem). Use 1 para contar uma vez, ou 2 para repetir o critério de 2026.</p>
            <div className="acoes"><input style={{ width: 90 }} value={bag} onChange={(e) => setBag(e.target.value)} inputMode="decimal" /><button className="primario" onClick={salvarBag}>Salvar</button></div></section>
        </div>)}
      {bloco("nac", "Viagens nacionais (por região)")}
      {bloco("int", "Viagens internacionais")}
    </>
  );
}

function LigacaoOrcamento({ dados, admin, recarregar, irProjeto }) {
  const [prev, setPrev] = useState(null);
  const [msg, setMsg] = useState("");
  const [erro, setErro] = useState("");
  const rodar = async (simular) => {
    setErro(""); setMsg("");
    if (!simular && !window.confirm("Aplicar o plano de viagens ao orçamento 2027? As linhas de viagens dos projetos serão substituídas pelos valores do plano.")) return;
    try {
      const r = await api("/viagens/aplicar", { method: "POST", body: { simular } });
      if (simular) setPrev(r); else { setPrev(null); setMsg(`Plano aplicado: ${r.itens.length} linhas do orçamento atualizadas (de ${fmt(r.total_antes)} para ${fmt(r.total_depois)}).`); recarregar(); }
    } catch (e) { setErro(e.message); }
  };
  const t = dados.totais;
  return (
    <>
      <div className="nota">Quando o plano estiver pronto, "aplicar ao orçamento" calcula cada viagem e lança os valores, mês a mês, nas contas de passagens, hospedagem, diárias e transporte da tarefa escolhida em cada projeto. Essas linhas passam a vir do plano de viagens (ficam travadas na tela do orçamento) e podem ser reaplicadas sempre que o plano mudar.</div>
      <div className="kpis">
        <Kpi rotulo="Aprovado em 2026 (viagens)" valor={fmt(t.aprovado)} tom="f26" />
        <Kpi rotulo="Executado em 2026" valor={fmt(t.executado)} tom="f26" />
        <Kpi rotulo="Plano de viagens 2027" valor={fmt(t.plano)} tom="f27" />
        <Kpi rotulo="Hoje no orçamento 2027" valor={fmt(t.orcamento)} tom="f27" sub={Math.abs(t.plano - t.orcamento) < 0.01 ? "conectado ao plano" : "diferente do plano"} />
      </div>
      {msg && <p className="ok">{msg}</p>}{erro && <p className="erro">{erro}</p>}
      <div className="rolagem">
        <table className="tab">
          <thead><tr><th>Projeto</th><th className="n">Aprovado 2026</th><th className="n">Executado 2026</th><th className="n">Planilha 2026</th><th className="n">Plano de viagens 2027</th><th className="n">Orçamento 2027 hoje</th><th>Situação</th></tr></thead>
          <tbody>{dados.projetos.map((p) => (
            <tr key={p.orcamento}><td>{p.orcamento ? <><button className="link" onClick={() => irProjeto(p.orcamento)}>{p.orcamento}</button> {p.projeto}</> : p.projeto}</td>
              <td className="n">{fmtN(p.aprovado_2026)}</td><td className="n">{fmtN(p.executado_2026)}</td><td className="n">{fmtN(p.planilha_2026)}</td>
              <td className="n"><strong>{fmtN(p.plano_2027)}</strong></td><td className="n">{fmtN(p.orcamento_2027)}</td>
              <td>{p.conectado ? <span className="tag ok">conectado</span> : <span className="tag aviso">diferença {fmtN(p.plano_2027 - p.orcamento_2027)}</span>}</td></tr>))}</tbody>
        </table>
      </div>
      {admin ? (
        <div className="acoes" style={{ marginTop: 14 }}><button onClick={() => rodar(true)}>Pré-visualizar a ligação</button>
          <button className="destaque" onClick={() => rodar(false)}>Aplicar o plano ao orçamento 2027</button></div>
      ) : <p className="mudo">A ligação com o orçamento é feita pelo administrador.</p>}
      {prev && (
        <section className="cartao"><h3>Pré-visualização</h3>
          {prev.bloqueado ? <><p className="erro">Não é possível aplicar ainda:</p><ul className="avisos">{prev.erros.map((e, i) => <li key={i} className="erro">{e}</li>)}</ul></> : (
            <>
              <p>As linhas de viagens dos projetos passam de <strong>{fmt(prev.total_antes)}</strong> para <strong>{fmt(prev.total_depois)}</strong>.</p>
              {prev.itens.some((i) => i.manual) && <div className="nota aviso">Algumas linhas tinham valores digitados à mão (marcadas abaixo) e serão substituídas pelo plano.</div>}
              <div className="rolagem"><table className="tab"><thead><tr><th>Projeto</th><th>Tarefa</th><th>Conta</th><th className="n">2026 aprovado</th><th className="n">Hoje</th><th className="n">Com o plano</th><th /></tr></thead>
                <tbody>{prev.itens.map((i, k) => (<tr key={k}><td>{i.orcamento}</td><td>{i.tarefa}</td><td>{i.conta_desc}</td><td className="n">{fmtN(i.ref_2026)}</td><td className="n">{fmtN(i.antes)}</td><td className="n"><strong>{fmtN(i.depois)}</strong></td><td>{i.manual && <span className="tag aviso">manual</span>}</td></tr>))}</tbody></table></div>
            </>)}
        </section>)}
    </>
  );
}

export default function Viagens({ admin, irProjeto }) {
  const [dados, setDados] = useState(null);
  const [tarifas, setTarifas] = useState([]);
  const [prem, setPrem] = useState(null);
  const [aba, setAba] = useState("plano");
  const [erro, setErro] = useState("");
  const carregar = useCallback(() => api("/viagens").then(setDados).catch((e) => setErro(e.message)), []);
  const carregarTarifas = useCallback(() => api("/viagens/tarifas").then(setTarifas), []);
  const carregarPrem = useCallback(() => api("/premissas").then(setPrem), []);
  useEffect(() => { carregar(); carregarTarifas(); carregarPrem(); }, [carregar, carregarTarifas, carregarPrem]);
  if (erro) return <p className="erro">{erro}</p>;
  if (!dados || !prem) return <p>Carregando…</p>;
  const t = dados.totais;
  const max = Math.max(1, ...dados.mensal.map((m) => Math.max(m.plano, m.ref)));
  return (
    <>
      <h2>Planejamento de viagens 2027</h2>
      <div className="kpis">
        <Kpi rotulo="Plano 2027" valor={fmt(t.plano)} tom="f27" sub={`${t.viagens} viagens`} />
        <Kpi rotulo="Planilha de 2026" valor={fmt(t.ref)} tom="f26" sub={<Delta de={t.ref} para={t.plano} />} />
        <Kpi rotulo="Aprovado em 2026" valor={fmt(t.aprovado)} tom="f26" />
        <Kpi rotulo="Executado em 2026" valor={fmt(t.executado)} tom="f26" />
      </div>
      <section className="cartao"><h3>Custo mensal das viagens</h3>
        <div className="legenda"><span><i style={{ background: "var(--laranja)" }} />Plano 2027</span><span><i style={{ background: "var(--cinza-claro)" }} />Planilha 2026</span></div>
        <div className="meses">{dados.mensal.map((m) => (
          <div key={m.mes} title={`${m.mes}: ${fmt(m.plano)} (2026: ${fmt(m.ref)})`}><div className="col" style={{ gap: 2 }}>
            <span style={{ height: (m.ref / max) * 100 + "%", background: "var(--cinza-claro)" }} /><span style={{ height: (m.plano / max) * 100 + "%" }} /></div><small>{m.mes.slice(0, 3)}</small></div>))}</div>
      </section>
      <Passos ativo={aba} onMudar={setAba} itens={[["plano", "Planejar as viagens"], ["tarifas", "Tarifas"], ["orcamento", "Levar ao orçamento"]]} />
      {aba === "plano" && <PlanoViagens dados={dados} tarifas={tarifas} recarregar={carregar} />}
      {aba === "tarifas" && <Tarifas admin={admin} tarifas={tarifas} recarregar={() => { carregarTarifas(); carregar(); }} premissas={prem} recarregarPrem={carregarPrem} />}
      {aba === "orcamento" && <LigacaoOrcamento dados={dados} admin={admin} recarregar={carregar} irProjeto={irProjeto} />}
    </>
  );
}
