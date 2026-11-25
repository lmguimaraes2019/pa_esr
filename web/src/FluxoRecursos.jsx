import React, { useEffect, useState } from "react";
import { api, fmt, mi } from "./api.js";

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


export default function useFluxo(gerencia = "") {
  const [d, setD] = useState(null);
  useEffect(() => { api("/fluxo" + (gerencia ? `?gerencia=${encodeURIComponent(gerencia)}` : "")).then(setD).catch(() => setD(false)); }, [gerencia]);
  return d;
}
