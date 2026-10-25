import React, { useEffect, useState } from "react";
import { api, fmt, lerNumero } from "./api.js";
import { TrocarSenha } from "./Login.jsx";

export function Premissas() {
  const [p, setP] = useState(null);
  const [v, setV] = useState({});
  const [sim, setSim] = useState(null);
  const [msg, setMsg] = useState("");
  const [erro, setErro] = useState("");
  useEffect(() => { api("/premissas").then((r) => { setP(r); setV(Object.fromEntries(Object.entries(r).map(([k, x]) => [k, String(x.valor).replace(".", ",")]))); }); }, []);
  if (!p) return <p>Carregando…</p>;
  const corpo = () => ({ reajuste_pessoal: lerNumero(v.reajuste_pessoal), reajuste_geral: lerNumero(v.reajuste_geral), dolar: lerNumero(v.dolar) });
  const guardar = async () => { setErro(""); setMsg(""); try { await api("/premissas", { method: "PUT", body: corpo() }); setMsg("Premissas salvas."); return true; } catch (e) { setErro(e.message); return false; } };
  const simular = async () => { if (await guardar()) setSim(await api("/premissas/aplicar", { method: "POST", body: { simular: true } })); };
  const aplicar = async () => {
    if (!window.confirm("Recalcular o 2027 a partir do 2026 aprovado? Linhas editadas à mão são preservadas.")) return;
    const r = await api("/premissas/aplicar", { method: "POST", body: { simular: false } });
    setSim(null); setMsg(`Aplicado em ${r.linhas_afetadas} linhas. Novo total: ${fmt(r.total_depois)}.`);
  };
  const campo = (k, rot, suf) => <label>{rot}<span className="com-sufixo"><input value={v[k] ?? ""} inputMode="decimal" onChange={(e) => setV({ ...v, [k]: e.target.value })} /><em>{suf}</em></span></label>;
  return (
    <>
      <h2>Premissas</h2>
      <section className="cartao">
        <div className="grade">
          {campo("reajuste_pessoal", "Reajuste de Pessoal", "%")}
          {campo("reajuste_geral", "Reajuste das demais despesas", "%")}
          {campo("dolar", "Dólar (parcerias e viagens)", "R$")}
        </div>
        {erro && <p className="erro">{erro}</p>}{msg && <p className="ok">{msg}</p>}
        <div className="acoes"><button onClick={guardar}>Salvar</button><button className="primario" onClick={simular}>Salvar e simular impacto</button></div>
        {sim && <div className="sim"><p>Afeta <strong>{sim.linhas_afetadas}</strong> linhas ({sim.linhas_editadas_preservadas} editadas à mão preservadas). Total vai de <strong>{fmt(sim.total_antes)}</strong> para <strong>{fmt(sim.total_depois)}</strong>.</p>
          <button className="primario" onClick={aplicar}>Aplicar ao 2027</button></div>}
      </section>
      <section className="cartao"><h3>Minha senha</h3><TrocarSenha /></section>
    </>
  );
}

export function Exportar({ irProjeto }) {
  const [pre, setPre] = useState(null);
  const carregar = () => api("/export/preflight").then(setPre);
  useEffect(() => { carregar(); }, []);
  if (!pre) return <p>Conferindo…</p>;
  return (
    <>
      <h2>Exportar para o Template 2027</h2>
      <div className="kpis"><div className="kpi"><span>Linhas</span><strong>{pre.linhas}</strong></div><div className="kpi"><span>Total</span><strong>{fmt(pre.total)}</strong></div></div>
      <section className="cartao">
        <h3>Conferência</h3>
        {pre.avisos.length === 0 && <p className="ok">Nenhuma pendência.</p>}
        <ul className="avisos">{pre.avisos.map((a, i) => (
          <li key={i} className={a.nivel}>{a.nivel === "erro" ? "Bloqueia: " : "Aviso: "}{a.orcamento && <button className="link" onClick={() => irProjeto(a.orcamento)}>Orçamento {a.orcamento}</button>} {a.mensagem}</li>))}</ul>
        <div className="acoes">
          <a className={"botao primario" + (pre.bloqueado ? " off" : "")} href={pre.bloqueado ? undefined : "/api/export/xlsx"} aria-disabled={pre.bloqueado}>Baixar planilha</a>
          <button onClick={carregar}>Conferir de novo</button>
        </div>
        <p className="mudo">O arquivo é o template oficial com a aba Calendarização preenchida. Ao abrir no Excel, as fórmulas de conta e total são recalculadas.</p>
      </section>
    </>
  );
}

