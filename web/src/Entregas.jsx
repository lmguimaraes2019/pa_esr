import React, { useCallback, useEffect, useState } from "react";
import { api } from "./api.js";

const MESES_N = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];
const KPIS_SUGERIDOS = ["Alunos capacitados", "Vagas ofertadas", "Taxa de conclusão (%)", "Satisfação / NPS", "Cursos lançados", "Turmas realizadas", "Parceiros ativos",
  "Receita gerada (R$)", "Entregas no prazo (%)", "Disponibilidade do serviço (%)", "Pessoas treinadas", "Eventos realizados"];

function Chip({ tom, children, title }) {
  return <span className={"chip " + tom} title={title}>{children}</span>;
}

function FormEntrega({ inicial, catalogo, onSalvar, onCancelar }) {
  const [f, setF] = useState(inicial);
  const [erro, setErro] = useState("");
  const set = (k, v) => setF((x) => ({ ...x, [k]: v }));
  const alterna = (id) => setF((x) => ({ ...x, estrategia: x.estrategia.includes(id) ? x.estrategia.filter((i) => i !== id) : [...x.estrategia, id] }));
  const salvar = async (e) => {
    e.preventDefault(); setErro("");
    try { await onSalvar({ descricao: f.descricao, mes: Number(f.mes), kpi: f.kpi, meta: f.meta, estrategia: f.estrategia }); } catch (x) { setErro(x.message); }
  };
  const grupos = [["po", "Plano de Operação (resultados-chave)", "po"], ["cg", "Contrato de Gestão (indicadores)", "cg"]];
  return (
    <form className="ent-form" onSubmit={salvar}>
      <label><span>Entrega prevista <span className="obrig">*</span></span>
        <textarea rows={3} value={f.descricao} onChange={(e) => set("descricao", e.target.value)} required minLength={3} maxLength={1000}
          placeholder="O que será entregue? Seja específico: produto, serviço ou resultado concreto, e para quem." /></label>
      <div className="grade">
        <label>Mês previsto<select value={f.mes} onChange={(e) => set("mes", e.target.value)}>
          <option value={0}>Sem mês definido</option>{MESES_N.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}</select></label>
        <label>KPI da entrega<input list="kpis-sugeridos" value={f.kpi} onChange={(e) => set("kpi", e.target.value)} maxLength={200} placeholder="Como saber que deu certo? Ex.: Alunos capacitados" /></label>
        <label>Meta do KPI<input value={f.meta} onChange={(e) => set("meta", e.target.value)} maxLength={200} placeholder="Ex.: 300 alunos até setembro" /></label>
      </div>
      <datalist id="kpis-sugeridos">{KPIS_SUGERIDOS.map((k) => <option key={k} value={k} />)}</datalist>
      <fieldset className="ent-estrategia"><legend>Conexão estratégica <span className="mudo">marque o que esta entrega ajuda a cumprir</span></legend>
        {!catalogo.length && <p className="mudo">O administrador ainda não cadastrou os resultados-chave do PO e os indicadores do Contrato de Gestão (Administração, Tabelas de referência). Enquanto isso, informe o KPI da entrega.</p>}
        {grupos.map(([tipo, titulo]) => {
          const itens = catalogo.filter((i) => i.tipo === tipo);
          return itens.length > 0 && (
            <div key={tipo} className="ent-grupo"><strong>{titulo}</strong>
              {itens.map((i) => (
                <label key={i.id} className="ent-check"><input type="checkbox" checked={f.estrategia.includes(i.id)} onChange={() => alterna(i.id)} />
                  <span><b>{i.codigo}</b> {i.descricao}{i.meta && <span className="mudo"> | meta: {i.meta}</span>}</span></label>))}
            </div>);
        })}
      </fieldset>
      {erro && <p className="erro" role="alert">{erro}</p>}
      <div className="acoes"><button className="primario">Salvar entrega</button><button type="button" onClick={onCancelar}>Cancelar</button></div>
    </form>
  );
}

