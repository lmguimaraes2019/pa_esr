import React, { useEffect, useState } from "react";
import { api, fmt, lerNumero } from "./api.js";
import { TrocarSenha } from "./Login.jsx";
import { CARGOS } from "./Planejamento.jsx";
import { custoMensal } from "./pessoal.js";

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
      <ParametrosPessoal reajuste={lerNumero(v.reajuste_pessoal) || 0} />
      <section className="cartao"><h3>Minha senha</h3><TrocarSenha /></section>
    </>
  );
}

const GRUPOS_PESSOAL = [
  { titulo: "Encargos sobre o salário", nota: "Além de INSS patronal de 20% e terceiros de 4,5%, que são fixos.", campos: [
    ["rat", "RAT ajustado", "%"], ["fgts", "FGTS", "%"], ["pis", "PIS", "%"]] },
  { titulo: "Benefícios", nota: "Valores mensais por pessoa.", campos: [
    ["vr_dia", "VR/VA por dia", "R$"], ["vr_dias", "Dias de VR/VA no mês", "dias"], ["vr_extra", "Complemento fixo do VR/VA", "R$"],
    ["vt", "Vale-transporte", "R$"], ["plano_saude", "Plano de saúde e odontológico (média)", "R$"],
    ["seguro_vida", "Seguro de vida", "% sal."], ["internet", "Ajuda de custo de internet", "R$"]] },
];

function ParametrosPessoal({ reajuste }) {
  const [d, setD] = useState(null);
  const [v, setV] = useState({});
  const [exemplo, setExemplo] = useState("5.891,66");
  const [msg, setMsg] = useState("");
  const [erro, setErro] = useState("");
  const carregar = () => api("/headcount/parametros").then((r) => { setD(r); setV(Object.fromEntries(r.parametros.map((p) => [p.chave, String(p.valor).replace(".", ",")]))); });
  useEffect(() => { carregar(); }, []);
  if (!d) return null;
  const num = (k) => lerNumero(v[k]);
  const par = Object.fromEntries(d.parametros.map((p) => [p.chave, num(p.chave)]));
  const invalido = d.parametros.some((p) => Number.isNaN(par[p.chave]) || par[p.chave] < 0);
  const sal = lerNumero(exemplo);
  const c = !invalido && sal > 0 ? custoMensal(sal * (1 + reajuste / 100), par) : null;
  const alterado = d.parametros.some((p) => Math.abs((par[p.chave] ?? 0) - p.valor) > 1e-9);
  const salvar = async () => {
    setErro(""); setMsg("");
    try { await api("/headcount/parametros/valores", { method: "PUT", body: { valores: par } }); setMsg("Parâmetros salvos. As linhas de headcount nos orçamentos foram recalculadas."); carregar(); } catch (e) { setErro(e.message); }
  };
  const padrao = () => setV(Object.fromEntries(d.parametros.map((p) => [p.chave, String(p.padrao).replace(".", ",")])));
  return (
    <section className="cartao param-pessoal">
      <h3>Custo de pessoal (Headcount)</h3>
      <p className="mudo">Parâmetros das fórmulas da planilha CUSTO_PESSOAL, aba Agosto_26. O custo mensal soma salário, encargos, benefícios e provisões de férias (com abono de 10 dias, mais 1/3) e 13º. O reajuste de pessoal acima já é aplicado sobre o salário da Tabela Salarial 2025.</p>
      <div className="param-grupos">
        {GRUPOS_PESSOAL.map((g) => (
          <fieldset key={g.titulo}>
            <legend>{g.titulo}</legend>
            <p className="mudo">{g.nota}</p>
            <div className="param-campos">
              {g.campos.map(([k, rot, suf]) => (
                <label key={k}>{rot}<span className="com-sufixo"><input value={v[k] ?? ""} inputMode="decimal" onChange={(e) => setV({ ...v, [k]: e.target.value })} /><em>{suf}</em></span></label>))}
            </div>
          </fieldset>))}
        <fieldset className="param-conf">
          <legend>Conferência</legend>
          <p className="mudo">Informe um salário da tabela para ver o custo com os parâmetros acima.</p>
          <label>Salário de exemplo<span className="com-sufixo"><input value={exemplo} inputMode="decimal" onChange={(e) => setExemplo(e.target.value)} /><em>R$</em></span></label>
          {c ? (
            <dl className="param-res">
              <div><dt>Salário e encargos</dt><dd>{fmt(c.encargos)}</dd></div>
              <div><dt>Benefícios</dt><dd>{fmt(c.beneficios)}</dd></div>
              <div><dt>Provisões</dt><dd>{fmt(c.provisoes)}</dd></div>
              <div className="total"><dt>Custo mensal</dt><dd>{fmt(c.mensal)}</dd></div>
              <div className="total"><dt>Anualizado</dt><dd>{fmt(c.anual)}</dd></div>
            </dl>) : <p className="erro">Confira os valores informados.</p>}
          {reajuste > 0 && <p className="mudo">Considera o reajuste de {String(reajuste).replace(".", ",")}% sobre o salário.</p>}
        </fieldset>
      </div>
      {erro && <p className="erro" role="alert">{erro}</p>}{msg && <p className="ok">{msg}</p>}
      <div className="acoes"><button className="primario" onClick={salvar} disabled={!alterado || invalido}>Salvar parâmetros</button>
        <button onClick={padrao}>Restaurar valores da planilha</button></div>
    </section>
  );
}

