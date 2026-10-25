import React, { useCallback, useEffect, useState } from "react";
import { api } from "./api.js";
import { Login, TrocarSenha } from "./Login.jsx";
import Resumo from "./Resumo.jsx";
import Projetos from "./Projetos.jsx";
import Projeto from "./Projeto.jsx";
import { Premissas, Usuarios, Exportar, Auditoria } from "./Admin.jsx";

export default function App() {
  const [user, setUser] = useState(undefined);
  const [aba, setAba] = useState("resumo");
  const [proj, setProj] = useState(null);

  const carregar = useCallback(() => api("/me").then(setUser).catch(() => setUser(null)), []);
  useEffect(() => { carregar(); }, [carregar]);

  if (user === undefined) return <div className="centro">Carregando…</div>;
  if (!user) return <Login onEntrou={setUser} />;
  if (user.trocar_senha) return <TrocarSenha obrigatoria onFeito={carregar} />;

  const admin = user.perfil === "admin";
  const abas = [["resumo", "Resumo"], ["projetos", "Projetos"],
    ...(admin ? [["premissas", "Premissas"], ["exportar", "Exportar"], ["usuarios", "Usuários"], ["auditoria", "Histórico"]] : [])];
  const ir = (a) => { setAba(a); setProj(null); };

  return (
    <div className="app">
      <header className="topo">
        <div className="marca"><strong>Orçamento ESR</strong> <span>2027</span></div>
        <nav>{abas.map(([k, t]) => <button key={k} className={aba === k ? "on" : ""} onClick={() => ir(k)}>{t}</button>)}</nav>
        <div className="quem">
          {user.nome}
          <button className="link" onClick={() => api("/logout", { method: "POST" }).then(() => setUser(null))}>Sair</button>
        </div>
      </header>
      <main>
        {aba === "resumo" && <Resumo />}
        {aba === "projetos" && (proj
          ? <Projeto orcamento={proj} admin={admin} voltar={() => setProj(null)} />
          : <Projetos abrir={setProj} />)}
        {admin && aba === "premissas" && <Premissas />}
        {admin && aba === "exportar" && <Exportar irProjeto={(o) => { setAba("projetos"); setProj(o); }} />}
        {admin && aba === "usuarios" && <Usuarios />}
        {admin && aba === "auditoria" && <Auditoria />}
      </main>
    </div>
  );
}
