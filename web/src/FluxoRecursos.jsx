import React, { useEffect, useState } from "react";
import { api, fmt, mi } from "./api.js";
import { Delta } from "./ui.jsx";

const AZUL = "#1f4e8c", LARANJA = "#e87722";

function Barra({ valor, max, cor }) {
  return <div style={{ background: "rgba(128,128,128,.14)", borderRadius: 4, height: 12, flex: 1 }}><div style={{ width: Math.max(valor / max * 100, valor > 0 ? 1.5 : 0) + "%", height: "100%", background: cor, borderRadius: 4 }} /></div>;
}

// Origem dos recursos: quanto de receita foi lançado e quanto de custo está planejado em cada origem
export function OrigemDosRecursos({ d }) {
  const fomento = (o) => /fomento|fndct/i.test(o);
  const saldo = (o) => (fomento(o.origem) && o.receita === 0 ? <span className="mudo">conta única</span>
    : <strong className={o.saldo < 0 ? "res-neg" : o.saldo > 0 ? "res-pos" : ""}>{fmt(o.saldo)}</strong>);
  const dif = d.total_receita - d.total_custo;
  return (
    <section className="cartao">
      <h3>Origem dos recursos: receita e custo em 2027</h3>
      <p className="mudo" style={{ marginTop: 0 }}>Para cada origem, a receita lançada e o custo planejado. Em fomento a conta é única na RNP, então o recurso vem do contrato e não de receita lançada.</p>
      <table className="tabela">
        <thead><tr><th>Origem</th><th className="n">Receita lançada</th><th className="n">Custo planejado</th><th className="n">Saldo (receita menos custo)</th></tr></thead>
        <tbody>{d.origens.map((o) => (
          <tr key={o.origem}><td><strong>{o.origem}</strong></td><td className="n">{fmt(o.receita)}</td><td className="n">{fmt(o.custo)}</td><td className="n">{saldo(o)}</td></tr>))}</tbody>
        <tfoot><tr><td>Total</td><td className="n">{fmt(d.total_receita)}</td><td className="n">{fmt(d.total_custo)}</td><td className="n"><strong className={dif < 0 ? "res-neg" : dif > 0 ? "res-pos" : ""}>{fmt(dif)}</strong></td></tr></tfoot>
      </table>
      <p className="mudo" style={{ margin: "10px 0 0" }}>A diferença é coberta por fomento e por origens ainda sem receita lançada. Considera só os seus projetos, sem contingenciados.</p>
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

export default function useFluxo(gerencia = "") {
  const [d, setD] = useState(null);
  useEffect(() => { api("/fluxo" + (gerencia ? `?gerencia=${encodeURIComponent(gerencia)}` : "")).then(setD).catch(() => setD(false)); }, [gerencia]);
  return d;
}
