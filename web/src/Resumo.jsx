import React, { useEffect, useState } from "react";
import { api, fmt, mi } from "./api.js";
import { Kpi, Delta, pct, Selo } from "./ui.jsx";
import { MeuPlanejamento } from "./Planejamento.jsx";

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

function Cobertura() {
  const [c, setC] = useState(null);
  useEffect(() => { api("/estrategia/cobertura").then(setC).catch(() => setC(false)); }, []);
  if (!c) return null;
  const grupos = [["po", "Plano de Operação"], ["cg", "Contrato de Gestão"]];
  return (
    <section className="cartao"><h3>Conexão estratégica</h3>
      <p className="mudo">Quais resultados do PO e indicadores do Contrato de Gestão têm entregas planejadas e quanto do plano 2027 está ligado a eles.</p>
      {c.catalogo_vazio ? <p className="mudo">Cadastre os itens em Administração, Tabelas de referência, "Plano de Operação e indicadores do Contrato de Gestão".</p> : (
        <div className="rolagem"><table className="tab"><thead><tr><th>Item</th><th className="n">Entregas</th><th className="n">Projetos</th><th className="n">Plano 2027 dos projetos</th></tr></thead>
          <tbody>{grupos.map(([t, nome]) => (<React.Fragment key={t}><tr><td colSpan={4}><strong>{nome}</strong></td></tr>
            {c.itens.filter((i) => i.tipo === t).map((i) => (
              <tr key={i.id} className={i.entregas ? "" : "sem-cobertura"}><td><b>{i.codigo}</b> {i.descricao}</td><td className="n">{i.entregas || "sem entregas"}</td><td className="n">{i.projetos}</td><td className="n">{fmt(i.plano_projetos)}</td></tr>))}</React.Fragment>))}</tbody></table></div>)}
      {c.sem_vinculo && c.sem_vinculo.length > 0 && <p className="aviso-txt"><strong>{c.sem_vinculo.length}</strong> projeto(s) com plano 2027 e nenhuma entrega ligada ao PO ou ao CG: {c.sem_vinculo.slice(0, 12).map((p) => p.orcamento || p).join(", ")}{c.sem_vinculo.length > 12 ? "…" : ""}</p>}
    </section>
  );
}

export default function Resumo({ plano, recarregarPlano, admin, ir }) {
  const [r, setR] = useState(null);
  const [erro, setErro] = useState("");
  useEffect(() => { api("/resumo").then(setR).catch((e) => setErro(e.message)); }, []);
  if (erro) return <p className="erro">{erro}</p>;
  if (!r) return <p>Carregando…</p>;
  const max = Math.max(1, ...r.mensal_plano.map((m) => m.valor));
  const s = r.linhas_status;
  const delta = r.total_plano - r.total_base;
  const receitas = plano ? plano.etapas.receitas.total : 0;
  const resultado = receitas - r.total_plano;
  return (
    <>
      <h2>{admin ? "Planejamento 2027" : "Meu planejamento 2027"}</h2>
      <MeuPlanejamento plano={plano} recarregar={recarregarPlano} admin={admin} ir={ir} />
      <h3 className="secao">Visão financeira</h3>
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
            <Kpi rotulo="Receitas 2027" valor={mi(receitas)} sub={plano ? `${plano.etapas.receitas.n} lançamento(s)` : ""} />
            <Kpi rotulo="Resultado 2027" valor={mi(resultado)} sub="receitas menos despesas" tom={resultado < 0 ? "rneg" : "rpos"} />
            <Kpi rotulo="Linhas ajustadas" valor={s.ajustada + s.nova} sub={`${s.mantida} mantidas de 2026`} />
            <Kpi rotulo="Vindas de viagens, eventos e headcount" valor={s.viagens} />
          </div>
        </section>
      </div>
      <Cobertura />
      <section className="cartao"><h3>Por origem de recurso</h3><Quadro itens={r.por_origem} rotulo="Origem" /></section>
      <section className="cartao"><h3>Por grupo de despesa</h3><Quadro itens={r.por_grupo} rotulo="Grupo" /></section>
      <section className="cartao"><h3>Calendarização mensal do plano 2027</h3>
        <div className="meses">{r.mensal_plano.map((m) => (
          <div key={m.mes} title={fmt(m.valor)}><div className="col"><span style={{ height: (m.valor / max) * 100 + "%" }} /></div><small>{m.mes.slice(0, 3)}</small></div>))}</div>
      </section>
    </>
  );
}
