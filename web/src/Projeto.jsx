import React, { useCallback, useEffect, useMemo, useState } from "react";
import { api, fmt, fmtN, lerNumero, MESES } from "./api.js";
import { Kpi, Delta, pct, Passos, Selo, Celula, BotaoIcone, Lapis, Lixeira, Desfazer } from "./ui.jsx";

function EditarLinha({ l, contas, onSalvar, onFechar }) {
  const trava = l.fonte === "viagens";
  const [f, setF] = useState({ edt: l.edt, tarefa: l.tarefa, conta_codigo: l.conta_codigo, obs: l.obs || "" });
  const [meses, setMeses] = useState(l.meses.map((v) => (v ? String(v).replace(".", ",") : "")));
  const [erro, setErro] = useState("");
  const total = meses.reduce((a, v) => a + (lerNumero(v) || 0), 0);
  const salvar = async (e) => {
    e.preventDefault();
    const nums = meses.map(lerNumero);
    if (nums.some((n) => Number.isNaN(n) || n < 0)) return setErro("Use apenas valores positivos nos meses.");
    try { await onSalvar(trava ? { obs: f.obs } : { ...f, meses: nums.map((n) => Math.round(n * 100) / 100) }); onFechar(); } catch (x) { setErro(x.message); }
  };
  return (
    <form className="cartao" id="form-linha" onSubmit={salvar}>
      <h3>Editar linha: {l.tarefa} | {l.conta_desc}</h3>
      {trava && <div className="nota aviso">Esta linha vem do plano de viagens. Só a observação pode ser alterada aqui; os valores mudam na aba Viagens.</div>}
      <div className="grade">
        <label>Meta/EDT<input value={f.edt} disabled={trava} onChange={(e) => setF({ ...f, edt: e.target.value })} required /></label>
        <label>Ação/Tarefa<input value={f.tarefa} disabled={trava} onChange={(e) => setF({ ...f, tarefa: e.target.value })} required /></label>
        <label>Conta contábil<select value={f.conta_codigo} disabled={trava} onChange={(e) => setF({ ...f, conta_codigo: e.target.value })}>
          {contas.map((c) => <option key={c.codigo} value={c.codigo}>{c.grupo} | {c.descricao}</option>)}</select></label>
        <label>Observação<input value={f.obs} onChange={(e) => setF({ ...f, obs: e.target.value })} /></label>
      </div>
      <div className="grade" style={{ gridTemplateColumns: "repeat(6, minmax(0, 1fr))" }}>
        {MESES.map((m, i) => <label key={m}>{m}<input value={meses[i]} disabled={trava} inputMode="decimal" onChange={(e) => setMeses(meses.map((v, k) => (k === i ? e.target.value : v)))} /></label>)}
      </div>
      <p><strong>Total 2027: {fmt(total)}</strong> {l.ref && <span className="mudo">(aprovado em 2026: {fmt(l.ref.total)})</span>}</p>
      {erro && <p className="erro" role="alert">{erro}</p>}
      <div className="acoes"><button className="primario">Salvar alterações</button><button type="button" onClick={onFechar}>Cancelar</button></div>
    </form>
  );
}

function NovaLinha({ contas, onCriar, onFechar }) {
  const [f, setF] = useState({ edt: "", tarefa: "", conta: "", total: "" });
  const [erro, setErro] = useState("");
  const salvar = async (e) => {
    e.preventDefault();
    const total = lerNumero(f.total);
    if (Number.isNaN(total) || total < 0) return setErro("Informe um valor anual válido.");
    const base = Math.floor((total / 12) * 100) / 100;
    const meses = Array(12).fill(base);
    meses[11] = Math.round((total - base * 11) * 100) / 100;
    try { await onCriar({ edt: f.edt, tarefa: f.tarefa, conta_codigo: f.conta, meses }); onFechar(); } catch (x) { setErro(x.message); }
  };
  return (
    <form className="cartao" id="form-nova" onSubmit={salvar}>
      <h3>Nova linha no plano 2027</h3>
      <div className="grade">
        <label>Meta/EDT<input value={f.edt} onChange={(e) => setF({ ...f, edt: e.target.value })} required /></label>
        <label>Ação/Tarefa<input value={f.tarefa} onChange={(e) => setF({ ...f, tarefa: e.target.value })} required /></label>
        <label>Conta contábil<select value={f.conta} onChange={(e) => setF({ ...f, conta: e.target.value })} required>
          <option value="">Selecione…</option>
          {contas.map((c) => <option key={c.codigo} value={c.codigo}>{c.grupo} | {c.descricao}</option>)}
        </select></label>
        <label>Valor anual (dividido em 12)<input value={f.total} onChange={(e) => setF({ ...f, total: e.target.value })} required inputMode="decimal" /></label>
      </div>
      {erro && <p className="erro">{erro}</p>}
      <div className="acoes"><button className="primario">Adicionar</button><button type="button" onClick={onFechar}>Cancelar</button></div>
    </form>
  );
}

