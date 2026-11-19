import React, { useEffect, useState } from "react";
import { api, fmt, mi } from "./api.js";
import { Delta } from "./ui.jsx";

const AZUL = "#1f4e8c", LARANJA = "#e87722";

function Barra({ valor, max, cor }) {
  return <div style={{ background: "rgba(128,128,128,.14)", borderRadius: 4, height: 12, flex: 1 }}><div style={{ width: Math.max(valor / max * 100, valor > 0 ? 1.5 : 0) + "%", height: "100%", background: cor, borderRadius: 4 }} /></div>;
}

// Origem dos recursos: quanto de receita foi lançado e quanto de custo está planejado em cada origem
export function OrigemDosRecursos({ d }) {
  const max = Math.max(1, ...d.origens.map((o) => Math.max(o.receita, o.custo)));
  const fomento = (o) => /fomento|fndct/i.test(o);
  return (
    <section className="cartao">
      <h3>Origem dos recursos: receita e custo em 2027</h3>
      <p className="mudo" style={{ marginTop: 0 }}>Para cada origem, a receita lançada e o custo planejado. Em fomento a conta é única na RNP, então o recurso vem do contrato e não de receita lançada.</p>
      <div style={{ display: "grid", gridTemplateColumns: "minmax(110px, 170px) 1fr minmax(120px, 150px) minmax(120px, 150px)", gap: "10px 14px", alignItems: "center" }}>
        <span className="mudo">Origem</span>
        <span className="mudo" style={{ display: "flex", gap: 14, whiteSpace: "nowrap", flexWrap: "wrap" }}><span><i style={{ background: LARANJA, display: "inline-block", width: 10, height: 10, borderRadius: 2 }} /> Receita lançada</span><span><i style={{ background: AZUL, display: "inline-block", width: 10, height: 10, borderRadius: 2 }} /> Custo planejado</span></span>
        <span className="mudo n" style={{ textAlign: "right" }}>Custo</span><span className="mudo n" style={{ textAlign: "right" }}>Saldo</span>
        {d.origens.map((o) => (
          <React.Fragment key={o.origem}>
            <strong>{o.origem}</strong>
            <div style={{ display: "grid", gap: 4 }}><Barra valor={o.receita} max={max} cor={LARANJA} /><Barra valor={o.custo} max={max} cor={AZUL} /></div>
            <span style={{ textAlign: "right" }}>{fmt(o.custo)}<br /><small className="mudo">receita {fmt(o.receita)}</small></span>
            <span style={{ textAlign: "right" }}>{fomento(o.origem) && o.receita === 0 ? <span className="mudo">conta única</span>
              : <strong className={o.saldo < 0 ? "res-neg" : o.saldo > 0 ? "res-pos" : ""}>{fmt(o.saldo)}</strong>}</span>
          </React.Fragment>))}
      </div>
      <p style={{ margin: "14px 0 0" }}><strong>Total:</strong> receita lançada {fmt(d.total_receita)} para um custo de {fmt(d.total_custo)}. A diferença é coberta por fomento e por origens ainda sem receita lançada. Considera só os seus projetos, sem contingenciados.</p>
    </section>);
}

// Custo por gerência: plano 2027 contra o aprovado 2026
export function CustoPorGerencia({ d }) {
  const max = Math.max(1, ...d.gerencias.map((g) => Math.max(g.custo, g.base)));
  const tot = d.gerencias.reduce((a, g) => a + g.custo, 0), totB = d.gerencias.reduce((a, g) => a + g.base, 0);
  return (
    <section className="cartao">
      <h3>Custo por gerência</h3>
      <p className="mudo" style={{ marginTop: 0 }}>Plano 2027 (azul) contra o aprovado de 2026 (cinza).</p>
      {d.gerencias.map((g) => (
        <div key={g.gerencia} style={{ marginBottom: 12 }}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}><strong>{g.gerencia}</strong><span>{fmt(g.custo)} <span className="mudo">({tot ? (g.custo / tot * 100).toFixed(0) : 0}%)</span> <Delta de={g.base} para={g.custo} /></span></div>
          <div style={{ display: "grid", gap: 3, marginTop: 4 }}><Barra valor={g.custo} max={max} cor={AZUL} /><Barra valor={g.base} max={max} cor="#9aa5b4" /></div>
        </div>))}
      <p className="mudo" style={{ margin: 0 }}>Total: {fmt(tot)} em 2027 contra {fmt(totB)} aprovados em 2026.</p>
    </section>);
}

export default function useFluxo() {
  const [d, setD] = useState(null);
  useEffect(() => { api("/fluxo").then(setD).catch(() => setD(false)); }, []);
  return d;
}
