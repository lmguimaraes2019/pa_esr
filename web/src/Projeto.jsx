import React, { useCallback, useEffect, useMemo, useState } from "react";
import { api, fmt, fmtN, lerNumero, MESES } from "./api.js";

function Celula({ valor, onSalvar }) {
  const [txt, setTxt] = useState(null);
  const mostra = txt ?? (valor ? fmtN(valor) : "");
  const fim = () => {
    if (txt === null) return;
    const n = lerNumero(txt);
    setTxt(null);
    if (!Number.isNaN(n) && Math.abs(n - valor) > 0.004) onSalvar(Math.max(0, Math.round(n * 100) / 100));
  };
  return <input className="cel" inputMode="decimal" value={mostra} onFocus={(e) => { setTxt(valor ? String(valor).replace(".", ",") : ""); e.target.select(); }}
    onChange={(e) => setTxt(e.target.value)} onBlur={fim} onKeyDown={(e) => { if (e.key === "Enter") e.target.blur(); if (e.key === "Escape") { setTxt(null); e.target.blur(); } }} />;
}

function NovaLinha({ contas, onCriar, onFechar }) {
  const [f, setF] = useState({ edt: "", tarefa: "", conta: "", total: "" });
  const [erro, setErro] = useState("");
  const salvar = async (e) => {
    e.preventDefault();
    const total = lerNumero(f.total);
    if (Number.isNaN(total) || total < 0) return setErro("Informe um valor anual válido.");
    const base = Math.floor((total / 12) * 100) / 100;
    const meses = Array(12).fill(base);
    meses[11] = Math.round((total - base * 11) * 100) / 100;       // o resto dos centavos vai para dezembro
    try { await onCriar({ edt: f.edt, tarefa: f.tarefa, conta_codigo: f.conta, meses }); onFechar(); } catch (x) { setErro(x.message); }
  };
  return (
    <form className="cartao nova" onSubmit={salvar}>
      <h3>Nova linha</h3>
      <div className="grade">
        <label>Meta/EDT<input value={f.edt} onChange={(e) => setF({ ...f, edt: e.target.value })} required /></label>
        <label>Ação/Tarefa<input value={f.tarefa} onChange={(e) => setF({ ...f, tarefa: e.target.value })} required /></label>
        <label>Conta contábil<select value={f.conta} onChange={(e) => setF({ ...f, conta: e.target.value })} required>
          <option value="">Selecione…</option>
          {contas.map((c) => <option key={c.codigo} value={c.codigo}>{c.grupo} | {c.descricao}</option>)}
        </select></label>
        <label>Valor anual (dividido em 12)<input value={f.total} onChange={(e) => setF({ ...f, total: e.target.value })} required inputMode="decimal" /></label>
      </div>
      {erro && <p className="erro">{erro}</p>}
      <div className="acoes"><button className="primario">Adicionar</button><button type="button" onClick={onFechar}>Cancelar</button></div>
    </form>
  );
}