function agrupar(linhas) {
  const m = new Map();
  linhas.forEach((l) => { const k = `${l.edt} | ${l.tarefa}`; if (!m.has(k)) m.set(k, []); m.get(k).push(l); });
  return [...m.entries()];
}

/* ---------------------------------------------------------------- passo 1: o que aconteceu em 2026 */
function Passado({ d, irPlano, recarregar, setErro }) {
  const [meses, setMeses] = useState(false);
  const restaurar = async (l) => { try { setErro(""); await api(`/linhas/${l.id}/restaurar`, { method: "POST" }); recarregar(); } catch (e) { setErro(e.message); } };
  const t = d.totais;
  const grupos = useMemo(() => agrupar(d.passado), [d]);
  const exec = t.realizado + t.empenhado;
  const restaurarGrupo = async (edt, tarefa) => {
    try { setErro(""); await api(`/projetos/${d.projeto.orcamento}/linhas/restaurar?` + new URLSearchParams(tarefa === undefined ? { edt } : { edt, tarefa }), { method: "POST" }); recarregar(); } catch (e) { setErro(e.message); }
  };
  const faltam = (edt, tarefa) => d.passado.filter((x) => x.removida && x.edt === edt && (tarefa === undefined || x.tarefa === tarefa)).length;
  return (
    <>
      <div className="nota">Esta é a fotografia de 2026: o que foi aprovado, o que já foi realizado e empenhado, e o que cada linha virou no plano de 2027. Os valores de 2026 não são editáveis; o realizado e o empenhado vêm da importação da base do Protheus. Uma linha excluída do plano de 2027 aparece como "removida" e pode ser trazida de volta.</div>
      <div className="kpis">
        <Kpi rotulo="Aprovado 2026" valor={fmt(t.base)} tom="f26" />
        <Kpi rotulo="Realizado" valor={fmt(t.realizado)} tom="f26" />
        <Kpi rotulo="Empenhado" valor={fmt(t.empenhado)} tom="f26" />
        <Kpi rotulo="Saldo não executado" valor={fmt(t.base - exec)} tom="f26" sub={`${pct(exec, t.base)} executado`} />
      </div>
      <div className="acoes"><label style={{ flexDirection: "row", alignItems: "center", gap: 8, textTransform: "none" }}><input type="checkbox" style={{ width: "auto" }} checked={meses} onChange={(e) => setMeses(e.target.checked)} />Mostrar o aprovado mês a mês</label></div>
      <div className="rolagem">
        <table className="tab">
          <thead><tr><th>Conta</th><th className="n">Aprovado</th><th className="n">Realizado</th><th className="n">Empenhado</th><th className="n">Saldo</th><th className="n">% exec.</th><th className="n">Em 2027</th><th>Situação</th>
            {meses && MESES.map((m) => <th key={m} className="n">{m}</th>)}</tr></thead>
          <tbody>
            {grupos.map(([k, ls], gi) => (
              <React.Fragment key={k}>
                {(gi === 0 || grupos[gi - 1][1][0].edt !== ls[0].edt) && (
                  <tr className="meta"><td colSpan={8 + (meses ? 12 : 0)}><span className="rotulo-nivel">Meta/EDT</span> {ls[0].edt}
                    {faltam(ls[0].edt) > 0 && <button className="link" onClick={() => restaurarGrupo(ls[0].edt)}>trazer de volta a Meta/EDT ({faltam(ls[0].edt)} linha(s) removida(s))</button>}</td></tr>)}
                <tr className="grupo" style={{ background: "var(--azul-claro)" }}><td colSpan={8 + (meses ? 12 : 0)} style={{ fontWeight: 800, color: "var(--azul)" }}><span className="rotulo-nivel">Ação/Tarefa</span> {ls[0].tarefa}
                  {faltam(ls[0].edt, ls[0].tarefa) > 0 && <button className="link" onClick={() => restaurarGrupo(ls[0].edt, ls[0].tarefa)}>trazer de volta a ação ({faltam(ls[0].edt, ls[0].tarefa)} linha(s) removida(s))</button>}</td></tr>
                {ls.map((l) => (
                  <tr key={l.id}>
                    <td><span className="mudo">{l.grupo}</span><br />{l.conta_desc}</td>
                    <td className="n">{fmtN(l.aprovado)}</td><td className="n">{fmtN(l.realizado)}</td><td className="n">{fmtN(l.empenhado)}</td>
                    <td className="n">{fmtN(l.saldo)}</td><td className="n">{l.pct === null ? "-" : l.pct.toFixed(0) + "%"}</td>
                    <td className="n"><strong>{fmtN(l.plano_2027)}</strong></td>
                    <td>{l.removida ? <><span className="tag removida">removida</span> <button className="link" onClick={() => restaurar(l)}>trazer de volta</button></>
                      : Math.abs(l.plano_2027 - l.aprovado) < 0.005 ? <span className="tag ok">mantida</span>
                      : <span className="tag ajustada">ajustada</span>}</td>
                    {meses && l.meses.map((v, i) => <td key={i} className="n">{v ? fmtN(v) : ""}</td>)}
                  </tr>))}
              </React.Fragment>))}
          </tbody>
        </table>
      </div>
      {(t.realizado_sem_linha > 1 || t.empenhado_sem_linha > 1) && (
        <p className="mudo">Execução de 2026 sem linha correspondente no aprovado: realizado {fmt(t.realizado_sem_linha)}, empenhado {fmt(t.empenhado_sem_linha)}.</p>)}
      <div className="acoes" style={{ marginTop: 16 }}><button className="destaque" onClick={irPlano}>Ir para o plano 2027 →</button></div>
    </>
  );
}