export function Exportar({ irProjeto }) {
  const [pre, setPre] = useState(null);
  const carregar = () => api("/export/preflight").then(setPre);
  useEffect(() => { carregar(); }, []);
  if (!pre) return <p>Conferindo…</p>;
  return (
    <>
      <h2>Exportar para o PMO da DSS (Template Planejamento Anual 2027)</h2>
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

function Acessos({ d, valor, onChange }) {
  const alt = (lista, item) => (lista.includes(item) ? lista.filter((x) => x !== item) : [...lista, item]);
  return (
    <>
      <fieldset className="cartao" style={{ margin: "8px 0" }}><legend>Gerentes de projetos que acompanha (vê todos os projetos de cada um)</legend>
        <div className="filtros" style={{ margin: 0 }}>{d.gerentes.map((g) => (
          <button type="button" key={g} className={valor.gerentes.includes(g) ? "on" : ""} onClick={() => onChange({ ...valor, gerentes: alt(valor.gerentes, g) })}>{g}</button>))}</div></fieldset>
      <fieldset className="cartao" style={{ margin: "8px 0" }}><legend>Projetos avulsos (além dos gerentes acima)</legend>
        <div style={{ maxHeight: 180, overflow: "auto" }}>{d.projetos.map((p) => (
          <label key={p.orcamento} style={{ display: "flex", gap: 8, alignItems: "center", textTransform: "none", letterSpacing: 0, fontWeight: 400 }}>
            <input type="checkbox" style={{ width: "auto" }} checked={valor.projetos.includes(p.orcamento)} onChange={() => onChange({ ...valor, projetos: alt(valor.projetos, p.orcamento) })} />
            {p.orcamento} | {p.descricao} <span className="mudo">({p.gerente})</span></label>))}</div></fieldset>
    </>
  );
}

export function Usuarios() {
  const vazio = { login: "", nome: "", perfil: "gestor", gerencia: "", cargo: "", gerentes: [], projetos: [] };
  const [d, setD] = useState(null);
  const [novo, setNovo] = useState(vazio);
  const [ed, setEd] = useState(null);
  const [temp, setTemp] = useState(null);
  const [erro, setErro] = useState("");
  const [msg, setMsg] = useState("");
  const carregar = () => api("/usuarios").then(setD);
  useEffect(() => { carregar(); }, []);
  if (!d) return <p>Carregando…</p>;
  const criar = async (e) => {
    e.preventDefault(); setErro(""); setMsg("");
    try { const r = await api("/usuarios", { method: "POST", body: novo }); setTemp({ login: r.login, senha: r.senha_temporaria }); setNovo(vazio); carregar(); }
    catch (x) { setErro(x.message); }
  };
  const salvar = async (e) => {
    e.preventDefault(); setErro(""); setMsg("");
    try { await api(`/usuarios/${ed.id}`, { method: "PATCH", body: { nome: ed.nome, perfil: ed.perfil, gerencia: ed.gerencia, cargo: ed.cargo, gerentes: ed.gerentes, projetos: ed.projetos } }); setMsg(`Usuário ${ed.login} atualizado.`); setEd(null); carregar(); }
    catch (x) { setErro(x.message); }
  };
  const reset = async (u) => { if (window.confirm(`Gerar nova senha provisória para ${u.nome}?`)) setTemp({ login: u.login, senha: (await api(`/usuarios/${u.id}/reset-senha`, { method: "POST" })).senha_temporaria }); };
  const alternar = async (u) => { try { await api(`/usuarios/${u.id}`, { method: "PATCH", body: { ativo: !u.ativo } }); carregar(); } catch (x) { setErro(x.message); } };
  return (
    <>
      <h2>Usuários</h2>
      <datalist id="lista-gerencias">{[...new Set(["DSS - Diretoria de Serviços e Soluções", "Diretoria Adjunta", ...d.usuarios.map((x) => x.gerencia).filter(Boolean)])].map((g) => <option key={g} value={g} />)}</datalist>
      <p className="mudo">Todos os usuários, inclusive administradores, precisam ter gerência e cargo. Eles organizam a tela de acompanhamento: DSS, Diretoria Adjunta, gerências, gerentes e coordenadores.</p>
      {temp && <div className="cartao pend"><strong>Senha provisória de {temp.login}</strong><p><code>{temp.senha}</code></p><p className="mudo">Anote agora: ela não será exibida de novo. Será exigida a troca no primeiro acesso.</p><button onClick={() => setTemp(null)}>Já anotei</button></div>}
      {msg && <p className="ok">{msg}</p>}{erro && <p className="erro" role="alert">{erro}</p>}
      <div className="rolagem"><table className="tab"><thead><tr><th>Usuário</th><th>Nome</th><th>Perfil</th><th>Gerência</th><th>Acompanha</th><th>Situação</th><th /></tr></thead>
        <tbody>{d.usuarios.map((u) => (<tr key={u.id}><td>{u.login}</td><td>{u.nome}</td><td>{u.perfil === "admin" ? "administrador (todos)" : "gestor"}</td><td>{u.gerencia || <span className="mudo">sem gerência</span>}{u.cargo ? <span className="mudo"> | {CARGOS[u.cargo]}</span> : <span className="mudo"> | sem cargo</span>}</td>
          <td>{u.perfil === "admin" ? <span className="mudo">todos os projetos</span> : <>{u.gerentes.join(", ") || <span className="mudo">nenhum gerente</span>}{u.projetos.length > 0 && <><br /><span className="mudo">+ projetos {u.projetos.join(", ")}</span></>}</>}</td>
          <td>{u.ativo ? (u.trocar_senha ? "aguardando 1º acesso" : "ativo") : "desativado"}</td>
          <td style={{ whiteSpace: "nowrap" }}><button className="link" onClick={() => { setErro(""); setMsg(""); setEd({ id: u.id, login: u.login, nome: u.nome, perfil: u.perfil, gerencia: u.gerencia, cargo: u.cargo, gerentes: u.gerentes, projetos: u.projetos }); }}>Editar</button> <button className="link" onClick={() => reset(u)}>Nova senha</button> <button className="link" onClick={() => alternar(u)}>{u.ativo ? "Desativar" : "Reativar"}</button></td></tr>))}</tbody></table></div>
      {ed && (
        <form className="cartao" onSubmit={salvar}><h3>Editar {ed.login}</h3>
          <div className="grade">
            <label>Nome<input value={ed.nome} onChange={(e) => setEd({ ...ed, nome: e.target.value })} required /></label>
            <label>Perfil<select value={ed.perfil} onChange={(e) => setEd({ ...ed, perfil: e.target.value })}><option value="gestor">Gestor</option><option value="admin">Administrador</option></select></label>
          <label>Gerência / diretoria<input list="lista-gerencias" value={ed.gerencia} onChange={(e) => setEd({ ...ed, gerencia: e.target.value })} placeholder="Ex.: Gerência de Tecnologia" required /></label>
          <label>Cargo<select value={ed.cargo} onChange={(e) => setEd({ ...ed, cargo: e.target.value })} required><option value="">Selecione</option>{Object.entries(CARGOS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
          </div>
          {ed.perfil === "gestor" ? <Acessos d={d} valor={ed} onChange={setEd} /> : <p className="mudo">O administrador vê e edita todos os projetos.</p>}
          <div className="acoes"><button className="primario">Salvar</button><button type="button" onClick={() => setEd(null)}>Cancelar</button></div></form>)}
      <form className="cartao" onSubmit={criar}><h3>Novo usuário</h3>
        <div className="grade">
          <label>Login<input value={novo.login} onChange={(e) => setNovo({ ...novo, login: e.target.value.toLowerCase() })} required pattern="[a-z0-9._-]{3,30}" /></label>
          <label>Nome<input value={novo.nome} onChange={(e) => setNovo({ ...novo, nome: e.target.value })} required /></label>
          <label>Perfil<select value={novo.perfil} onChange={(e) => setNovo({ ...novo, perfil: e.target.value })}><option value="gestor">Gestor</option><option value="admin">Administrador</option></select></label>
          <label>Gerência / diretoria<input list="lista-gerencias" value={novo.gerencia} onChange={(e) => setNovo({ ...novo, gerencia: e.target.value })} placeholder="Ex.: Gerência de Tecnologia" required /></label>
          <label>Cargo<select value={novo.cargo} onChange={(e) => setNovo({ ...novo, cargo: e.target.value })} required><option value="">Selecione</option>{Object.entries(CARGOS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
        </div>
        {novo.perfil === "gestor" && <Acessos d={d} valor={novo} onChange={setNovo} />}
        <button className="primario">Criar</button></form>
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

export function Realizado() {
  const [arq, setArq] = useState(null);
  const [r, setR] = useState(null);
  const [erro, setErro] = useState("");
  const [msg, setMsg] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const enviar = async (simular) => {
    setErro(""); setMsg(""); if (!arq) return setErro("Escolha a planilha primeiro.");
    if (!simular && !window.confirm("Substituir o realizado e o empenhado de 2026 pelos valores desta planilha?")) return;
    setOcupado(true);
    try {
      const f = new FormData(); f.append("arquivo", arq);
      const resp = await fetch(`/api/execucao/importar?simular=${simular}`, { method: "POST", body: f, credentials: "same-origin" });
      const j = await resp.json().catch(() => ({}));
      if (!resp.ok) throw new Error(typeof j.detail === "string" ? j.detail : "Não foi possível ler a planilha.");
      setR(j); if (!simular) { setMsg("Realizado e empenhado de 2026 atualizados."); }
    } catch (e) { setErro(e.message); } finally { setOcupado(false); }
  };
  return (
    <>
      <h2>Realizado e empenhado de 2026</h2>
      <div className="nota">Em 2026 o app só recebe o <strong>realizado</strong> e o <strong>empenhado</strong>, importados da base do Protheus (planilha com a aba BASE ESR). O aprovado de 2026 e o plano de 2027 não são alterados. Cada importação substitui os valores anteriores.</div>
      {msg && <p className="ok">{msg}</p>}{erro && <p className="erro" role="alert">{erro}</p>}
      <section className="cartao">
        <label>Planilha do Protheus (.xlsx)<input type="file" accept=".xlsx" onChange={(e) => { setArq(e.target.files[0] || null); setR(null); }} /></label>
        <div className="acoes"><button onClick={() => enviar(true)} disabled={!arq || ocupado}>Conferir antes de importar</button>
          <button className="primario" onClick={() => enviar(false)} disabled={!arq || ocupado || !r || !r.simulacao}>Importar</button></div>
        {!r?.simulacao && arq && !msg && <p className="mudo">Clique em "Conferir antes de importar" para ver o que vai mudar.</p>}
      </section>
      {r && (
        <section className="cartao"><h3>{r.simulacao ? "O que vai mudar" : "Importado"}</h3>
          <p>Realizado: <strong>{fmt(r.realizado_antes)}</strong> para <strong>{fmt(r.realizado_depois)}</strong> | Empenhado: <strong>{fmt(r.empenhado_antes)}</strong> para <strong>{fmt(r.empenhado_depois)}</strong> | {r.linhas} linhas</p>
          {r.orcamentos_ignorados.length > 0 && <div className="nota aviso">Orçamentos da planilha que não existem no app e foram ignorados: {r.orcamentos_ignorados.join(", ")}.</div>}
          <div className="rolagem"><table className="tab"><thead><tr><th>Orçamento</th><th className="n">Realizado antes</th><th className="n">Realizado depois</th><th className="n">Empenhado antes</th><th className="n">Empenhado depois</th></tr></thead>
            <tbody>{r.projetos.map((p) => <tr key={p.orcamento}><td>{p.orcamento}</td><td className="n">{fmt(p.realizado_antes)}</td><td className="n"><strong>{fmt(p.realizado_depois)}</strong></td><td className="n">{fmt(p.empenhado_antes)}</td><td className="n"><strong>{fmt(p.empenhado_depois)}</strong></td></tr>)}</tbody></table></div>
        </section>)}
    </>
  );
}
