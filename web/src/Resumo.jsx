import React, { useEffect, useState } from "react";
import { api, fmt, mi } from "./api.js";

function Barras({ itens, chave = "nome" }) {
  const max = Math.max(1, ...itens.map((i) => Math.max(i.plano, i.base)));
  return (
    <table className="tab">
      <thead><tr><th>{chave === "nome" ? "" : ""}</th><th className="n">2026 aprovado</th><th className="n">2027 plano</th><th className="n">Variação</th><th style={{ width: "32%" }}></th></tr></thead>
      <tbody>{itens.map((i) => (
        <tr key={i.nome}>
          <td>{i.nome}</td><td className="n">{fmt(i.base)}</td><td className="n">{fmt(i.plano)}</td>
          <td className="n">{i.base ? ((i.plano / i.base - 1) * 100).toFixed(1).replace(".", ",") + "%" : "novo"}</td>
          <td><div className="barra"><span className="b26" style={{ width: (i.base / max) * 100 + "%" }} /><span className="b27" style={{ width: (i.plano / max) * 100 + "%" }} /></div></td>
        </tr>))}</tbody>
    </table>
  );
}

export default function Resumo() {
  const [r, setR] = useState(null);
  const [erro, setErro] = useState("");
  useEffect(() => { api("/resumo").then(setR).catch((e) => setErro(e.message)); }, []);
  if (erro) return <p className="erro">{erro}</p>;
  if (!r) return <p>Carregando…</p>;
  const max = Math.max(1, ...r.mensal_plano.map((m) => m.valor));
  return (
    <>
      <h2>Resumo do planejamento</h2>
      <div className="kpis">
        <div className="kpi"><span>Aprovado {r.ciclo_base}</span><strong>{mi(r.total_base)}</strong></div>
        <div className="kpi"><span>Plano {r.ciclo_plano}</span><strong>{mi(r.total_plano)}</strong></div>
        <div className="kpi"><span>Variação</span><strong>{r.total_base ? ((r.total_plano / r.total_base - 1) * 100).toFixed(1).replace(".", ",") + "%" : "-"}</strong></div>
        <div className="kpi"><span>Diferença</span><strong>{fmt(r.total_plano - r.total_base)}</strong></div>
      </div>
      <section className="cartao"><h3>Por origem de recurso</h3><Barras itens={r.por_origem} /></section>
      <section className="cartao"><h3>Por grupo de despesa</h3><Barras itens={r.por_grupo} /></section>
      <section className="cartao"><h3>Calendarização mensal {r.ciclo_plano}</h3>
        <div className="meses">{r.mensal_plano.map((m) => (
          <div key={m.mes} title={fmt(m.valor)}><div className="col"><span style={{ height: (m.valor / max) * 100 + "%" }} /></div><small>{m.mes.slice(0, 3)}</small></div>))}</div>
      </section>
    </>
  );
}
