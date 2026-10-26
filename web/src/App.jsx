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
import { Premissas, Usuarios, Exportar, Auditoria, Realizado } from "./Admin.jsx";

export default function App() {
  const [user, setUser] = useState(undefined);
  const [aba, setAba] = useState("resumo");
  const [proj, setProj] = useState(null);
  const [plano, setPlano] = useState(null);

  const carregar = useCallback(() => api("/me").then(setUser).catch(() => setUser(null)), []);
  useEffect(() => { carregar(); }, [carregar]);
  const carregarPlano = useCallback(() => api("/planejamento").then(setPlano).catch(() => {}), []);
  useEffect(() => { if (user && !user.trocar_senha) carregarPlano(); }, [user, aba, proj, carregarPlano]);

  if (user === undefined) return <div className="centro" style={{ color: "#fff" }}>Carregando…</div>;
  if (!user) return <Login onEntrou={setUser} />;
  if (user.trocar_senha) return <TrocarSenha obrigatoria onFeito={carregar} />;

  const admin = user.perfil === "admin";
  const ADMIN = [["premissas", "Premissas"], ["realizado", "Realizado 2026"], ["exportar", "Exportar para o PMO"], ["usuarios", "Usuários"], ["auditoria", "Histórico"]];
  const ETAPAS = [["projetos", "Despesas"], ["receitas", "Receitas"], ["viagens", "Viagens"], ["eventos", "Eventos"], ["headcount", "Headcount"]];
  const emPlano = ETAPAS.some(([k]) => k === aba);
  const emAdmin = ADMIN.some(([k]) => k === aba);
  const abas = [["resumo", "Meu planejamento", aba === "resumo"], ["projetos", "Plano 2027", emPlano], ...(admin ? [["admin", "Administração", emAdmin]] : [])];
  const pend = (k) => (plano ? ({ viagens: plano.etapas.viagens.pendentes, eventos: plano.etapas.eventos.pendentes, headcount: plano.etapas.headcount.pendentes }[k] || 0) : 0);
  const ir = (a, p = null) => { setAba(a); setProj(p); window.scrollTo(0, 0); };

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
        {aba === "resumo" && <Resumo plano={plano} recarregarPlano={carregarPlano} admin={admin} ir={ir} />}
        {aba === "projetos" && (proj
          ? <Projeto orcamento={proj} admin={admin} voltar={() => setProj(null)} irViagens={() => ir("viagens")} irEtapa={(k) => ir(k)} />
          : <Projetos abrir={setProj} />)}
        {aba === "receitas" && <Receitas admin={admin} irProjeto={(o) => ir("projetos", o)} />}
        {aba === "eventos" && <Eventos irProjeto={(o) => ir("projetos", o)} />}
        {aba === "headcount" && <Headcount admin={admin} irProjeto={(o) => ir("projetos", o)} />}
        {aba === "viagens" && <Viagens admin={admin} irProjeto={(o) => ir("projetos", o)} />}
        {admin && aba === "premissas" && <Premissas />}
        {admin && aba === "realizado" && <Realizado />}
        {admin && aba === "exportar" && <Exportar irProjeto={(o) => ir("projetos", o)} />}
        {admin && aba === "usuarios" && <Usuarios />}
        {admin && aba === "auditoria" && <Auditoria />}
      </main>
    </div>
  );
}