export function Usuarios() {
  const [d, setD] = useState(null);
  const [novo, setNovo] = useState({ login: "", nome: "", perfil: "gestor", gerente: "" });
  const [temp, setTemp] = useState(null);
  const [erro, setErro] = useState("");
  const carregar = () => api("/usuarios").then(setD);
  useEffect(() => { carregar(); }, []);
  if (!d) return <p>Carregando…</p>;
  const criar = async (e) => {
    e.preventDefault(); setErro("");
    try { const r = await api("/usuarios", { method: "POST", body: { ...novo, gerente: novo.gerente || null } }); setTemp({ login: r.login, senha: r.senha_temporaria }); setNovo({ login: "", nome: "", perfil: "gestor", gerente: "" }); carregar(); }
    catch (x) { setErro(x.message); }
  };
  const reset = async (u) => { if (window.confirm(`Gerar nova senha provisória para ${u.nome}?`)) setTemp({ login: u.login, senha: (await api(`/usuarios/${u.id}/reset-senha`, { method: "POST" })).senha_temporaria }); };
  const alternar = async (u) => { try { await api(`/usuarios/${u.id}`, { method: "PATCH", body: { ativo: !u.ativo } }); carregar(); } catch (x) { setErro(x.message); } };
  return (
    <>
      <h2>Usuários</h2>
      {temp && <div className="cartao pend"><strong>Senha provisória de {temp.login}</strong><p><code>{temp.senha}</code></p><p className="mudo">Anote agora: ela não será exibida de novo. Será exigida a troca no primeiro acesso.</p><button onClick={() => setTemp(null)}>Entendi</button></div>}
      {erro && <p className="erro">{erro}</p>}
      <table className="tab"><thead><tr><th>Usuário</th><th>Nome</th><th>Perfil</th><th>Gerente de projetos</th><th>Situação</th><th /></tr></thead>
        <tbody>{d.usuarios.map((u) => (<tr key={u.id}><td>{u.login}</td><td>{u.nome}</td><td>{u.perfil}</td><td>{u.gerente}</td><td>{u.ativo ? (u.trocar_senha ? "aguardando 1º acesso" : "ativo") : "desativado"}</td>
          <td className="acoes"><button className="link" onClick={() => reset(u)}>Nova senha</button><button className="link" onClick={() => alternar(u)}>{u.ativo ? "Desativar" : "Reativar"}</button></td></tr>))}</tbody></table>
      <form className="cartao" onSubmit={criar}><h3>Novo usuário</h3>
        <div className="grade">
          <label>Login<input value={novo.login} onChange={(e) => setNovo({ ...novo, login: e.target.value.toLowerCase() })} required pattern="[a-z0-9._-]{3,30}" /></label>
          <label>Nome<input value={novo.nome} onChange={(e) => setNovo({ ...novo, nome: e.target.value })} required /></label>
          <label>Perfil<select value={novo.perfil} onChange={(e) => setNovo({ ...novo, perfil: e.target.value })}><option value="gestor">Gestor</option><option value="admin">Administrador</option></select></label>
          <label>Gerente de projetos<input list="gerentes" value={novo.gerente} onChange={(e) => setNovo({ ...novo, gerente: e.target.value })} /></label>
          <datalist id="gerentes">{d.gerentes.map((g) => <option key={g} value={g} />)}</datalist>
        </div><button className="primario">Criar</button></form>
    </>
  );
}

export function Auditoria() {
  const [l, setL] = useState(null);
  useEffect(() => { api("/auditoria?limite=300").then(setL); }, []);
  if (!l) return <p>Carregando…</p>;
  return (<><h2>Histórico de alterações</h2>
    <table className="tab"><thead><tr><th>Quando (UTC)</th><th>Responsável</th><th>Ação</th><th>Orçamento</th><th>Detalhe</th></tr></thead>
      <tbody>{l.map((a) => <tr key={a.id}><td>{a.em}</td><td>{a.usuario}</td><td>{a.acao}</td><td>{a.orcamento}</td><td>{a.detalhe}</td></tr>)}</tbody></table></>);
}
