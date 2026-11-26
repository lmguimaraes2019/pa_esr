import React, { useCallback, useEffect, useState } from "react";
import { api } from "./api.js";
import { Login, TrocarSenha } from "./Login.jsx";
import Resumo from "./Resumo.jsx";
import Projetos from "./Projetos.jsx";
import Projeto from "./Projeto.jsx";
import Viagens from "./Viagens.jsx";
import Receitas from "./Receitas.jsx";
import Eventos from "./Eventos.jsx";
import Headcount from "./Headcount.jsx";
import Execucao from "./Execucao.jsx";
import Exposicao from "./Exposicao.jsx";
import Relatorios from "./Relatorios.jsx";
import { Premissas, Usuarios, Auditoria, Realizado, Referencias } from "./Admin.jsx";

export default function App() {
  const [user, setUser] = useState(undefined);
  const [aba, setAba] = useState("resumo");
  const [proj, setProj] = useState(null);
  const [plano, setPlano] = useState(null);
  const [planoErro, setPlanoErro] = useState("");
  const [soEntregas, setSoEntregas] = useState(false);      // lista de projetos filtrada pelas pendências: 'entregas' ou 'financiamento'

  const carregar = useCallback(() => api("/me").then(setUser).catch(() => setUser(null)), []);
  useEffect(() => { carregar(); }, [carregar]);
  const carregarPlano = useCallback(() => api("/planejamento").then((d) => { setPlanoErro(""); setPlano(d); }).catch((e) => setPlanoErro((e && e.message) || "erro desconhecido")), []);
  useEffect(() => { if (user && !user.trocar_senha) carregarPlano(); }, [user, aba, proj, carregarPlano]);

  if (user === undefined) return <div className="centro" style={{ color: "#fff" }}>Carregando…</div>;
  if (!user) return <Login onEntrou={setUser} />;
  if (user.trocar_senha) return <TrocarSenha obrigatoria onFeito={carregar} />;

  const admin = user.perfil === "admin";
  const ADMIN = [["premissas", "Premissas"], ["realizado", "Realizado 2026"], ["referencias", "Tabelas de referência"], ["usuarios", "Usuários"], ["auditoria", "Histórico"]];
  const ETAPAS = [["projetos", "Despesas"], ["receitas", "Receitas"], ["viagens", "Viagens"], ["eventos", "Eventos"], ["headcount", "Headcount"], ["exposicao", "Exposição ao dólar"], ["execucao", "Execução 2026"]];
  const emPlano = ETAPAS.some(([k]) => k === aba);
  const emAdmin = ADMIN.some(([k]) => k === aba);
  const abas = [["resumo", "Meu planejamento", aba === "resumo"], ["projetos", "Plano 2027", emPlano], ["relatorios", "Relatórios", aba === "relatorios"], ...(admin ? [["admin", "Administração", emAdmin]] : [])];
  const pend = (k) => (plano ? ({ viagens: plano.etapas.viagens.pendentes, eventos: plano.etapas.eventos.pendentes, headcount: plano.etapas.headcount.pendentes }[k] || 0) : 0);
  const ir = (a, p = null, filtro = false) => { setAba(a); setProj(p); setSoEntregas(filtro); window.scrollTo(0, 0); };

  return (
    <div className="app">
      <header className="topo">
        <img className="logo" src="/logo-negativo.png" alt="Escola Superior de Redes" />
        <nav>{abas.map(([k, t, on]) => <button key={k} className={on ? "on" : ""} onClick={() => ir(k === "admin" ? "premissas" : k)}>{t}</button>)}</nav>
        <div className="quem">
          {user.nome}
          <button className="link" onClick={() => api("/logout", { method: "POST" }).then(() => setUser(null))}>Sair</button>
        </div>
      </header>
      {emPlano && <nav className="subnav etapas" aria-label="Etapas do plano 2027">{ETAPAS.map(([k, t], i) => (
        <button key={k} className={aba === k ? "on" : ""} onClick={() => ir(k)}><span className="n">{i + 1}</span>{t}{pend(k) > 0 && <span className="pend-badge" title={`${pend(k)} pendência(s)`}>{pend(k)}</span>}</button>))}</nav>}
      {admin && emAdmin && <nav className="subnav" aria-label="Administração">{ADMIN.map(([k, t]) => <button key={k} className={aba === k ? "on" : ""} onClick={() => ir(k)}>{t}</button>)}</nav>}
      <main>
        {aba === "resumo" && <Resumo plano={plano} planoErro={planoErro} recarregarPlano={carregarPlano} admin={admin} ir={ir} />}
        {aba === "projetos" && (proj
          ? <Projeto orcamento={proj} admin={admin} pmo={admin || user.cargo === "pmo"} voltar={() => setProj(null)} irViagens={() => ir("viagens")} irEtapa={(k) => ir(k)} irProjeto={(o) => ir("projetos", o)} />
          : <Projetos abrir={setProj} semEntregas={soEntregas === "entregas" && plano ? plano.projetos.filter((p) => p.entregas.pendentes > 0).map((p) => p.orcamento) : null} semFonte={soEntregas === "financiamento" && plano ? plano.projetos.filter((p) => p.financiamento.pendentes > 0).map((p) => p.orcamento) : null} limparFiltro={() => setSoEntregas(false)} />)}
        {aba === "relatorios" && <Relatorios pmo={admin || user.cargo === "pmo"} irProjeto={(o) => ir("projetos", o)} />}
        {aba === "receitas" && <Receitas admin={admin} irProjeto={(o) => ir("projetos", o)} />}
        {aba === "eventos" && <Eventos irProjeto={(o) => ir("projetos", o)} />}
        {aba === "exposicao" && <Exposicao irProjeto={(o) => ir("projetos", o)} />}
        {aba === "execucao" && <Execucao irProjeto={(o) => ir("projetos", o)} />}
        {aba === "headcount" && <Headcount admin={admin} irProjeto={(o) => ir("projetos", o)} />}
        {aba === "viagens" && <Viagens admin={admin} irProjeto={(o) => ir("projetos", o)} />}
        {admin && aba === "premissas" && <Premissas />}
        {admin && aba === "realizado" && <Realizado />}
        {admin && aba === "referencias" && <Referencias />}
        {admin && aba === "usuarios" && <Usuarios />}
        {admin && aba === "auditoria" && <Auditoria />}
      </main>
    </div>
  );
}
