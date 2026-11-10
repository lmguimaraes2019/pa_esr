import React, { useCallback, useEffect, useState } from "react";
import { api } from "./api.js";

const MESES_N = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];
const KPIS_SUGERIDOS = ["Alunos capacitados", "Vagas ofertadas", "Taxa de conclusão (%)", "Satisfação / NPS", "Cursos lançados", "Turmas realizadas", "Parceiros ativos",
  "Receita gerada (R$)", "Entregas no prazo (%)", "Disponibilidade do serviço (%)", "Pessoas treinadas", "Eventos realizados"];


export const rotuloEst = (e) => (/^\d/.test(e.codigo) ? ({ diretriz: "Diretriz", re: "RE", po: "RO", cg: "CG" }[e.tipo] + " " + e.codigo) : e.codigo);

export function fecho(catalogo, ids) {
  const porId = Object.fromEntries(catalogo.map((e) => [e.id, e]));
  const out = new Set(); const fila = [...ids];
  while (fila.length) { const i = fila.pop(); if (out.has(i) || !porId[i]) continue; out.add(i); fila.push(...porId[i].pais); }
  return out;
}

const NIVEL = { diretriz: 0, re: 1, po: 2, cg: 0 };

function ItemEst({ e, marcado, coberto, onAlterna }) {
  return (
    <label className={"est-item n" + NIVEL[e.tipo] + (marcado ? " marcado" : "")}>
      <input type="checkbox" checked={marcado} onChange={() => onAlterna(e.id)} />
      <span className="est-corpo">
        <span className="est-tit"><b className={"est-cod " + e.tipo}>{rotuloEst(e)}</b> {e.descricao}
          {coberto && !marcado && <span className="chip herdado" title="Já coberto por um item marcado abaixo dele">coberto</span>}</span>
        {e.tipo === "po" && (e.objetivo || e.meta) && (
          <span className="est-det">{e.meta && <span><i>Métrica:</i> {e.meta}</span>}
            <span className="est-meta">{e.conclusao && <span className="chip mes">{e.conclusao}</span>}{e.responsavel && <span className="chip">{e.responsavel}</span>}{e.fomento && <span className="chip">{e.fomento}</span>}</span></span>)}
        {e.tipo === "re" && e.lider && <span className="est-det mudo">{e.lider}</span>}
      </span>
    </label>
  );
}

