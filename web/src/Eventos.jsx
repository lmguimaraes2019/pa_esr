import React, { useCallback, useEffect, useState } from "react";
import { api, fmt, fmtN, lerNumero } from "./api.js";
import { TarefaOrc, Kpi, BotaoIcone, Lapis, Lixeira } from "./ui.jsx";

const MESES_N = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];

// mesma regra do servidor (app/viagens.py), usada na prévia do formulário
function custoViagem(tipo, t, n, dias, pern, bv) {
  if (!t || dias < 1 || n < 1) return 0;
  const p = pern === "" || pern == null ? Math.max(dias - 1, 0) : Math.max(Number(pern), 0);
  return t.passagem * n + t.bagagem * n * bv + p * t.hospedagem * n + t.ajuda_custo * dias * n + t.aux_transporte * n + (tipo === "int" ? t.seguro * n : 0);
}

const Obrig = () => <span className="obrig" title="Informação obrigatória">*</span>;

function Formulario({ inicial, dados, onSalvar, onFechar }) {
  const [f, setF] = useState({ ...inicial, inscricao: inicial.inscricao == null ? "" : String(inicial.inscricao).replace(".", ","), pernoites: inicial.pernoites ?? "" });
  const [erro, setErro] = useState("");
  const set = (k, v) => setF((x) => ({ ...x, [k]: v }));
  const n = Math.max(Number(f.n_pessoas) || 1, 1);
  const origens = [...new Set(dados.tarifas.filter((t) => t.tipo === f.tipo).map((t) => t.origem))];
  const destinos = dados.tarifas.filter((t) => t.tipo === f.tipo && t.origem === f.origem).map((t) => t.destino);
  const tarifa = dados.tarifas.find((t) => t.tipo === f.tipo && t.origem === f.origem && t.destino === f.destino);
  const viagem = custoViagem(f.tipo, tarifa, n, Number(f.dias), f.pernoites, dados.bagagem_vezes);
  const insc = lerNumero(f.inscricao);
  const inscBrl = (Number.isNaN(insc) ? 0 : insc) * (f.moeda === "USD" ? dados.dolar : 1) * n;
  const pessoas = Array.from({ length: n }, (_, i) => f.pessoas[i] || "");
  const salvar = async (e) => {
    e.preventDefault(); setErro("");
    if (f.inscricao !== "" && (Number.isNaN(insc) || insc < 0)) return setErro("Informe um custo de inscrição válido (use 0 se o evento é gratuito).");
    try {
      await onSalvar({ orcamento: f.orcamento, nome: f.nome, local: f.local, tipo: f.tipo, mes: Number(f.mes), n_pessoas: n, dias: Number(f.dias),
        pernoites: f.pernoites === "" ? null : Number(f.pernoites), inscricao: f.inscricao === "" ? null : insc, moeda: f.moeda,
        origem: f.origem, destino: f.destino, pessoas: pessoas.filter((x) => x.trim()), justificativa: f.justificativa, edt: f.edt || "", tarefa: f.tarefa || "" });
      onFechar();
    } catch (x) { setErro(x.message); }
  };
  return (
    <form className="cartao" id="form-evento" onSubmit={salvar}>
      <h3>{f.id ? "Editar evento" : "Novo evento 2027"}</h3>
      <p className="mudo">Campos com <Obrig /> são necessários para o evento ser considerado completo. Você pode salvar agora e completar depois.</p>
      <div className="grade">
        <label><span>Projeto que custeia <Obrig /></span><select value={f.orcamento} onChange={(e) => setF((x) => ({ ...x, orcamento: e.target.value, edt: "", tarefa: "" }))} required>
          <option value="">Selecione…</option>{dados.projetos.map((p) => <option key={p.orcamento} value={p.orcamento}>{p.orcamento} | {p.descricao}</option>)}</select></label>
        <TarefaOrc dados={dados} orcamento={f.orcamento} edt={f.edt} tarefa={f.tarefa} onChange={(a, b) => setF((x) => ({ ...x, edt: a, tarefa: b }))} />
        <label><span>Nome do evento <Obrig /></span><input value={f.nome} onChange={(e) => set("nome", e.target.value)} /></label>
        <label><span>Local (cidade e país) <Obrig /></span><input value={f.local} onChange={(e) => set("local", e.target.value)} placeholder="ex.: Recife, Brasil" /></label>
        <label><span>Abrangência <Obrig /></span><select value={f.tipo} onChange={(e) => setF((x) => ({ ...x, tipo: e.target.value, origem: "", destino: "" }))}>
          <option value="nac">Nacional</option><option value="int">Internacional</option></select></label>
        <label>Mês do evento<select value={f.mes} onChange={(e) => set("mes", e.target.value)}>{MESES_N.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}</select></label>
        <label><span>Quantas pessoas participam <Obrig /></span><input type="number" min="1" max="200" value={f.n_pessoas} onChange={(e) => set("n_pessoas", e.target.value)} required /></label>
        <label><span>Quantos dias <Obrig /></span><input type="number" min="1" max="60" value={f.dias} onChange={(e) => set("dias", e.target.value)} required /></label>
        <label>Pernoites (opcional)<input type="number" min="0" value={f.pernoites} placeholder={`padrão ${Math.max(Number(f.dias) - 1, 0)}`} onChange={(e) => set("pernoites", e.target.value)} /></label>
      </div>
      <h4 className="sub">Custo de inscrição</h4>
      <div className="grade">
        <label><span>Valor por pessoa <Obrig /></span><input value={f.inscricao} inputMode="decimal" onChange={(e) => set("inscricao", e.target.value)} placeholder="0 se for gratuito" /></label>
        <label>Moeda<select value={f.moeda} onChange={(e) => set("moeda", e.target.value)}><option value="BRL">Real (R$)</option><option value="USD">Dólar (US$, câmbio {fmtN(dados.dolar)})</option></select></label>
      </div>
      <h4 className="sub">Viagem <span className="mudo">calculada com as tarifas da aba Viagens</span></h4>
      <div className="grade">
        <label><span>Origem <Obrig /></span><select value={f.origem} onChange={(e) => setF((x) => ({ ...x, origem: e.target.value, destino: "" }))}><option value="">Selecione…</option>{origens.map((o) => <option key={o}>{o}</option>)}</select></label>
        <label><span>Destino <Obrig /></span><select value={f.destino} onChange={(e) => set("destino", e.target.value)}><option value="">Selecione…</option>{destinos.map((o) => <option key={o}>{o}</option>)}</select></label>
      </div>
      <h4 className="sub">Quem participa <Obrig /></h4>
      <div className="grade">{pessoas.map((nome, i) => (
        <label key={i}>Pessoa {i + 1}<input value={nome} onChange={(e) => setF((x) => { const p = [...pessoas]; p[i] = e.target.value; return { ...x, pessoas: p }; })} /></label>))}</div>
      <label><span>Justificativa <Obrig /></span><textarea rows={3} value={f.justificativa} onChange={(e) => set("justificativa", e.target.value)} placeholder="Por que a ESR deve participar? Qual o resultado esperado?" /></label>
      <div className="resumo-custo">
        <span>Inscrições <strong>{fmt(inscBrl)}</strong></span><span>Viagem <strong>{tarifa ? fmt(viagem) : "defina origem e destino"}</strong></span>
        <span>Total do evento <strong>{fmt(inscBrl + viagem)}</strong></span>
      </div>
      {erro && <p className="erro" role="alert">{erro}</p>}
      <div className="acoes"><button className="primario">Salvar evento</button><button type="button" onClick={onFechar}>Cancelar</button></div>
    </form>
  );
}

