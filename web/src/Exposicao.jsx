import React, { useCallback, useEffect, useState } from "react";
import { api, fmtN, lerNumero } from "./api.js";
import { Kpi, BotaoIcone, Lapis, Lixeira } from "./ui.jsx";

const SIMNAO = ["", "Sim", "Não"];
const vazio = (orc) => ({ id: null, orcamento: orc || "", sc_andamento: "", diretoria: "DSS", gerencia: "ESR", ponto_focal: "", tipo: "", processo: "", descricao: "", fabricante: "", canal: "", moeda: "USD", valor: "", pais_origem: "", trimestre: 1, conecta: "", previsao_sc: "" });

function Formulario({ inicial, dados, onSalvar, onFechar }) {
  const [f, setF] = useState({ ...inicial, valor: inicial.valor ? String(inicial.valor).replace(".", ",") : "" });
  const [erro, setErro] = useState("");
  const set = (k, v) => setF((x) => ({ ...x, [k]: v }));
  const valor = lerNumero(f.valor);
  const brl = (Number.isNaN(valor) ? 0 : valor) * (dados.cambio[f.moeda] || 0);
  const salvar = async (e) => {
    e.preventDefault(); setErro("");
    if (f.valor === "" || Number.isNaN(valor) || valor <= 0) return setErro("Informe o valor total na moeda escolhida.");
    try {
      await onSalvar({ orcamento: f.orcamento, sc_andamento: f.sc_andamento, diretoria: f.diretoria, gerencia: f.gerencia, ponto_focal: f.ponto_focal, tipo: f.tipo, processo: f.processo,
        descricao: f.descricao, fabricante: f.fabricante, canal: f.canal, moeda: f.moeda, valor, pais_origem: f.pais_origem, trimestre: Number(f.trimestre), conecta: f.conecta, previsao_sc: f.previsao_sc });
      onFechar();
    } catch (x) { setErro(x.message); }
  };
  return (
    <form className="cartao" id="form-exposicao" onSubmit={salvar}>
      <h3>{f.id ? "Editar exposição cambial" : "Nova exposição cambial 2027"}</h3>
      <div className="grade">
        <label>CC/Projeto<select value={f.orcamento} onChange={(e) => set("orcamento", e.target.value)} required>
          <option value="">Selecione…</option>{dados.projetos.map((p) => <option key={p.orcamento} value={p.orcamento}>{p.orcamento} | {p.descricao}</option>)}</select></label>
        <label>Descrição do produto ou serviço<input value={f.descricao} onChange={(e) => set("descricao", e.target.value)} placeholder="ex.: Hardware diversos" /></label>
        <label>Tipo<input list="tipos-exp" value={f.tipo} onChange={(e) => set("tipo", e.target.value)} placeholder="HW, SW, SV…" /><datalist id="tipos-exp">{dados.tipos.map((t) => <option key={t}>{t}</option>)}</datalist></label>
        <label>Ponto focal (pessoa responsável)<input value={f.ponto_focal} onChange={(e) => set("ponto_focal", e.target.value)} /></label>
        <label>Moeda<select value={f.moeda} onChange={(e) => set("moeda", e.target.value)}><option value="USD">Dólar (USD)</option><option value="EUR">Euro (EUR)</option></select></label>
        <label>Valor total {f.moeda}<input inputMode="decimal" value={f.valor} onChange={(e) => set("valor", e.target.value)} placeholder="ex.: 3.000,00" required />
          {brl > 0 && <small className="mudo">≈ R$ {fmtN(brl)} no câmbio de {fmtN(dados.cambio[f.moeda])}</small>}</label>
        <label>País de origem<input value={f.pais_origem} onChange={(e) => set("pais_origem", e.target.value)} placeholder="ex.: EUA" /></label>
        <label>Trimestre<select value={f.trimestre} onChange={(e) => set("trimestre", e.target.value)}>{dados.trimestres.map((t) => <option key={t.n} value={t.n}>{t.nome}</option>)}</select></label>
        <label>Fabricante/fornecedor<input value={f.fabricante} onChange={(e) => set("fabricante", e.target.value)} /></label>
        <label>Canal/distribuidor<input value={f.canal} onChange={(e) => set("canal", e.target.value)} /></label>
        <label>SC em andamento?<select value={f.sc_andamento} onChange={(e) => set("sc_andamento", e.target.value)}>{SIMNAO.map((x) => <option key={x} value={x}>{x || "Selecione…"}</option>)}</select></label>
        <label>Processo (ADC ou SC de referência)<input value={f.processo} onChange={(e) => set("processo", e.target.value)} /></label>
        <label>Previsão de abertura de SC<input value={f.previsao_sc} onChange={(e) => set("previsao_sc", e.target.value)} placeholder="ex.: mar/2027" /></label>
        <label>Referente ao Programa CONECTA?<select value={f.conecta} onChange={(e) => set("conecta", e.target.value)}>{SIMNAO.map((x) => <option key={x} value={x}>{x || "Selecione…"}</option>)}</select></label>
        <label>Diretoria<input value={f.diretoria} onChange={(e) => set("diretoria", e.target.value)} /></label>
        <label>Gerência<input value={f.gerencia} onChange={(e) => set("gerencia", e.target.value)} /></label>
      </div>
      {erro && <p className="erro" role="alert">{erro}</p>}
      <div className="acoes"><button className="primario">Salvar</button><button type="button" onClick={onFechar}>Cancelar</button></div>
    </form>
  );
}

