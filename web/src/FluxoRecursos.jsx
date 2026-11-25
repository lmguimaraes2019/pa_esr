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
      <h3>Origem dos recursos em 2027</h3>
      <p className="mudo" style={{ marginTop: 0 }}>Receita lançada e custo planejado por origem. Em fomento a conta é única na RNP: o recurso vem do contrato, não de receita lançada.</p>
      <table className="tab tab-grande">
        <thead><tr><th>Origem</th><th className="n">Receita lançada</th><th className="n">Custo planejado</th><th className="n">Saldo</th></tr></thead>
        <tbody>{d.origens.map((o) => (
          <tr key={o.origem}><td><strong>{o.origem}</strong></td><td className="n">{fmt(o.receita)}</td><td className="n">{fmt(o.custo)}</td><td className="n">{saldo(o)}</td></tr>))}</tbody>
        <tfoot><tr><td>Total</td><td className="n">{fmt(d.total_receita)}</td><td className="n">{fmt(d.total_custo)}</td><td className="n"><strong className={dif < 0 ? "res-neg" : dif > 0 ? "res-pos" : ""}>{fmt(dif)}</strong></td></tr></tfoot>
      </table>
      <p className="mudo" style={{ margin: "10px 0 0", fontSize: ".85rem" }}>Saldo = receita menos custo. A diferença é coberta por fomento e por origens ainda sem receita lançada. Só os seus projetos, sem contingenciados.</p>
    </section>);
}

// Custo por gerência: plano 2027 contra o aprovado 2026
export function CustoPorGerencia({ d }) {
  const tot = d.gerencias.reduce((a, g) => a + g.custo, 0), totB = d.gerencias.reduce((a, g) => a + g.base, 0);
  const pct = (de, para) => (de ? ((para - de) / de * 100).toFixed(0).replace(".", ",") + "%" : "novo");
  return (
    <section className="cartao">
      <h3>Custo por gerência</h3>
      <p className="mudo" style={{ marginTop: 0 }}>Plano 2027 contra o aprovado de 2026.</p>
      <table className="tab tab-grande">
        <thead><tr><th>Gerência</th><th className="n">Aprovado 2026</th><th className="n">Plano 2027</th><th className="n">Variação</th><th className="n">Var. %</th><th style={{ width: 130 }}>Peso no total</th></tr></thead>
        <tbody>{d.gerencias.map((g) => {
          const p = tot ? g.custo / tot * 100 : 0;
          return (
            <tr key={g.gerencia}><td><strong>{g.gerencia}</strong></td><td className="n">{fmt(g.base)}</td><td className="n">{fmt(g.custo)}</td>
              <td className="n"><Delta de={g.base} para={g.custo} /></td><td className="n">{pct(g.base, g.custo)}</td>
              <td><span className="peso"><span className="peso-barra"><i style={{ width: Math.max(p, p > 0 ? 2 : 0) + "%" }} /></span>{p.toFixed(0)}%</span></td></tr>);
        })}</tbody>
        <tfoot><tr><td>Total</td><td className="n">{fmt(totB)}</td><td className="n">{fmt(tot)}</td><td className="n"><Delta de={totB} para={tot} /></td><td className="n">{pct(totB, tot)}</td><td>100%</td></tr></tfoot>
      </table>
    </section>);
}

export default function useFluxo(gerencia = "") {
  const [d, setD] = useState(null);
  useEffect(() => { api("/fluxo" + (gerencia ? `?gerencia=${encodeURIComponent(gerencia)}` : "")).then(setD).catch(() => setD(false)); }, [gerencia]);
  return d;
}
