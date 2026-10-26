import React, { useState } from "react";
import { api } from "./api.js";

export function Login({ onEntrou }) {
  const [login, setLogin] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const enviar = async (e) => {
    e.preventDefault(); setErro(""); setOcupado(true);
    try { onEntrou(await api("/login", { method: "POST", body: { login, senha } })); }
    catch (x) { setErro(x.message); } finally { setOcupado(false); }
  };
  return (
    <div className="centro">
      <form className="cartao login" onSubmit={enviar}>
        <img className="logo" src="/logo-positivo.png" alt="Escola Superior de Redes" />
        <h1 style={{ textAlign: "center", fontSize: "1.1rem" }}>PLANEJAMENTO ANUAL 2027</h1>
        <label>Usuário<input value={login} onChange={(e) => setLogin(e.target.value)} autoFocus autoComplete="username" /></label>
        <label>Senha<input type="password" value={senha} onChange={(e) => setSenha(e.target.value)} autoComplete="current-password" /></label>
        {erro && <p className="erro" role="alert">{erro}</p>}
        <button className="primario" disabled={ocupado || !login || !senha}>Entrar</button>
      </form>
    </div>
  );
}

export function TrocarSenha({ obrigatoria, onFeito }) {
  const [atual, setAtual] = useState("");
  const [nova, setNova] = useState("");
  const [conf, setConf] = useState("");
  const [msg, setMsg] = useState({ erro: "", ok: false });
  const enviar = async (e) => {
    e.preventDefault();
    if (nova !== conf) return setMsg({ erro: "A confirmação não confere com a nova senha.", ok: false });
    try { await api("/me/senha", { method: "POST", body: { atual, nova } }); setMsg({ erro: "", ok: true }); onFeito?.(); }
    catch (x) { setMsg({ erro: x.message, ok: false }); }
  };
  const corpo = (
    <form className={"cartao login"} onSubmit={enviar} style={obrigatoria ? undefined : { borderTop: 0, width: "min(400px,100%)", margin: 0, padding: 0, border: 0 }}>
      {obrigatoria && <img className="logo" src="/logo-positivo.png" alt="Escola Superior de Redes" />}
      <h1 style={{ fontSize: "1.1rem" }}>{obrigatoria ? "DEFINA SUA SENHA" : "TROCAR SENHA"}</h1>
      {obrigatoria && <p className="mudo">Troque a senha provisória para continuar. Mínimo de 10 caracteres, com maiúscula, minúscula e número.</p>}
      <label>Senha atual<input type="password" value={atual} onChange={(e) => setAtual(e.target.value)} autoComplete="current-password" /></label>
      <label>Nova senha<input type="password" value={nova} onChange={(e) => setNova(e.target.value)} autoComplete="new-password" /></label>
      <label>Repita a nova senha<input type="password" value={conf} onChange={(e) => setConf(e.target.value)} autoComplete="new-password" /></label>
      {msg.erro && <p className="erro" role="alert">{msg.erro}</p>}
      {msg.ok && <p className="ok">Senha alterada.</p>}
      <button className="primario" disabled={!atual || !nova || !conf}>Salvar senha</button>
    </form>
  );
  return obrigatoria ? <div className="centro">{corpo}</div> : corpo;
}
