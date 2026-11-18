import React, { useCallback, useEffect, useState } from "react";
import { api, fmt, fmtN, lerNumero } from "./api.js";
import { Kpi, BotaoIcone, Lapis, Lixeira } from "./ui.jsx";

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
        origem: f.origem, destino: f.destino, pessoas: pessoas.filter((x) => x.trim()), justificativa: f.justificativa, edt: f.edt || "", tarefa: f.tarefa || "", site: f.site || "", rnp: !!f.rnp });
      onFechar();
    } catch (x) { setErro(x.message); }
  };
  return (
    <form className="cartao" id="form-evento" onSubmit={salvar}>
      <h3>{f.id ? "Editar evento" : "Novo evento 2027"}</h3>
      <p className="mudo">Campos com <Obrig /> são necessários para o evento ser considerado completo. Você pode salvar agora e completar depois.</p>
      <div className="grade">
        <label><span>Projeto que custeia <Obrig /></span><select value={f.orcamento} onChange={(e) => set("orcamento", e.target.value)} required>
          <option value="">Selecione…</option>{dados.projetos.map((p) => <option key={p.orcamento} value={p.orcamento}>{p.orcamento} | {p.descricao}</option>)}</select></label>
        <label><span>Nome do evento <Obrig /></span><input value={f.nome} onChange={(e) => set("nome", e.target.value)} /></label>
        <label className="ent-check"><input type="checkbox" checked={!!f.rnp} onChange={(e) => set("rnp", e.target.checked)} /> Evento da RNP</label>
        <label>Site do evento<input inputMode="url" value={f.site || ""} onChange={(e) => set("site", e.target.value)} placeholder="https://www.evento.com.br" /></label>
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
      <h4 className="sub">Viagem <span className="mudo">calculada com as tarifas da aba Viagens e lançada lá automaticamente, sem duplicar o valor</span></h4>
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
  const [tipoF, setTipoF] = useState("todos");
  const [erro, setErro] = useState("");
  const carregar = useCallback(() => api("/eventos").then(setDados).catch((e) => setErro(e.message)), []);
  useEffect(() => { carregar(); }, [carregar]);
  if (!dados) return erro ? <p className="erro">{erro}</p> : <p>Carregando…</p>;
  const t = dados.totais;
  const novo = { id: null, orcamento: proj !== "todos" ? proj : "", nome: "", local: "", tipo: "nac", mes: 1, n_pessoas: 1, dias: 1, pernoites: null, inscricao: null, moeda: "BRL", origem: "", destino: "", pessoas: [], justificativa: "", edt: "", tarefa: "", site: "", rnp: false };
  const lista = dados.itens.filter((e) => (proj === "todos" || e.orcamento === proj) && (!soPend || !e.completo)
    && (tipoF === "todos" || (tipoF === "rnp" ? e.rnp : e.tipo === tipoF)));
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
          <option value="todos">Todos os projetos</option>{dados.projetos.map((p) => <option key={p.orcamento} value={p.orcamento}>{p.orcamento} | {p.descricao}</option>)}</select>
          <select value={tipoF} onChange={(e) => setTipoF(e.target.value)} aria-label="Tipo de evento">
            <option value="todos">Todos os eventos ({dados.itens.length})</option>
            <option value="nac">Eventos nacionais ({dados.itens.filter((e) => e.tipo === "nac").length})</option>
            <option value="int">Eventos internacionais ({dados.itens.filter((e) => e.tipo === "int").length})</option>
            <option value="rnp">Eventos RNP ({dados.itens.filter((e) => e.rnp).length})</option></select></div>
        <button className="destaque" onClick={() => abrir(novo)}>+ Novo evento</button>
      </div>
      <div className="evt-lista">
        {lista.length === 0 && <p className="mudo">Nenhum evento neste filtro. Use "+ Novo evento".</p>}
        {lista.map((e) => (
          <article key={e.id} className={"evt " + (e.completo ? "" : "pend")}>
            <div className="evt-mes"><strong>{MESES_N[e.mes - 1].slice(0, 3)}</strong><small>2027</small></div>
            <div className="evt-corpo">
              <h4>{e.nome || <span className="up">sem nome</span>}
                <span className="tag">{e.tipo === "int" ? "internacional" : "nacional"}</span>{e.rnp && <span className="tag ok">RNP</span>}
                {e.completo ? <span className="tag ok">completo</span> : <span className="tag aviso">pendente</span>}</h4>
              <p className="evt-sub">{e.local || "local não informado"}{e.site && <> · <a href={e.site} target="_blank" rel="noopener noreferrer">site do evento</a></>}</p>
              <p className="evt-proj"><button className="link" onClick={() => irProjeto(e.orcamento)}>{e.orcamento}</button> <span className="mudo">{e.projeto}</span></p>
              {e.justificativa && <p className="evt-just" title={e.justificativa}>{e.justificativa}</p>}
              {e.pessoas.length > 0 && <details className="evt-pessoas"><summary>{e.n_pessoas} participante(s)</summary><div>{e.pessoas.map((p) => <span key={p} className="chip">{p}</span>)}</div></details>}
              {!e.completo && <div className="pend-lista">{e.faltando.map((x) => <span key={x}>{x}</span>)}</div>}
            </div>
            <div className="evt-num">
              <dl>
                <div><dt>Pessoas</dt><dd>{e.n_pessoas}</dd></div>
                <div><dt>Dias</dt><dd>{e.dias}</dd></div>
                <div><dt>Inscrição</dt><dd>{fmtN(e.inscricao_total)}{e.moeda === "USD" && <small>US$ {fmtN(e.inscricao)} por pessoa</small>}</dd></div>
                <div><dt>Viagem</dt><dd>{e.viagem.total ? fmtN(e.viagem.total) : "-"}{e.origem && <small>{e.origem} para {e.destino}</small>}</dd></div>
              </dl>
              <div className="evt-total"><span>Total</span><strong>{fmtN(e.total)}</strong></div>
            </div>
            <div className="barra-icones evt-acoes"><BotaoIcone icone={<Lapis />} dica="Editar o evento" onClick={() => abrir(e)} /><BotaoIcone icone={<Lixeira />} tom="perigo" dica="Excluir o evento" onClick={() => excluir(e)} /></div>
          </article>))}
      </div>
      <div className="evt-rodape"><span>Total do filtro ({lista.length} evento(s))</span>
        <span>Inscrições <strong>{fmtN(lista.reduce((a, e) => a + e.inscricao_total, 0))}</strong></span>
        <span>Viagens <strong>{fmtN(lista.reduce((a, e) => a + e.viagem.total, 0))}</strong></span>
        <span>Total <strong>{fmtN(lista.reduce((a, e) => a + e.total, 0))}</strong></span></div>
      {form && <Formulario key={form.id ?? "novo"} inicial={form} dados={dados} onFechar={() => setForm(null)} onSalvar={salvar} />}
      {dados.por_projeto.length > 0 && (
        <section className="cartao"><h3>Por projeto</h3><div className="rolagem"><table className="tab">
          <thead><tr><th>Projeto</th><th className="n">Eventos</th><th className="n">Pessoas</th><th className="n">Inscrições</th><th className="n">Viagens</th><th className="n">Total</th></tr></thead>
          <tbody>{dados.por_projeto.map((p) => <tr key={p.orcamento}><td><button className="link" onClick={() => irProjeto(p.orcamento)}>{p.orcamento}</button> {p.projeto}</td><td className="n">{p.eventos}</td><td className="n">{p.pessoas}</td><td className="n">{fmtN(p.inscricao)}</td><td className="n">{fmtN(p.viagem)}</td><td className="n"><strong>{fmtN(p.total)}</strong></td></tr>)}</tbody></table></div></section>)}
    </>
  );
}