export default function Eventos({ irProjeto }) {
  const [dados, setDados] = useState(null);
  const [form, setForm] = useState(null);
  const [proj, setProj] = useState("todos");
  const [soPend, setSoPend] = useState(false);
  const [erro, setErro] = useState("");
  const carregar = useCallback(() => api("/eventos").then(setDados).catch((e) => setErro(e.message)), []);
  useEffect(() => { carregar(); }, [carregar]);
  if (!dados) return erro ? <p className="erro">{erro}</p> : <p>Carregando…</p>;
  const t = dados.totais;
  const novo = { id: null, orcamento: proj !== "todos" ? proj : "", nome: "", local: "", tipo: "nac", mes: 1, n_pessoas: 1, dias: 1, pernoites: null, inscricao: null, moeda: "BRL", origem: "", destino: "", pessoas: [], justificativa: "", edt: "", tarefa: "" };
  const lista = dados.itens.filter((e) => (proj === "todos" || e.orcamento === proj) && (!soPend || !e.completo));
  const abrir = (e) => { setForm(e); setTimeout(() => document.getElementById("form-evento")?.scrollIntoView({ behavior: "smooth", block: "center" }), 50); };
  const salvar = async (b) => { if (form.id) await api(`/eventos/${form.id}`, { method: "PUT", body: b }); else await api("/eventos", { method: "POST", body: b }); carregar(); };
  const excluir = async (e) => {
    if (!window.confirm(`Excluir o evento "${e.nome || "sem nome"}" (${fmt(e.total)})?`)) return;
    try { setErro(""); await api(`/eventos/${e.id}`, { method: "DELETE" }); carregar(); } catch (x) { setErro(x.message); }
  };
  const max = Math.max(1, ...dados.mensal.map((m) => m.valor));
  return (
    <>
      <h2>Participação em eventos 2027</h2>
      <div className="nota"><strong>Para cada evento, informe:</strong> nome do evento, quantas pessoas participam, local, se é nacional ou internacional, custo de inscrição, quantos dias, trecho da viagem (o custo vem das tarifas da aba Viagens), nome das pessoas que participarão e a justificativa. Eventos com informação faltando ficam marcados como pendentes.</div>
      <div className="kpis">
        <Kpi rotulo="Eventos" valor={t.eventos} sub={`${t.pessoas} participações`} tom="f27" />
        <Kpi rotulo="Inscrições" valor={fmt(t.inscricao)} tom="f27" />
        <Kpi rotulo="Viagens" valor={fmt(t.viagem)} tom="f27" />
        <Kpi rotulo="Total em eventos" valor={fmt(t.total)} tom="f27" sub={t.incompletos ? `${t.incompletos} com pendências` : "todos completos"} />
      </div>
      <section className="cartao"><h3>Custo por mês</h3>
        <div className="meses">{dados.mensal.map((m) => (
          <div key={m.mes} title={`${m.mes}: ${fmt(m.valor)}`}><div className="col"><span style={{ height: (m.valor / max) * 100 + "%" }} /></div><small>{m.mes.slice(0, 3)}</small></div>))}</div></section>
      {t.incompletos > 0 && <div className="nota aviso"><strong>{t.incompletos} evento(s) com informações pendentes.</strong> <button className="link" onClick={() => setSoPend(!soPend)}>{soPend ? "Mostrar todos" : "Mostrar só os pendentes"}</button></div>}
      {erro && <p className="erro" role="alert">{erro}</p>}
      <div className="barra-ferramentas">
        <div className="filtros"><select style={{ width: 320 }} value={proj} onChange={(e) => setProj(e.target.value)}>
          <option value="todos">Todos os projetos</option>{dados.projetos.map((p) => <option key={p.orcamento} value={p.orcamento}>{p.orcamento} | {p.descricao}</option>)}</select></div>
        <button className="destaque" onClick={() => abrir(novo)}>+ Novo evento</button>
      </div>
      <p className="legenda-icones"><span><Lapis /> editar o evento</span><span className="perigo"><Lixeira /> excluir</span></p>
      <div className="rolagem"><table className="tab">
        <thead><tr><th>Ações</th><th>Mês</th><th>Evento</th><th>Projeto</th><th className="n">Pessoas</th><th className="n">Dias</th><th className="n">Inscrição</th><th className="n">Viagem</th><th className="n">Total</th><th>Situação</th></tr></thead>
        <tbody>
          {lista.length === 0 && <tr><td colSpan={10} className="mudo">Nenhum evento neste filtro. Use "+ Novo evento".</td></tr>}
          {lista.map((e) => (
            <tr key={e.id}>
              <td style={{ whiteSpace: "nowrap" }}><div className="barra-icones"><BotaoIcone icone={<Lapis />} dica="Editar o evento" onClick={() => abrir(e)} /><BotaoIcone icone={<Lixeira />} tom="perigo" dica="Excluir o evento" onClick={() => excluir(e)} /></div></td>
              <td>{MESES_N[e.mes - 1].slice(0, 3)}</td>
              <td><strong>{e.nome || <span className="up">sem nome</span>}</strong> <span className="tag">{e.tipo === "int" ? "internacional" : "nacional"}</span><br /><span className="mudo">{e.local || "local não informado"}</span>
                {e.justificativa && <><br /><span className="mudo" title={e.justificativa}>{e.justificativa.length > 90 ? e.justificativa.slice(0, 90) + "…" : e.justificativa}</span></>}</td>
              <td><button className="link" onClick={() => irProjeto(e.orcamento)}>{e.orcamento}</button><br /><span className="mudo">{e.projeto}</span>{e.tarefa && <><br /><span className="mudo" style={{ fontSize: ".76rem" }}>entra em: {e.tarefa}</span></>}</td>
              <td className="n">{e.n_pessoas}<br /><span className="mudo" style={{ fontSize: ".75rem" }}>{e.pessoas.join(", ")}</span></td>
              <td className="n">{e.dias}</td>
              <td className="n">{fmtN(e.inscricao_total)}{e.moeda === "USD" && <><br /><span className="mudo">US$ {fmtN(e.inscricao)} por pessoa</span></>}</td>
              <td className="n">{e.viagem.total ? fmtN(e.viagem.total) : "-"}{e.origem && <><br /><span className="mudo" style={{ fontSize: ".75rem" }}>{e.origem} para {e.destino}</span></>}</td>
              <td className="n"><strong>{fmtN(e.total)}</strong></td>
              <td>{e.completo ? <span className="tag ok">completo</span> : <><span className="tag aviso">pendente</span><div className="pend-lista">{e.faltando.map((x) => <span key={x}>{x}</span>)}</div></>}</td>
            </tr>))}
        </tbody>
        <tfoot><tr><td colSpan={6}>Total do filtro</td><td className="n">{fmtN(lista.reduce((a, e) => a + e.inscricao_total, 0))}</td><td className="n">{fmtN(lista.reduce((a, e) => a + e.viagem.total, 0))}</td><td className="n">{fmtN(lista.reduce((a, e) => a + e.total, 0))}</td><td /></tr></tfoot>
      </table></div>
      {form && <Formulario key={form.id ?? "novo"} inicial={form} dados={dados} onFechar={() => setForm(null)} onSalvar={salvar} />}
      {dados.por_projeto.length > 0 && (
        <section className="cartao"><h3>Por projeto</h3><div className="rolagem"><table className="tab">
          <thead><tr><th>Projeto</th><th className="n">Eventos</th><th className="n">Pessoas</th><th className="n">Inscrições</th><th className="n">Viagens</th><th className="n">Total</th></tr></thead>
          <tbody>{dados.por_projeto.map((p) => <tr key={p.orcamento}><td><button className="link" onClick={() => irProjeto(p.orcamento)}>{p.orcamento}</button> {p.projeto}</td><td className="n">{p.eventos}</td><td className="n">{p.pessoas}</td><td className="n">{fmtN(p.inscricao)}</td><td className="n">{fmtN(p.viagem)}</td><td className="n"><strong>{fmtN(p.total)}</strong></td></tr>)}</tbody></table></div></section>)}
    </>
  );
}