const sn = (t) => (t || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
const numeros = (e) => (e.codigo.match(/\d+/g) || []).map(Number);
const porNumero = (a, b) => { const x = numeros(a), y = numeros(b); for (let i = 0; i < Math.max(x.length, y.length); i++) if ((x[i] ?? -1) !== (y[i] ?? -1)) return (x[i] ?? -1) - (y[i] ?? -1); return 0; };

/** Seletor em árvore: diretriz > RE > RO, com busca, filtro "só ESR", seleção sempre visível e indicadores do CG ao final. */
export function SeletorEstrategia({ catalogo, ids, onChange }) {
  const [q, setQ] = useState("");
  const temEsr = catalogo.some((e) => e.tipo === "po" && /\bESR\b/.test(e.responsavel));
  const [soEsr, setSoEsr] = useState(temEsr);
  const [verCg, setVerCg] = useState(false);
  const [abertos, setAbertos] = useState(() => new Set(catalogo.filter((e) => ids.includes(e.id)).flatMap((e) => [e.id, ...e.pais])));
  const porId = Object.fromEntries(catalogo.map((e) => [e.id, e]));
  const cobertos = fecho(catalogo, ids);
  const alterna = (id) => onChange(ids.includes(id) ? ids.filter((i) => i !== id) : [...ids, id]);
  const txt = sn(q.trim());
  const filhosDe = {};
  catalogo.forEach((e) => e.pais.forEach((pid) => { const pai = porId[pid]; if (pai && pai.tipo !== "cg" && ((pai.tipo === "diretriz" && e.tipo === "re") || (pai.tipo === "re" && e.tipo === "po"))) (filhosDe[pid] ||= []).push(e); }));
  const filhos = (e) => (filhosDe[e.id] || []).slice().sort(porNumero);
  const passaTxt = (e) => !txt || sn(e.codigo + " " + e.descricao + " " + e.meta + " " + e.responsavel + " " + e.lider + " " + e.objetivo).includes(txt);
  const passaEsr = (e) => !soEsr || ids.includes(e.id) || /\bESR\b/.test(e.responsavel);
  // um item aparece se ele (RO) passa nos filtros, ou se algum item abaixo dele aparece
  const aparece = (e) => (e.tipo === "po" ? passaTxt(e) && passaEsr(e) : filhos(e).some(aparece) || (!soEsr && passaTxt(e)) || (txt && passaTxt(e) && !soEsr));
  const dirs = catalogo.filter((e) => e.tipo === "diretriz").sort(porNumero);
  const visiveis = dirs.filter(aparece);
  const cgs = catalogo.filter((e) => e.tipo === "cg" && (!txt || passaTxt(e))).sort(porNumero);
  const nRos = catalogo.filter((e) => e.tipo === "po").length;
  const nVis = catalogo.filter((e) => e.tipo === "po" && aparece(e)).length;
  const aberto = (e) => !!txt || abertos.has(e.id);
  const toggle = (id) => setAbertos((x) => { const n = new Set(x); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const expandirTudo = (abrir) => setAbertos(abrir ? new Set(catalogo.filter((e) => e.tipo === "diretriz" || e.tipo === "re").map((e) => e.id)) : new Set());
  const sel = ids.map((i) => porId[i]).filter(Boolean).sort(porNumero);
  const nSel = (e) => filhos(e).reduce((a, f) => a + (ids.includes(f.id) ? 1 : 0) + nSel(f), 0);
  const Cab = ({ e }) => (
    <div className={"est-grupo n" + NIVEL[e.tipo] + (ids.includes(e.id) ? " marcado" : "")}>
      <button type="button" className="est-seta" onClick={() => toggle(e.id)} aria-expanded={aberto(e)} aria-label={aberto(e) ? "Recolher" : "Expandir"}>{aberto(e) ? "▾" : "▸"}</button>
      <label className="est-gtit"><input type="checkbox" checked={ids.includes(e.id)} onChange={() => alterna(e.id)} />
        <b className={"est-cod " + e.tipo}>{rotuloEst(e)}</b> <span>{e.descricao}</span>
        {cobertos.has(e.id) && !ids.includes(e.id) && <span className="chip herdado" title="Já coberto por um item marcado abaixo dele">coberto</span>}</label>
      <span className="est-cont mudo">{nSel(e) > 0 && <strong className="est-nsel">{nSel(e)} marcado(s)</strong>} {e.tipo === "diretriz" ? `${filhos(e).filter(aparece).length} RE` : `${filhos(e).filter(aparece).length} RO`}</span>
    </div>);
  return (
    <div className="est-sel">
      <div className="est-sel-sel" aria-live="polite">
        {sel.length ? (<><strong>Marcados ({sel.length}):</strong>{sel.map((e) => (
          <button type="button" key={e.id} className={"chip rem " + e.tipo} title={e.descricao + " (clique para remover)"} onClick={() => alterna(e.id)}>{rotuloEst(e)} ×</button>))}</>)
          : <span className="mudo">Nenhum item marcado. Abra uma diretriz, escolha o RO que o orçamento ajuda a entregar e marque a caixa. Marcar o RO já cobre o RE, a diretriz e o indicador do CG.</span>}
      </div>
      <div className="est-barra">
        <input className="est-busca" type="search" placeholder="Buscar por código, texto, métrica ou responsável" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Buscar na estratégia" />
        {temEsr && <label className="est-so"><input type="checkbox" checked={soEsr} onChange={(e) => setSoEsr(e.target.checked)} /> só ROs da ESR</label>}
        <button type="button" className="link" onClick={() => expandirTudo(true)}>Expandir tudo</button>
        <button type="button" className="link" onClick={() => expandirTudo(false)}>Recolher tudo</button>
      </div>
      <p className="mudo est-conta">{soEsr ? <>Mostrando {nVis} de {nRos} ROs do PO 2027 (responsável ESR). O orçamento serve a um RO de outra área? <button type="button" className="link" onClick={() => setSoEsr(false)}>Ver todos os ROs</button></> : <>Mostrando {nVis} de {nRos} ROs do PO 2027.</>}</p>
      <div className="est-lista" role="group" aria-label="Diretrizes, resultados estratégicos e resultados operacionais">
        {visiveis.map((d) => (
          <div key={d.id} className="est-bloco">
            <Cab e={d} />
            {aberto(d) && filhos(d).filter(aparece).map((r) => (
              <div key={r.id}>
                <Cab e={r} />
                {aberto(r) && filhos(r).filter(aparece).map((o) => <ItemEst key={o.id} e={o} marcado={ids.includes(o.id)} coberto={cobertos.has(o.id)} onAlterna={alterna} />)}
              </div>))}
          </div>))}
        {!visiveis.length && <p className="mudo" style={{ margin: 8 }}>Nada encontrado.{soEsr && " Tente ver todos os ROs."}</p>}
        {cgs.length > 0 && <div className="est-sep">Indicadores do Contrato de Gestão <span className="mudo" style={{ fontWeight: 400 }}>(já cobertos pelo RO marcado)</span>
          {!txt && !cgs.some((e) => ids.includes(e.id)) && <button type="button" className="link" style={{ marginLeft: 8 }} onClick={() => setVerCg(!verCg)}>{verCg ? "ocultar" : "marcar um indicador diretamente"}</button>}</div>}
        {(verCg || txt || cgs.some((e) => ids.includes(e.id))) && cgs.map((e) => <ItemEst key={e.id} e={e} marcado={ids.includes(e.id)} coberto={cobertos.has(e.id)} onAlterna={alterna} />)}
      </div>
    </div>
  );
}

function Cadeia({ catalogo, id }) {
  const porId = Object.fromEntries(catalogo.map((e) => [e.id, e]));
  const e = porId[id];
  if (!e) return null;
  const acima = e.pais.map((i) => porId[i]).filter(Boolean).sort((a, b) => ({ re: 0, diretriz: 1, cg: 2 }[a.tipo] - { re: 0, diretriz: 1, cg: 2 }[b.tipo]));
  return (
    <li className="cadeia">
      <span className={"chip " + e.tipo} title={e.descricao}>{rotuloEst(e)}</span>
      <span className="cadeia-txt">{e.descricao}</span>
      {acima.length > 0 && <span className="cadeia-pais">{acima.map((a) => <span key={a.id} className={"chip " + a.tipo} title={a.descricao}>{rotuloEst(a)}</span>)}</span>}
    </li>
  );
}

function VinculoEstrategico({ orcamento, catalogo, vinculos, onSalvo, contingenciado }) {
  const [aberto, setAberto] = useState(false);
  const [ids, setIds] = useState(vinculos);
  const [erro, setErro] = useState("");
  useEffect(() => { setIds(vinculos); }, [vinculos]);
  if (!catalogo.length) return (
    <div className="nota">O administrador ainda não cadastrou o Plano de Operação e os indicadores do Contrato de Gestão (Administração, Tabelas de referência). Quando isso acontecer, aqui você liga o orçamento a eles.</div>);
  const salvar = async () => {
    setErro("");
    try { await api(`/projetos/${orcamento}/estrategia`, { method: "PUT", body: { ids } }); setAberto(false); onSalvo(); } catch (e) { setErro(e.message); }
  };
  return (
    <section className={"cartao vinculo " + (!vinculos.length && !contingenciado ? "pend" : "")}>
      <div className="cab">
        <div><h3>Vínculo estratégico do orçamento</h3>
          <p className="mudo">A que direcionador, resultado estratégico (RE), resultado operacional (RO) do PO e indicador do Contrato de Gestão este orçamento serve? Marcar um RO já cobre o RE, a diretriz e o indicador do CG acima dele.</p></div>
        {!aberto && <button className={vinculos.length ? "" : "primario"} onClick={() => setAberto(true)}>{vinculos.length ? "Alterar vínculo" : "Vincular ao PO e ao CG"}</button>}
      </div>
      {!aberto && (vinculos.length
        ? <ul className="cadeias">{vinculos.map((id) => <Cadeia key={id} catalogo={catalogo} id={id} />)}</ul>
        : <p className="aviso-txt">{contingenciado ? "Sem vínculo (orçamento contingenciado)." : "Este orçamento ainda não está ligado a nenhum item do PO ou do Contrato de Gestão. Isso é uma pendência do projeto."}</p>)}
      {aberto && (
        <>
          <SeletorEstrategia catalogo={catalogo} ids={ids} onChange={setIds} />
          {erro && <p className="erro" role="alert">{erro}</p>}
          <div className="acoes"><button className="primario" onClick={salvar}>Salvar vínculo ({ids.length})</button><button onClick={() => { setIds(vinculos); setAberto(false); }}>Cancelar</button></div>
        </>)}
    </section>
  );
}

function Chip({ tom, children, title }) {
  return <span className={"chip " + tom} title={title}>{children}</span>;
}

function FormEntrega({ inicial, catalogo: todosItens, vinculos, onSalvar, onCancelar }) {
  const [f, setF] = useState(inicial);
  const [todos, setTodos] = useState(false);
  const noVinculo = vinculos.length ? fecho(todosItens, vinculos) : null;
  const base = todosItens.filter((i) => i.tipo === "po" || i.tipo === "cg");
  const catalogo = todos || !noVinculo ? base : base.filter((i) => noVinculo.has(i.id) || f.estrategia.includes(i.id));
  const temMais = !!noVinculo && base.length > catalogo.length || todos;
  const [erro, setErro] = useState("");
  const set = (k, v) => setF((x) => ({ ...x, [k]: v }));
  const alterna = (id) => setF((x) => ({ ...x, estrategia: x.estrategia.includes(id) ? x.estrategia.filter((i) => i !== id) : [...x.estrategia, id] }));
  const salvar = async (e) => {
    e.preventDefault(); setErro("");
    try { await onSalvar({ descricao: f.descricao, mes: Number(f.mes), kpi: f.kpi, meta: f.meta, estrategia: f.estrategia }); } catch (x) { setErro(x.message); }
  };
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
      <fieldset className="ent-estrategia"><legend>Esta entrega contribui para <span className="mudo">marque o RO do PO ou o indicador do CG que ela ajuda a cumprir</span></legend>
        {!catalogo.length && <p className="mudo">O catálogo do PO e do CG ainda não foi cadastrado pelo administrador. Enquanto isso, informe o KPI da entrega.</p>}
        {catalogo.map((i) => (
          <label key={i.id} className="ent-check"><input type="checkbox" checked={f.estrategia.includes(i.id)} onChange={() => alterna(i.id)} />
            <span><b>{rotuloEst(i)}</b> {i.descricao}{i.meta && <span className="mudo"> | {i.meta}</span>}</span></label>))}
        {temMais && <button type="button" className="link" onClick={() => setTodos(!todos)}>{todos ? "Mostrar só os itens do vínculo do orçamento" : "Mostrar todos os ROs e indicadores"}</button>}
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
    <>
    <VinculoEstrategico orcamento={orcamento} catalogo={d.catalogo} vinculos={d.vinculos} onSalvo={mudou} contingenciado={contingenciado} />
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
              ? <div className="ent-corpo"><FormEntrega inicial={{ descricao: e.descricao, mes: e.mes, kpi: e.kpi, meta: e.meta, estrategia: e.estrategia }} catalogo={d.catalogo} vinculos={d.vinculos} onSalvar={salvar(e.id)} onCancelar={() => setEditando(null)} /></div>
              : <div className="ent-corpo">
                <p className="ent-texto">{e.descricao}</p>
                <div className="ent-chips">
                  <Chip tom="mes">{e.mes ? `até ${MESES_N[e.mes - 1]}` : "sem mês"}</Chip>
                  {e.kpi ? <Chip tom="kpi" title="KPI da entrega">KPI: {e.kpi}{e.meta && ` | meta ${e.meta}`}</Chip> : <Chip tom="vazio">sem KPI</Chip>}
                  {e.estrategia.map((id) => cat[id] && <Chip key={id} tom={cat[id].tipo} title={cat[id].descricao}>{rotuloEst(cat[id])}</Chip>)}
                  {!e.estrategia.length && <Chip tom="vazio">sem vínculo com PO ou CG</Chip>}
                </div>
                <div className="acoes"><button className="link" onClick={() => setEditando(e.id)}>Detalhar e conectar</button><button className="link perigo" onClick={() => excluir(e)}>Excluir</button></div>
              </div>}
          </li>))}
        {editando === "nova" && <li className="ent-item"><span className="ent-n">{d.entregas.length + 1}</span>
          <div className="ent-corpo"><FormEntrega inicial={vazio} catalogo={d.catalogo} vinculos={d.vinculos} onSalvar={salvar("nova")} onCancelar={() => setEditando(null)} /></div></li>}
      </ol>
      {!d.entregas.length && editando !== "nova" && <p className="mudo">Nenhuma entrega lançada ainda.</p>}
      <div className="ent-rapido">
        <label><span>Adicionar várias entregas de uma vez <span className="mudo">uma por linha; depois use "Detalhar e conectar" em cada uma</span></span>
          <textarea rows={4} value={lote} onChange={(e) => setLote(e.target.value)} placeholder={"Ex.:\nTurma 1 do curso de segurança concluída\nPlataforma de parcerias em produção\nRelatório anual de resultados publicado"} /></label>
        <div className="acoes"><button className="primario" onClick={adicionar} disabled={!lote.trim()}>Adicionar entregas</button>
          <button onClick={() => setEditando("nova")} disabled={editando === "nova"}>+ Entrega detalhada</button></div>
      </div>
    </section>
    </>
  );
}