/* ---------------------------------------------------------------- passo 2: o que muda em 2027 */
const FILTROS = [["todas", "Todas"], ["ajustes", "Ajustadas e novas"], ["mantida", "Mantidas de 2026"], ["viagens", "Do plano de viagens"], ["alerta", "Com alerta"]];

function DadosOrcamento({ d, admin, recarregar, setErro }) {
  const p = d.projeto;
  const [listas, setListas] = useState(null);
  const [origem, setOrigem] = useState(p.origem);
  const [nome, setNome] = useState(p.descricao);
  const [msg, setMsg] = useState("");
  useEffect(() => { api("/listas").then(setListas).catch(() => {}); }, []);
  useEffect(() => { setOrigem(p.origem); setNome(p.descricao); }, [p.origem, p.descricao]);
  if (!listas) return null;
  const pode = admin || p.novo;
  const salvar = async (corpo, texto) => {
    try { setErro(""); setMsg(""); await api(`/projetos/${p.orcamento}`, { method: "PATCH", body: corpo }); setMsg(texto); recarregar(); } catch (e) { setErro(e.message); }
  };
  return (
    <section className="cartao dados-orc">
      <h3>Dados do orçamento</h3>
      <div className="grade">
        <label>Origem de recursos em 2027
          <select value={origem} onChange={(e) => setOrigem(e.target.value)}>{listas.origens.map((o) => <option key={o}>{o}</option>)}</select></label>
        {pode && <label>Nome do orçamento<input value={nome} onChange={(e) => setNome(e.target.value)} /></label>}
      </div>
      <div className="acoes">
        <button className="primario" disabled={origem === p.origem} onClick={() => salvar({ origem }, `Origem de 2027 alterada para ${origem}. A de 2026 continua ${p.origem_2026}.`)}>Salvar origem</button>
        {pode && <button disabled={nome.trim() === p.descricao || nome.trim().length < 3} onClick={() => salvar({ descricao: nome }, "Nome atualizado.")}>Salvar nome</button>}
        {msg && <span className="ok">{msg}</span>}
      </div>
      <p className="mudo">A mudança vale só para o plano de 2027: define a origem enviada no Template do PMO e o grupo do resumo e das receitas em 2027. {p.novo ? "" : <>Em 2026 este orçamento continua em <strong>{p.origem_2026}</strong>, e os valores aprovados e executados de 2026 não mudam. </>}A alteração fica registrada no histórico.</p>
    </section>
  );
}