export default function Projeto({ orcamento, admin, voltar }) {
  const [d, setD] = useState(null);
  const [contas, setContas] = useState([]);
  const [erro, setErro] = useState("");
  const [nova, setNova] = useState(false);
  const [aberta, setAberta] = useState(null);

  const carregar = useCallback(() => api(`/projetos/${orcamento}`).then(setD).catch((e) => setErro(e.message)), [orcamento]);
  useEffect(() => { carregar(); api("/contas").then(setContas); }, [carregar]);

  const trocar = (id, nova) => setD((x) => ({ ...x, linhas: x.linhas.map((l) => (l.id === id ? nova : l)) }));
  const salvarMeses = async (l, i, v) => {
    const meses = [...l.meses]; meses[i] = v;
    try { setErro(""); trocar(l.id, await api(`/linhas/${l.id}`, { method: "PUT", body: { meses } })); carregar(); }
    catch (e) { setErro(e.message); }
  };
  const excluir = async (l) => {
    if (!window.confirm(`Excluir a linha "${l.tarefa} | ${l.conta_desc}" (${fmt(l.total)})?`)) return;
    try { await api(`/linhas/${l.id}`, { method: "DELETE" }); carregar(); } catch (e) { setErro(e.message); }
  };
  const grupos = useMemo(() => {
    const m = new Map();
    (d?.linhas || []).forEach((l) => { const k = `${l.edt} | ${l.tarefa}`; if (!m.has(k)) m.set(k, []); m.get(k).push(l); });
    return [...m.entries()];
  }, [d]);

  if (erro && !d) return <p className="erro">{erro} <button className="link" onClick={voltar}>Voltar</button></p>;
  if (!d) return <p>Carregando…</p>;
  const { projeto: p, totais: t } = d;

  return (
    <>
      <button className="link" onClick={voltar}>← Projetos</button>
      <div className="cab">
        <div><h2>{p.descricao}</h2><p className="mudo">Orçamento {p.orcamento} · Projeto {p.n_projeto || "sem número"} · {p.origem} · {p.gerente}</p></div>
        {admin && !p.n_projeto && <NumeroProjeto orcamento={p.orcamento} onSalvo={carregar} />}
      </div>
      <div className="kpis">
        <div className="kpi"><span>2026 aprovado</span><strong>{fmt(t.base)}</strong></div>
        <div className="kpi"><span>2027 plano</span><strong>{fmt(t.plano)}</strong></div>
        <div className="kpi"><span>Variação</span><strong>{fmt(t.plano - t.base)}</strong></div>
        <div className="kpi"><span>Realizado 2026</span><strong>{fmt(t.realizado)}</strong></div>
      </div>
      {erro && <p className="erro" role="alert">{erro}</p>}
      <p className="mudo">Edite os meses direto na tabela e tecle Enter. Cada alteração fica registrada com o seu usuário. A linha cinza abaixo de cada valor é o 2026 aprovado.</p>
      <div className="rolagem">
        <table className="tab grid">
          <thead><tr><th>Conta</th>{MESES.map((m) => <th key={m} className="n">{m}</th>)}<th className="n">Total</th><th /></tr></thead>
          <tbody>
            {grupos.map(([k, ls]) => (
              <React.Fragment key={k}>
                <tr className="grupo"><td colSpan={15}>{k}</td></tr>
                {ls.map((l) => (
                  <React.Fragment key={l.id}>
                    <tr className={l.editada ? "ed" : ""}>
                      <td title={l.atualizado_por ? `Última edição: ${l.atualizado_por}` : ""}><span className="mudo">{l.grupo}</span><br />{l.conta_desc}{l.obs && <span className="tag" title={l.obs}>obs</span>}</td>
                      {l.meses.map((v, i) => <td key={i} className="n"><Celula valor={v} onSalvar={(n) => salvarMeses(l, i, n)} /></td>)}
                      <td className="n"><strong>{fmtN(l.total)}</strong></td>
                      <td><button className="link" title="Excluir linha" onClick={() => excluir(l)}>✕</button></td>
                    </tr>
                    {l.ref && (
                      <tr className="ref"><td>2026 {l.realizado > 0 && <small>· realizado {fmt(l.realizado)}</small>}</td>
                        {l.ref.meses.map((v, i) => <td key={i} className="n">{v ? fmtN(v) : ""}</td>)}<td className="n">{fmtN(l.ref.total)}</td><td /></tr>)}
                  </React.Fragment>))}
              </React.Fragment>))}
          </tbody>
          <tfoot><tr><td>Total</td>{MESES.map((_, i) => <td key={i} className="n">{fmtN(d.linhas.reduce((a, l) => a + l.meses[i], 0))}</td>)}<td className="n">{fmtN(t.plano)}</td><td /></tr></tfoot>
        </table>
      </div>
      {nova ? <NovaLinha contas={contas} onFechar={() => setNova(false)} onCriar={async (b) => { await api(`/projetos/${orcamento}/linhas`, { method: "POST", body: b }); carregar(); }} />
            : <button className="primario" onClick={() => setNova(true)}>+ Nova linha</button>}
      {(t.realizado_sem_linha > 1 || t.empenhado_sem_linha > 1) && (
        <p className="mudo">Execução 2026 sem linha correspondente neste projeto: realizado {fmt(t.realizado_sem_linha)}, empenhado {fmt(t.empenhado_sem_linha)}.</p>)}
    </>
  );
}

function NumeroProjeto({ orcamento, onSalvo }) {
  const [v, setV] = useState("");
  const [erro, setErro] = useState("");
  const salvar = async () => {
    try { await api(`/projetos/${orcamento}`, { method: "PATCH", body: { n_projeto: v } }); onSalvo(); } catch (e) { setErro(e.message); }
  };
  return (
    <div className="cartao pend">
      <strong>Nº do Projeto pendente</strong>
      <div className="acoes"><input value={v} onChange={(e) => setV(e.target.value)} placeholder="ex.: 2999" inputMode="numeric" /><button className="primario" onClick={salvar} disabled={!v}>Salvar</button></div>
      {erro && <p className="erro">{erro}</p>}
    </div>
  );
}