export default function EntregasProjeto({ orcamento, contingenciado, onMudou }) {
  const [d, setD] = useState(null);
  const [erro, setErro] = useState("");
  const [lote, setLote] = useState("");
  const [editando, setEditando] = useState(null);      // id da entrega, ou "nova"
  const carregar = useCallback(() => api(`/projetos/${orcamento}/entregas`).then(setD).catch((e) => setErro(e.message)), [orcamento]);
  useEffect(() => { carregar(); }, [carregar]);
  if (erro && !d) return <p className="erro">{erro}</p>;
  if (!d) return <p>Carregando…</p>;
  const cat = Object.fromEntries(d.catalogo.map((i) => [i.id, i]));
  const mudou = () => { carregar(); onMudou && onMudou(); };
  const adicionar = async () => {
    setErro("");
    const linhas = lote.split("\n").map((x) => x.trim()).filter((x) => x.length >= 3);
    if (!linhas.length) return setErro("Escreva ao menos uma entrega (uma por linha).");
    try { await api(`/projetos/${orcamento}/entregas/lote`, { method: "POST", body: { linhas } }); setLote(""); mudou(); } catch (e) { setErro(e.message); }
  };
  const salvar = (id) => async (corpo) => {
    if (id === "nova") await api(`/projetos/${orcamento}/entregas`, { method: "POST", body: corpo });
    else await api(`/entregas/${id}`, { method: "PUT", body: corpo });
    setEditando(null); mudou();
  };
  const excluir = async (e) => {
    if (!window.confirm(`Excluir a entrega "${e.descricao.slice(0, 80)}"?`)) return;
    try { await api(`/entregas/${e.id}`, { method: "DELETE" }); mudou(); } catch (x) { setErro(x.message); }
  };
  const conectadas = d.entregas.filter((e) => e.estrategia.length).length;
  const semNada = d.entregas.filter((e) => !e.estrategia.length && !e.kpi).length;
  const vazio = { descricao: "", mes: 0, kpi: "", meta: "", estrategia: [] };
  return (
    <section className="cartao">
      <h3>Entregas previstas para 2027</h3>
      <p className="mudo">Liste tudo o que este projeto vai entregar em 2027. Cada entrega pode ter mês previsto, um KPI para medir o resultado e a ligação com o Plano de Operação (PO) e com os indicadores do Contrato de Gestão (CG). Assim a leitura do orçamento mostra o que ele compra em resultados.</p>
      {contingenciado && <div className="nota aviso">Orçamento contingenciado: as entregas são opcionais até a liberação.</div>}
      {erro && <p className="erro" role="alert">{erro}</p>}
      {d.entregas.length > 0 && (
        <div className="ent-resumo"><span><strong>{d.entregas.length}</strong> entrega(s)</span><span><strong>{conectadas}</strong> ligada(s) ao PO ou ao CG</span>
          {semNada > 0 && <span className="aviso-txt"><strong>{semNada}</strong> sem KPI nem conexão estratégica</span>}</div>)}
      <ol className="ent-lista">
        {d.entregas.map((e, i) => (
          <li key={e.id} className={"ent-item " + (!e.estrategia.length && !e.kpi ? "sem" : "")}>
            <span className="ent-n">{i + 1}</span>
            {editando === e.id
              ? <div className="ent-corpo"><FormEntrega inicial={{ descricao: e.descricao, mes: e.mes, kpi: e.kpi, meta: e.meta, estrategia: e.estrategia }} catalogo={d.catalogo} onSalvar={salvar(e.id)} onCancelar={() => setEditando(null)} /></div>
              : <div className="ent-corpo">
                <p className="ent-texto">{e.descricao}</p>
                <div className="ent-chips">
                  <Chip tom="mes">{e.mes ? `até ${MESES_N[e.mes - 1]}` : "sem mês"}</Chip>
                  {e.kpi ? <Chip tom="kpi" title="KPI da entrega">KPI: {e.kpi}{e.meta && ` | meta ${e.meta}`}</Chip> : <Chip tom="vazio">sem KPI</Chip>}
                  {e.estrategia.map((id) => cat[id] && <Chip key={id} tom={cat[id].tipo} title={cat[id].descricao}>{cat[id].tipo === "po" ? "PO" : "CG"} {cat[id].codigo}</Chip>)}
                  {!e.estrategia.length && <Chip tom="vazio">sem vínculo com PO ou CG</Chip>}
                </div>
                <div className="acoes"><button className="link" onClick={() => setEditando(e.id)}>Detalhar e conectar</button><button className="link perigo" onClick={() => excluir(e)}>Excluir</button></div>
              </div>}
          </li>))}
        {editando === "nova" && <li className="ent-item"><span className="ent-n">{d.entregas.length + 1}</span>
          <div className="ent-corpo"><FormEntrega inicial={vazio} catalogo={d.catalogo} onSalvar={salvar("nova")} onCancelar={() => setEditando(null)} /></div></li>}
      </ol>
      {!d.entregas.length && editando !== "nova" && <p className="mudo">Nenhuma entrega lançada ainda.</p>}
      <div className="ent-rapido">
        <label><span>Adicionar várias entregas de uma vez <span className="mudo">uma por linha; depois use "Detalhar e conectar" em cada uma</span></span>
          <textarea rows={4} value={lote} onChange={(e) => setLote(e.target.value)} placeholder={"Ex.:\nTurma 1 do curso de segurança concluída\nPlataforma de parcerias em produção\nRelatório anual de resultados publicado"} /></label>
        <div className="acoes"><button className="primario" onClick={adicionar} disabled={!lote.trim()}>Adicionar entregas</button>
          <button onClick={() => setEditando("nova")} disabled={editando === "nova"}>+ Entrega detalhada</button></div>
      </div>
    </section>
  );
}
