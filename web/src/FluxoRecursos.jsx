import React, { useEffect, useState } from "react";
import { api, fmt, mi } from "./api.js";
import { Delta, pct } from "./ui.jsx";

// Origem dos recursos: 2026 (aprovado e executado) e 2027 (plano, receita lançada e saldo) em cada origem
export function OrigemDosRecursos({ d, ps }) {
  const fomento = (o) => /fomento|fndct/i.test(o);
  const por = {};
  ps.forEach((p) => { const o = p.origem || "Sem origem"; const x = (por[o] ||= { origem: o, n: 0, a26: 0, e26: 0, p27: 0, rec: 0 }); x.n += 1; x.a26 += p.total_2026; x.e26 += p.realizado_2026; x.p27 += p.total_2027; });
  d.origens.forEach((o) => { (por[o.origem] ||= { origem: o.origem, n: 0, a26: 0, e26: 0, p27: 0, rec: 0 }).rec = o.receita; });
  const linhas = Object.values(por).sort((a, b) => b.p27 - a.p27);
  const tot = linhas.reduce((t, x) => ({ n: t.n + x.n, a26: t.a26 + x.a26, e26: t.e26 + x.e26, p27: t.p27 + x.p27, rec: t.rec + x.rec }), { n: 0, a26: 0, e26: 0, p27: 0, rec: 0 });
  const saldo = (x, total) => { const v = x.rec - x.p27; return !total && fomento(x.origem) && x.rec === 0 ? <span className="mudo">conta única</span> : <strong className={v < 0 ? "res-neg" : v > 0 ? "res-pos" : ""}>{fmt(v)}</strong>; };
  const linha = (x, total) => (
    <tr key={x.origem}><td><strong>{x.origem}</strong>{!total && <span className="mudo"> ({x.n})</span>}</td><td className="n">{fmt(x.a26)}</td><td className="n">{fmt(x.e26)}</td><td className="n">{pct(x.e26, x.a26)}</td>
      <td className="n"><strong>{fmt(x.p27)}</strong></td><td className="n"><Delta de={x.a26} para={x.p27} /></td><td className="n">{fmt(x.rec)}</td><td className="n">{saldo(x, total)}</td></tr>);
  return (
    <section className="cartao">
      <h3>Origem dos recursos: 2026 e plano 2027</h3>
      <p className="mudo" style={{ marginTop: 0 }}>Por origem do recurso (entre parênteses, o número de projetos). Em fomento a conta é única na RNP: o recurso vem do contrato, não de receita lançada. Saldo = receita 2027 menos plano 2027.</p>
      <div className="rolagem" style={{ margin: 0 }}><table className="tab tab-grande">
        <thead><tr><th>Origem</th><th className="n">Aprovado 2026</th><th className="n">Executado 2026</th><th className="n">% exec.</th><th className="n">Plano 2027</th><th className="n">Variação</th><th className="n">Receita 2027</th><th className="n">Saldo 2027</th></tr></thead>
        <tbody>{linhas.map((x) => linha(x, false))}</tbody>
        <tfoot>{linha({ ...tot, origem: "Total" }, true)}</tfoot>
      </table></div>
    </section>);
}


export default function useFluxo(gerencia = "", conting = true) {
  const [d, setD] = useState(null);
  useEffect(() => { api("/fluxo?contingenciados=" + conting + (gerencia ? `&gerencia=${encodeURIComponent(gerencia)}` : "")).then(setD).catch(() => setD(false)); }, [gerencia, conting]);
  return d;
}