export default function Exposicao({ irProjeto }) {
  const [dados, setDados] = useState(null);
  const [form, setForm] = useState(null);
  const [proj, setProj] = useState("todos");
  const [erro, setErro] = useState("");
  const carregar = useCallback(() => api("/exposicao").then(setDados).catch((e) => setErro(e.message)), []);
  useEffect(() => { carregar(); }, [carregar]);
  if (!dados) return erro ? <p className="erro">{erro}</p> : <p>Carregando…</p>;
  const t = dados.totais;
  const lista = dados.itens.filter((i) => proj === "todos" || i.orcamento === proj);
  const abrir = (i) => { setForm(i); setTimeout(() => document.getElementById("form-exposicao")?.scrollIntoView({ behavior: "smooth", block: "center" }), 50); };
  const salvar = async (b) => { if (form.id) await api(`/exposicao/${form.id}`, { method: "PUT", body: b }); else await api("/exposicao", { method: "POST", body: b }); carregar(); };
  const excluir = async (i) => {
    if (!window.confirm(`Excluir "${i.descricao || "item sem descrição"}" (${i.moeda} ${fmtN(i.valor)})?`)) return;
    try { setErro(""); await api(`/exposicao/${i.id}`, { method: "DELETE" }); carregar(); } catch (x) { setErro(x.message); }
  };
  return (
    <>
      <h2>Exposição ao dólar 2027</h2>
      <div className="nota">Cadastre as compras previstas em moeda estrangeira (dólar ou euro), indicando o projeto, o tipo, o valor, o país de origem e o trimestre. A planilha gerada segue o formato da área responsável pela exposição cambial.</div>
      <div className="kpis">
        <Kpi rotulo="Total em dólar" valor={"US$ " + fmtN(t.usd)} sub={`≈ R$ ${fmtN(t.brl_usd)} (câmbio ${fmtN(dados.cambio.USD)})`} tom="f27" />
        <Kpi rotulo="Total em euro" valor={"€ " + fmtN(t.eur)} sub={dados.cambio.EUR ? `≈ R$ ${fmtN(t.brl_eur)} (câmbio ${fmtN(dados.cambio.EUR)})` : ""} tom="f27" />
        <Kpi rotulo="Itens" valor={t.itens} sub={t.incompletos ? `${t.incompletos} com informações pendentes` : "todos completos"} tom="f27" />
      </div>
      <section className="cartao"><h3>Por trimestre</h3><div className="rolagem"><table className="tab">
        <thead><tr><th>Trimestre</th><th className="n">Itens</th><th className="n">USD</th><th className="n">EUR</th></tr></thead>
        <tbody>{dados.por_trimestre.map((q) => <tr key={q.trimestre}><td>{q.nome}</td><td className="n">{q.itens}</td><td className="n">{q.usd ? fmtN(q.usd) : "-"}</td><td className="n">{q.eur ? fmtN(q.eur) : "-"}</td></tr>)}</tbody></table></div></section>
      {erro && <p className="erro" role="alert">{erro}</p>}
      <div className="barra-ferramentas">
        <div className="filtros"><select style={{ width: 320 }} value={proj} onChange={(e) => setProj(e.target.value)}>
          <option value="todos">Todos os projetos</option>{dados.projetos.map((p) => <option key={p.orcamento} value={p.orcamento}>{p.orcamento} | {p.descricao}</option>)}</select></div>
        <a className="botao" href="/api/exposicao/xlsx" download>Baixar planilha (.xlsx)</a>
        <button className="destaque" onClick={() => abrir(vazio(proj !== "todos" ? proj : ""))}>+ Nova exposição</button>
      </div>
      <p className="legenda-icones"><span><Lapis /> editar</span><span className="perigo"><Lixeira /> excluir</span></p>
      <div className="rolagem"><table className="tab pa-exp">
        <thead><tr><th>Ações</th><th>Descrição</th><th>Tipo</th><th>CC/Projeto</th><th>Ponto focal</th><th>Moeda</th><th className="n">Valor</th><th>País</th><th>Trimestre</th><th>SC</th><th>CONECTA</th><th>Situação</th></tr></thead>
        <tbody>
          {lista.length === 0 && <tr><td colSpan={12} className="mudo">Nenhuma exposição neste filtro. Use "+ Nova exposição".</td></tr>}
          {lista.map((i) => (
            <tr key={i.id}>
              <td style={{ whiteSpace: "nowrap" }}><div className="barra-icones"><BotaoIcone icone={<Lapis />} dica="Editar" onClick={() => abrir(i)} /><BotaoIcone icone={<Lixeira />} tom="perigo" dica="Excluir" onClick={() => excluir(i)} /></div></td>
              <td><strong>{i.descricao || <span className="up">sem descrição</span>}</strong>{(i.fabricante || i.canal) && <><br /><span className="mudo">{[i.fabricante, i.canal].filter(Boolean).join(" | ")}</span></>}</td>
              <td>{i.tipo}</td>
              <td><button className="link" onClick={() => irProjeto(i.orcamento)}>{i.orcamento}</button><br /><span className="mudo">{i.projeto}</span></td>
              <td>{i.ponto_focal}</td>
              <td>{i.moeda}</td>
              <td className="n"><strong>{fmtN(i.valor)}</strong></td>
              <td>{i.pais_origem}</td>
              <td>{dados.trimestres.find((q) => q.n === i.trimestre)?.nome.replace(" TRIMESTRE 2027", "º tri")}</td>
              <td>{i.sc_andamento}{i.previsao_sc && <><br /><span className="mudo">{i.previsao_sc}</span></>}</td>
              <td>{i.conecta}</td>
              <td>{i.completo ? <span className="tag ok">completo</span> : <><span className="tag aviso">pendente</span><div className="pend-lista">{i.faltando.map((x) => <span key={x}>{x}</span>)}</div></>}</td>
            </tr>))}
        </tbody>
      </table></div>
      {form && <Formulario key={form.id ?? "novo"} inicial={form} dados={dados} onFechar={() => setForm(null)} onSalvar={salvar} />}
    </>
  );
}