function Plano({ d, admin, contas, recarregar, setErro, irViagens }) {
  const [nova, setNova] = useState(false);
  const [editando, setEditando] = useState(null);
  const [filtro, setFiltro] = useState("todas");
  const t = d.totais;
  const trocar = async (l, corpo) => {
    try { setErro(""); await api(`/linhas/${l.id}`, { method: "PUT", body: corpo }); recarregar(); } catch (e) { setErro(e.message); }
  };
  const salvarMeses = (l, i, v) => { const meses = [...l.meses]; meses[i] = v; trocar(l, { meses }); };
  const excluir = async (l) => {
    if (!window.confirm(`Excluir a linha "${l.tarefa} | ${l.conta_desc}" (${fmt(l.total)}) do orçamento de 2027? A linha de 2026 continua visível no passo "Entender 2026" e pode ser trazida de volta.`)) return;
    try { await api(`/linhas/${l.id}`, { method: "DELETE" }); recarregar(); } catch (e) { setErro(e.message); }
  };
  const excluirGrupo = async (edt, tarefa) => {
    const alvo = d.linhas.filter((l) => l.edt === edt && (tarefa === undefined || l.tarefa === tarefa));
    const nome = tarefa === undefined ? `a Meta/EDT "${edt}" inteira (todas as ações)` : `a ação "${edt} | ${tarefa}"`;
    if (!window.confirm(`Excluir ${nome} do orçamento de 2027?\n${alvo.length} linha(s), ${fmt(alvo.reduce((a, l) => a + l.total, 0))}.\nAs linhas de 2026 continuam em "Entender 2026" e podem ser trazidas de volta.`)) return;
    try { setErro(""); await api(`/projetos/${d.projeto.orcamento}/linhas?` + new URLSearchParams(tarefa === undefined ? { edt } : { edt, tarefa }), { method: "DELETE" }); recarregar(); } catch (e) { setErro(e.message); }
  };
  const visiveis = d.linhas.filter((l) =>
    filtro === "todas" ? true : filtro === "ajustes" ? ["ajustada", "nova"].includes(l.status)
    : filtro === "alerta" ? l.alertas.length > 0 : l.status === filtro);
  const grupos = useMemo(() => agrupar(visiveis), [d, filtro]);
  const s = t.status;
  return (
    <>
      <DadosOrcamento d={d} admin={admin} recarregar={recarregar} setErro={setErro} />
      <div className="kpis">
        <Kpi rotulo="Plano 2027" valor={fmt(t.plano)} tom="f27" />
        <Kpi rotulo="Aprovado 2026" valor={fmt(t.base)} tom="f26" />
        <Kpi rotulo="Diferença" valor={fmt(t.plano - t.base)} tom={t.plano - t.base > 0 ? "pos" : "neg"} sub={t.base ? ((t.plano - t.base) / t.base * 100).toFixed(1).replace(".", ",") + "%" : ""} />
        <Kpi rotulo="Executado 2026" valor={fmt(t.realizado + t.empenhado)} tom="f26" sub={pct(t.realizado + t.empenhado, t.base) + " do aprovado"} />
      </div>
      {t.alertas > 0 && <div className="nota aviso"><strong>{t.alertas} linha(s) pedem atenção.</strong> Em 2026 o executado ficou acima do aprovado ou abaixo de metade dele. Use o filtro "Com alerta" para revisar.</div>}
      {t.removidas > 0 && <div className="nota aviso">{t.removidas} linha(s) de 2026 não existem mais no plano de 2027 (veja no passo 1, situação "removida").</div>}
      <p className="mudo">Cada linha começa igual ao aprovado de 2026 (linha cinza abaixo). Cada alteração fica registrada com o seu usuário. Linhas do plano de viagens são alteradas na aba <button className="link" onClick={irViagens}>Viagens</button>.</p>
      <div className="barra-ferramentas">
      <div className="filtros">{FILTROS.map(([k, n]) => (
        <button key={k} className={filtro === k ? "on" : ""} onClick={() => setFiltro(k)}>
          {n}{k === "ajustes" ? ` (${s.ajustada + s.nova})` : k === "mantida" ? ` (${s.mantida})` : k === "viagens" ? ` (${s.viagens})` : k === "alerta" ? ` (${t.alertas})` : ""}</button>))}</div>
        <button className="destaque" onClick={() => { setEditando(null); setNova(true); setTimeout(() => document.getElementById("form-nova")?.scrollIntoView({ behavior: "smooth", block: "center" }), 50); }}>+ Nova linha</button>
      </div>
      <p className="legenda-icones"><span><Lapis /> editar a linha inteira</span><span className="perigo"><Lixeira /> excluir de 2027 (na linha, na ação ou na Meta/EDT inteira)</span><span><Desfazer /> voltar ao aprovado de 2026</span><span className="mudo">Os meses também podem ser editados direto na tabela (Enter para salvar).</span></p>
      <div className="rolagem">
        <table className="tab grid">
          <thead><tr><th className="col-acoes">Ações</th><th className="col-conta">Conta</th>{MESES.map((m) => <th key={m} className="n">{m}</th>)}<th className="n">Total 2027</th><th className="n">Δ vs 2026</th></tr></thead>
          <tbody>
            {grupos.length === 0 && <tr><td colSpan={16} className="mudo">Nenhuma linha neste filtro.</td></tr>}
            {grupos.map(([k, ls], gi) => (
              <React.Fragment key={k}>
                {(gi === 0 || grupos[gi - 1][1][0].edt !== ls[0].edt) && (
                  <tr className="meta"><td className="col-acoes"><div className="barra-icones"><BotaoIcone icone={<Lixeira />} tom="perigo" dica="Excluir toda a Meta/EDT (todas as ações)" onClick={() => excluirGrupo(ls[0].edt)} /></div></td>
                    <td className="col-conta" colSpan={15}><span className="rotulo-nivel">Meta/EDT</span> {ls[0].edt}</td></tr>)}
                <tr className="grupo"><td className="col-acoes"><div className="barra-icones"><BotaoIcone icone={<Lixeira />} tom="perigo" dica="Excluir esta Ação/Tarefa" onClick={() => excluirGrupo(ls[0].edt, ls[0].tarefa)} /></div></td>
                  <td className="col-conta" colSpan={15}><span className="rotulo-nivel">Ação/Tarefa</span> {ls[0].tarefa}</td></tr>
                {ls.map((l) => (
                  <React.Fragment key={l.id}>
                    <tr className={l.status}>
                      <td className="col-acoes">
                        <div className="barra-icones">
                          <BotaoIcone icone={<Lapis />} dica="Editar a linha inteira" onClick={() => { setNova(false); setEditando(l); setTimeout(() => document.getElementById("form-linha")?.scrollIntoView({ behavior: "smooth", block: "center" }), 50); }} />
                          <BotaoIcone icone={<Lixeira />} tom="perigo" desligado={l.fonte === "viagens"} dica={l.fonte === "viagens" ? "Linha do plano de viagens: altere o plano na aba Viagens" : "Excluir esta linha de 2027"} onClick={() => excluir(l)} />
                          <BotaoIcone icone={<Desfazer />} desligado={l.status !== "ajustada"} dica={l.status === "ajustada" ? "Voltar aos valores aprovados em 2026" : "Sem alterações para desfazer"} onClick={() => trocar(l, { meses: l.ref.meses })} />
                        </div>
                      </td>
                      <td className="col-conta" title={l.atualizado_por ? `Última edição: ${l.atualizado_por}` : ""}>
                        <span className="mudo">{l.grupo}</span>
                        {l.status === "ajustada" && <span className="tag ajustada">ajustada</span>}
                        {l.status === "nova" && <span className="tag nova">nova</span>}
                        {l.status === "viagens" && <span className="tag viagens">plano de viagens</span>}
                        <br />{l.conta_desc}
                        {l.alertas.map((a) => <span key={a} className="alerta">⚠ {a}</span>)}
                      </td>
                      {l.meses.map((v, i) => <td key={i} className="n"><Celula valor={v} travada={l.fonte === "viagens"} onSalvar={(n) => salvarMeses(l, i, n)} /></td>)}
                      <td className="n"><strong>{fmtN(l.total)}</strong></td>
                      <td className="n">{l.ref ? <Delta de={l.ref.total} para={l.total} /> : <span className="up">+{fmtN(l.total)}</span>}</td>
                      <td />
                    </tr>
                    {l.ref && (
                      <tr className="ref"><td className="col-acoes" /><td className="col-conta">2026 aprovado · executado {fmt(l.executado)}</td>
                        {l.ref.meses.map((v, i) => <td key={i} className="n">{v ? fmtN(v) : ""}</td>)}<td className="n">{fmtN(l.ref.total)}</td><td /></tr>)}
                  </React.Fragment>))}
              </React.Fragment>))}
          </tbody>
          <tfoot><tr><td className="col-acoes" /><td className="col-conta">Total do plano 2027</td>{MESES.map((_, i) => <td key={i} className="n">{fmtN(d.linhas.reduce((a, l) => a + l.meses[i], 0))}</td>)}<td className="n">{fmtN(t.plano)}</td><td className="n"><Delta de={t.base} para={t.plano} /></td></tr></tfoot>
        </table>
      </div>
      {editando && <EditarLinha key={editando.id} l={editando} contas={contas} onFechar={() => setEditando(null)} onSalvar={async (b) => { await api(`/linhas/${editando.id}`, { method: "PUT", body: b }); recarregar(); }} />}
      {nova ? <NovaLinha contas={contas} onFechar={() => setNova(false)} onCriar={async (b) => { await api(`/projetos/${d.projeto.orcamento}/linhas`, { method: "POST", body: b }); recarregar(); }} />
            : null}
    </>
  );
}

