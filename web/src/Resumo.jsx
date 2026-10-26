import React, { useEffect, useState } from "react";
import { api, fmt, mi } from "./api.js";
import { Kpi, Delta, pct, Selo } from "./ui.jsx";

function Quadro({ itens, rotulo }) {
  const max = Math.max(1, ...itens.map((i) => Math.max(i.plano, i.base)));
  return (
    <table className="tab">
      <thead>
        <tr className="grupos"><th rowSpan={2} style={{ background: "#fff" }} />
          <th colSpan={3} className="g26"><Selo ano={2026} /></th><th colSpan={2} className="g27"><Selo ano={2027} /></th><th rowSpan={2} style={{ background: "#fff", width: "18%" }} /></tr>
        <tr><th>{rotulo}</th><th className="n g26">Aprovado</th><th className="n g26">Executado</th><th className="n g26">% exec.</th><th className="n g27">Plano 2027</th><th className="n g27">Δ vs aprovado</th><th /></tr>
      </thead>
      <tbody>{itens.map((i) => (
        <tr key={i.nome}>
          <td>{i.nome}</td><td className="n">{fmt(i.base)}</td><td className="n">{fmt(i.executado)}</td><td className="n">{pct(i.executado, i.base)}</td>
          <td className="n"><strong>{fmt(i.plano)}</strong></td><td className="n"><Delta de={i.base} para={i.plano} /></td>
          <td><div className="barra"><span className="b26" style={{ width: (i.base / max) * 100 + "%" }} /><span className="b27" style={{ width: (i.plano / max) * 100 + "%" }} /></div></td>
        </tr>))}</tbody>
      <tfoot><tr><td>Total</td><td className="n">{fmt(itens.reduce((a, i) => a + i.base, 0))}</td><td className="n">{fmt(itens.reduce((a, i) => a + i.executado, 0))}</td><td />
        <td className="n">{fmt(itens.reduce((a, i) => a + i.plano, 0))}</td><td className="n"><Delta de={itens.reduce((a, i) => a + i.base, 0)} para={itens.reduce((a, i) => a + i.plano, 0)} /></td><td /></tr></tfoot>
    </table>
  );
}

export default function Resumo({ irProjetos, irViagens }) {
  const [r, setR] = useState(null);
  const [erro, setErro] = useState("");
  useEffect(() => { api("/resumo").then(setR).catch((e) => setErro(e.message)); }, []);
  if (erro) return <p className="erro">{erro}</p>;
  if (!r) return <p>Carregando…</p>;
  const max = Math.max(1, ...r.mensal_plano.map((m) => m.valor));
  const s = r.linhas_status;
  const delta = r.total_plano - r.total_base;
  return (
    <>
      <h2>Planejamento anual</h2>
      <div className="duas">
        <section className="lado passado">
          <h3><Selo ano={2026} /> O que foi aprovado e executado</h3>
          <p className="mudo">Base de comparação. Não é alterada.</p>
          <div className="kpis">
            <Kpi rotulo="Orçamento aprovado" valor={mi(r.total_base)} />
            <Kpi rotulo="Realizado" valor={mi(r.total_realizado)} />
            <Kpi rotulo="Empenhado" valor={mi(r.total_empenhado)} />
            <Kpi rotulo="Executado / aprovado" valor={pct(r.total_executado, r.total_base)} sub="realizado + empenhado" />
          </div>
        </section>
        <section className="lado futuro">
          <h3><Selo ano={2027} /> O que você está planejando</h3>
          <p className="mudo">Nasce como cópia do aprovado e recebe os ajustes.</p>
          <div className="kpis">
            <Kpi rotulo="Plano 2027" valor={mi(r.total_plano)} />
            <Kpi rotulo="Diferença para 2026" valor={fmt(delta)} sub={r.total_base ? ((delta / r.total_base) * 100).toFixed(1).replace(".", ",") + "% sobre o aprovado" : ""} />
            <Kpi rotulo="Linhas ajustadas" valor={s.ajustada + s.nova} sub={`${s.mantida} mantidas de 2026`} />
            <Kpi rotulo="Vindas do plano de viagens" valor={s.viagens} />
          </div>
        </section>
      </div>
      <div className="acoes"><button className="primario" onClick={irProjetos}>Ajustar o orçamento por projeto</button><button className="destaque" onClick={irViagens}>Planejar viagens</button></div>
      <section className="cartao"><h3>Por origem de recurso</h3><Quadro itens={r.por_origem} rotulo="Origem" /></section>
      <section className="cartao"><h3>Por grupo de despesa</h3><Quadro itens={r.por_grupo} rotulo="Grupo" /></section>
      <section className="cartao"><h3>Calendarização mensal do plano 2027</h3>
        <div className="meses">{r.mensal_plano.map((m) => (
          <div key={m.mes} title={fmt(m.valor)}><div className="col"><span style={{ height: (m.valor / max) * 100 + "%" }} /></div><small>{m.mes.slice(0, 3)}</small></div>))}</div>
      </section>
    </>
  );
}