export default function Projeto({ orcamento, admin, voltar, irViagens }) {
  const [d, setD] = useState(null);
  const [contas, setContas] = useState([]);
  const [erro, setErro] = useState("");
  const [passo, setPasso] = useState("plano");
  const carregar = useCallback(() => api(`/projetos/${orcamento}`).then(setD).catch((e) => setErro(e.message)), [orcamento]);
  useEffect(() => { carregar(); api("/contas").then(setContas); }, [carregar]);
  if (erro && !d) return <p className="erro">{erro} <button className="link" onClick={voltar}>Voltar</button></p>;
  if (!d) return <p>Carregando…</p>;
  const p = d.projeto;
  return (
    <>
      <button className="link" onClick={voltar}>← Projetos</button>
      <div className="cab">
        <div><h2 style={{ marginBottom: 6 }}>{p.descricao}</h2><p className="mudo">{p.novo ? <span className="tag ok">novo</span> : <>Orçamento {p.orcamento}</>} · Projeto {p.n_projeto || "sem número"} · {p.origem} · {p.gerente}</p>
          {!p.novo && p.origem !== p.origem_2026 && <p className="troca-origem"><span className="rotulo-nivel">Origem de recursos</span><span className="selo s26">2026</span> {p.origem_2026}<span className="seta" aria-hidden="true">→</span><span className="selo s27">2027</span> <strong>{p.origem}</strong></p>}</div>
        {admin && !p.n_projeto && <NumeroProjeto orcamento={p.orcamento} onSalvo={carregar} />}
      </div>
      <Passos ativo={passo} onMudar={setPasso} itens={[["passado", "Entender 2026"], ["plano", "Planejar 2027"]]} />
      {erro && <p className="erro" role="alert">{erro}</p>}
      {passo === "passado" ? <Passado d={d} irPlano={() => setPasso("plano")} recarregar={carregar} setErro={setErro} />
        : <Plano d={d} admin={admin} contas={contas} recarregar={carregar} setErro={setErro} irViagens={irViagens} />}
    </>
  );
}

function NumeroProjeto({ orcamento, onSalvo }) {
  const [v, setV] = useState("");
  const [erro, setErro] = useState("");
  const salvar = async () => {
    try { await api(`/projetos/${orcamento}`, { method: "PATCH", body: { n_projeto: v } }); onSalvo(); } catch (e) { setErro(e.message); }
  };
  return (
    <div className="cartao pend" style={{ margin: 0 }}>
      <strong>Nº do Projeto pendente</strong>
      <div className="acoes"><input style={{ width: 140 }} value={v} onChange={(e) => setV(e.target.value)} placeholder="ex.: 2999" inputMode="numeric" /><button className="primario" onClick={salvar} disabled={!v}>Salvar</button></div>
      {erro && <p className="erro">{erro}</p>}
    </div>
  );
}
