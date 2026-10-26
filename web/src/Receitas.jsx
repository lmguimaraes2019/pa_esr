import React, { useCallback, useEffect, useMemo, useState } from "react";
import { api, fmt, fmtN, lerNumero, MESES } from "./api.js";
import { Kpi, Delta, Passos, Celula, BotaoIcone, Lapis, Lixeira } from "./ui.jsx";

const FONTES_SUGERIDAS = ["Contrato de gestão", "Parcerias", "Growth", "Fomento", "Turmas abertas", "Projetos especiais", "Outras receitas"];
const vazio = { id: null, tipo: "receita", orcamento: "", fonte: "", descricao: "", obs: "", meses: Array(12).fill(""), ano: 2027, cliente: "", origem_cliente: "", gestor_cliente: "" };

function Formulario({ inicial, dados, onSalvar, onFechar }) {
  const [f, setF] = useState({ ...inicial, meses: inicial.meses.map((v) => (v ? String(v).replace(".", ",") : "")), valor: inicial.id && inicial.total ? String(inicial.total).replace(".", ",") : "" });
  const inter = f.tipo === "intercompany";
  const [anual, setAnual] = useState("");
  const [erro, setErro] = useState("");
  const total = f.meses.reduce((a, v) => a + (lerNumero(v) || 0), 0);
  const distribuir = () => {
    const t = lerNumero(anual);
    if (Number.isNaN(t) || t < 0) return setErro("Informe um valor anual válido.");
    const base = Math.floor((t / 12) * 100) / 100;
    const m = Array(12).fill(base); m[11] = Math.round((t - base * 11) * 100) / 100;
    setErro(""); setF({ ...f, meses: m.map((v) => String(v).replace(".", ",")) });
  };
  const salvar = async (e) => {
    e.preventDefault(); setErro("");
    if (inter) {
      const v = lerNumero(f.valor);
      if (Number.isNaN(v) || v <= 0) return setErro("Informe o valor da transferência.");
      const ano = Number(f.ano);
      if (!Number.isInteger(ano) || ano < 2020 || ano > 2100) return setErro("Informe um ano válido, a partir de 2020.");
      const corpo = { orcamento: f.orcamento, ano: Number(f.ano), cliente: f.cliente, origem_cliente: f.origem_cliente, gestor_cliente: f.gestor_cliente, obs: f.obs, descricao: f.descricao };
      try { await onSalvar(f.id ? { ...corpo, valor: v } : { ...corpo, tipo: "intercompany", valor: v }); onFechar(); } catch (x) { setErro(x.message); }
      return;
    }
    const nums = f.meses.map(lerNumero);
    if (nums.every((n) => !n) && anual.trim()) {      // só o valor anual: não precisa calendarizar
      const v = lerNumero(anual);
      if (Number.isNaN(v) || v <= 0) return setErro("Informe um valor anual válido.");
      try { await onSalvar({ orcamento: f.orcamento, fonte: f.fonte, descricao: f.descricao, obs: f.obs, valor: v }); onFechar(); } catch (x) { setErro(x.message); }
      return;
    }
    if (nums.some((n) => Number.isNaN(n) || n < 0)) return setErro("Use apenas valores positivos nos meses.");
    try { await onSalvar({ orcamento: f.orcamento, fonte: f.fonte, descricao: f.descricao, obs: f.obs, meses: nums.map((n) => Math.round(n * 100) / 100) }); onFechar(); } catch (x) { setErro(x.message); }
  };
  const fontes = [...new Set([...dados.fontes, ...FONTES_SUGERIDAS])];
  return (
    <form className="cartao" id="form-receita" onSubmit={salvar}>
      <h3>{f.id ? (inter ? "Editar transferência intercompany" : "Editar receita") : "Nova receita 2027"}</h3>
      {!f.id && <div className="passos" role="tablist" style={{ marginTop: 0 }}>
        {[["receita", "Receita"], ["intercompany", "Transferência intercompany"]].map(([k, t]) => <button type="button" key={k} role="tab" aria-selected={f.tipo === k} className={f.tipo === k ? "on" : ""} onClick={() => setF({ ...f, tipo: k })}>{t}</button>)}</div>}
      {inter ? (
        <>
          <p className="mudo">Recurso que o projeto recebe de outro projeto da casa. O ano é só a referência: a transferência é sempre contabilizada no orçamento de 2027 e não precisa ser calendarizada.</p>
          <div className="ic-form">
            <fieldset><legend>Quem recebe</legend>
              <label><span>Projeto que recebe <span className="obrig">*</span></span><select value={f.orcamento} onChange={(e) => setF({ ...f, orcamento: e.target.value })} required>
                <option value="">Selecione…</option>{dados.projetos.map((p) => <option key={p.orcamento} value={p.orcamento}>{p.orcamento} | {p.descricao}</option>)}</select></label>
            </fieldset>
            <fieldset><legend>Quem paga (projeto cliente)</legend>
              <label><span>Projeto cliente <span className="obrig">*</span></span><input value={f.cliente} onChange={(e) => setF({ ...f, cliente: e.target.value })} placeholder="ex.: 2356 - DSS-DAGSOL-SDS-RGHU FASE 5" required /></label>
              <div className="ic-linha">
                <label><span>Origem de recursos <span className="obrig">*</span></span><select value={f.origem_cliente} onChange={(e) => setF({ ...f, origem_cliente: e.target.value })} required>
                  <option value="">Selecione…</option>{dados.origens.map((o) => <option key={o}>{o}</option>)}</select></label>
                <label><span>Gestor do cliente <span className="obrig">*</span></span><input list="gestores-ic" value={f.gestor_cliente} onChange={(e) => setF({ ...f, gestor_cliente: e.target.value })} required /></label>
                <datalist id="gestores-ic">{dados.gerentes.map((g) => <option key={g} value={g} />)}</datalist>
              </div>
            </fieldset>
            <fieldset><legend>Valor</legend>
              <div className="ic-linha">
                <label><span>Valor (R$) <span className="obrig">*</span></span><input value={f.valor} inputMode="decimal" onChange={(e) => setF({ ...f, valor: e.target.value })} placeholder="250.000,00" required /></label>
                <label><span>Ano de referência <span className="obrig">*</span></span><input type="number" min="2020" max="2100" step="1" value={f.ano} onChange={(e) => setF({ ...f, ano: e.target.value })} required /></label>
                <label><span>Observação</span><input value={f.obs} onChange={(e) => setF({ ...f, obs: e.target.value })} /></label>
              </div>
            </fieldset>
          </div>
          {erro && <p className="erro" role="alert">{erro}</p>}
          <div className="acoes"><button className="primario">Salvar transferência</button><button type="button" onClick={onFechar}>Cancelar</button></div>
        </>
      ) : (<>
      <div className="grade">
        <label>Projeto<select value={f.orcamento} onChange={(e) => setF({ ...f, orcamento: e.target.value })} required>
          <option value="">Selecione…</option>{dados.projetos.map((p) => <option key={p.orcamento} value={p.orcamento}>{p.orcamento} | {p.descricao}</option>)}</select></label>
        <label>Fonte da receita<input list="fontes-receita" value={f.fonte} onChange={(e) => setF({ ...f, fonte: e.target.value })} required /></label>
        <datalist id="fontes-receita">{fontes.map((x) => <option key={x} value={x} />)}</datalist>
        <label>Descrição<input value={f.descricao} onChange={(e) => setF({ ...f, descricao: e.target.value })} placeholder="ex.: turmas AWS, repasse trimestral" /></label>
        <label>Observação<input value={f.obs} onChange={(e) => setF({ ...f, obs: e.target.value })} /></label>
      </div>
      <div className="acoes"><label style={{ maxWidth: 220 }}>Valor anual<input value={anual} inputMode="decimal" onChange={(e) => setAnual(e.target.value)} placeholder="ex.: 1.200.000,00" /></label>
        <button type="button" onClick={distribuir}>Dividir em 12 meses</button><span className="mudo">Calendarizar é opcional: só o valor anual já basta.</span></div>
      <div className="grade" style={{ gridTemplateColumns: "repeat(6, minmax(0, 1fr))" }}>
        {MESES.map((m, i) => <label key={m}>{m}<input value={f.meses[i]} inputMode="decimal" onChange={(e) => setF({ ...f, meses: f.meses.map((v, k) => (k === i ? e.target.value : v)) })} /></label>)}
      </div>
      <p><strong>Total 2027: {fmt(total)}</strong></p>
      {erro && <p className="erro" role="alert">{erro}</p>}
      <div className="acoes"><button className="primario">Salvar receita</button><button type="button" onClick={onFechar}>Cancelar</button></div>
      </>)}
    </form>
  );
}

function Lancamentos({ dados, recarregar, setErro }) {
  const [form, setForm] = useState(null);
  const [origem, setOrigem] = useState("todas");
  const [proj, setProj] = useState("todos");
  const origens = [...new Set(dados.projetos.map((p) => p.origem))];
  const filtrada = dados.linhas.filter((l) => (origem === "todas" || l.origem === origem) && (proj === "todos" || l.orcamento === proj));
  const lista = filtrada.filter((l) => l.tipo !== "intercompany");
  const listaIc = filtrada.filter((l) => l.tipo === "intercompany");
  const trocar = async (l, corpo) => { try { setErro(""); await api(`/receitas/${l.id}`, { method: "PUT", body: corpo }); recarregar(); } catch (e) { setErro(e.message); } };
  const excluir = async (l) => {
    if (!window.confirm(`Excluir a receita "${l.fonte}" do projeto ${l.orcamento} (${fmt(l.total)})?`)) return;
    try { setErro(""); await api(`/receitas/${l.id}`, { method: "DELETE" }); recarregar(); } catch (e) { setErro(e.message); }
  };
  const abrir = (f) => { setForm(f); setTimeout(() => document.getElementById("form-receita")?.scrollIntoView({ behavior: "smooth", block: "center" }), 50); };
  const salvar = async (b) => {
    if (form.id) await api(`/receitas/${form.id}`, { method: "PUT", body: b }); else await api("/receitas", { method: "POST", body: b });
    recarregar();
  };
  const tot = (i) => lista.reduce((a, l) => a + (l.calendarizada ? l.meses[i] : 0), 0);
  return (
    <>
      <div className="nota">Lance aqui a receita prevista de cada projeto, mês a mês, por fonte. O resultado de cada projeto e de cada origem de recurso é a receita menos a despesa planejada em "Despesas". A linha cinza mostra a previsão de 2026, quando existe.</div>
      <div className="barra-ferramentas">
        <div className="filtros">
          <select style={{ width: 200 }} value={origem} onChange={(e) => { setOrigem(e.target.value); setProj("todos"); }}>
            <option value="todas">Todas as origens</option>{origens.map((o) => <option key={o}>{o}</option>)}</select>
          <select style={{ width: 300 }} value={proj} onChange={(e) => setProj(e.target.value)}>
            <option value="todos">Todos os projetos</option>{dados.projetos.filter((p) => origem === "todas" || p.origem === origem).map((p) => <option key={p.orcamento} value={p.orcamento}>{p.orcamento} | {p.descricao}</option>)}</select>
        </div>
        <div className="acoes" style={{ margin: 0 }}><button className="destaque" onClick={() => abrir({ ...vazio, orcamento: proj !== "todos" ? proj : "" })}>+ Nova receita</button>
        <button onClick={() => abrir({ ...vazio, tipo: "intercompany", orcamento: proj !== "todos" ? proj : "" })}>+ Transferência intercompany</button></div>
      </div>
      <p className="legenda-icones"><span><Lapis /> editar a receita inteira</span><span className="perigo"><Lixeira /> excluir</span><span className="mudo">Os meses também podem ser editados direto na tabela (Enter para salvar).</span></p>
      <div className="rolagem">
        <table className="tab grid">
          <thead><tr><th className="col-acoes">Ações</th><th className="col-conta">Projeto e fonte</th>{MESES.map((m) => <th key={m} className="n">{m}</th>)}<th className="n">Total 2027</th><th className="n">Δ vs 2026</th></tr></thead>
          <tbody>
            {lista.length === 0 && <tr><td colSpan={16} className="mudo">Nenhuma receita lançada neste filtro. Use "+ Nova receita".</td></tr>}
            {lista.map((l) => (
              <React.Fragment key={l.id}>
                <tr>
                  <td className="col-acoes"><div className="barra-icones">
                    <BotaoIcone icone={<Lapis />} dica="Editar a receita inteira" onClick={() => abrir(l)} />
                    <BotaoIcone icone={<Lixeira />} tom="perigo" dica="Excluir esta receita" onClick={() => excluir(l)} /></div></td>
                  <td className="col-conta" title={l.atualizado_por ? `Última edição: ${l.atualizado_por}` : ""}>
                    <span className="mudo">{l.orcamento} | {l.projeto}</span><br /><strong>{l.fonte}</strong><span className="tag">{l.origem}</span>
                    {l.descricao && <><br /><span className="mudo">{l.descricao}</span></>}</td>
                  {l.meses.map((v, i) => <td key={i} className="n"><Celula valor={v} onSalvar={(n) => { const m = [...l.meses]; m[i] = n; trocar(l, { meses: m }); }} /></td>)}
                  <td className="n"><strong>{fmtN(l.total)}</strong></td>
                  <td className="n">{l.ref ? <Delta de={l.ref.total} para={l.total} altaBoa /> : <span className="down">+{fmtN(l.total)}</span>}</td>
                </tr>
                {l.ref && <tr className="ref"><td className="col-acoes" /><td className="col-conta">2026 previsto</td>{l.ref.meses.map((v, i) => <td key={i} className="n">{v ? fmtN(v) : ""}</td>)}<td className="n">{fmtN(l.ref.total)}</td><td /></tr>}
              </React.Fragment>))}
          </tbody>
          <tfoot><tr><td className="col-acoes" /><td className="col-conta">Total do filtro</td>{MESES.map((_, i) => <td key={i} className="n">{fmtN(tot(i))}</td>)}<td className="n">{fmtN(lista.reduce((a, l) => a + l.total, 0))}</td><td /></tr></tfoot>
        </table>
      </div>
      <section className="cartao ic-secao">
        <div className="cab"><div><h3 style={{ margin: 0 }}>Transferências intercompany</h3>
          <p className="mudo">Recursos recebidos de outros projetos. Contam no total de 2027, sem calendário.</p></div>
          <div className="ic-total"><span>Total no filtro</span><strong>{fmt(listaIc.reduce((a, l) => a + l.total, 0))}</strong></div></div>
        {listaIc.length === 0 ? <p className="mudo">Nenhuma transferência intercompany neste filtro. Use "+ Transferência intercompany".</p> : (
          <div className="rolagem"><table className="tab ic-tab">
            <thead><tr><th>Ações</th><th>Projeto que recebe</th><th>Projeto cliente</th><th>Origem de recursos</th><th>Gestor do cliente</th><th>Ref.</th><th className="n">Valor</th></tr></thead>
            <tbody>{listaIc.map((l) => (
              <tr key={l.id}>
                <td><div className="barra-icones"><BotaoIcone icone={<Lapis />} dica="Editar a transferência" onClick={() => abrir(l)} />
                  <BotaoIcone icone={<Lixeira />} tom="perigo" dica="Excluir a transferência" onClick={() => excluir(l)} /></div></td>
                <td><strong>{l.orcamento}</strong><br /><span className="mudo">{l.projeto}</span></td>
                <td>{l.cliente}</td>
                <td><span className="tag">{l.origem_cliente}</span></td>
                <td>{l.gestor_cliente}</td>
                <td>{l.ano}</td>
                <td className="n"><strong>{fmtN(l.total)}</strong></td>
              </tr>))}</tbody>
            <tfoot><tr><td colSpan={6}>Total</td><td className="n">{fmtN(listaIc.reduce((a, l) => a + l.total, 0))}</td></tr></tfoot>
          </table></div>)}
      </section>
      {form && <Formulario key={form.id ?? "novo"} inicial={form} dados={dados} onFechar={() => setForm(null)} onSalvar={salvar} />}
    </>
  );
}

const Resultado = ({ v }) => <strong className={v < 0 ? "res-neg" : "res-pos"}>{fmt(v)}</strong>;

function PorOrigem({ dados }) {
  return (
    <>
      <div className="nota">Resultado de 2027 por origem de recurso: receita prevista menos a despesa planejada dos projetos de cada origem. Resultado negativo significa que a despesa planejada supera a receita lançada.</div>
      <div className="rolagem"><table className="tab">
        <thead><tr><th>Origem de recurso</th><th className="n">Projetos</th><th className="n">Receita 2026</th><th className="n">Receita 2027</th><th className="n">Despesa 2026</th><th className="n">Despesa 2027</th><th className="n">Resultado 2027</th></tr></thead>
        <tbody>{dados.por_origem.map((o) => (
          <tr key={o.origem}><td><strong>{o.origem}</strong></td><td className="n">{o.projetos}</td><td className="n">{fmtN(o.receita_2026)}</td><td className="n"><strong>{fmtN(o.receita)}</strong></td>
            <td className="n">{fmtN(o.despesa_2026)}</td><td className="n"><strong>{fmtN(o.despesa)}</strong></td><td className="n"><Resultado v={o.resultado} /></td></tr>))}</tbody>
        <tfoot><tr><td>Total</td><td className="n" /><td className="n">{fmtN(dados.totais.receita_2026)}</td><td className="n">{fmtN(dados.totais.receita)}</td><td className="n">{fmtN(dados.totais.despesa_2026)}</td><td className="n">{fmtN(dados.totais.despesa)}</td><td className="n"><Resultado v={dados.totais.resultado} /></td></tr></tfoot>
      </table></div>
    </>
  );
}

function PorProjeto({ dados, irProjeto }) {
  return (
    <>
      <div className="nota">Receita e despesa de 2027 por projeto. Projetos sem receita lançada aparecem marcados: se o projeto não gera receita própria, ele é custeado pelos demais.</div>
      <div className="rolagem"><table className="tab">
        <thead><tr><th>Projeto</th><th>Origem</th><th>Gerente</th><th className="n">Receita 2027</th><th className="n">Despesa 2027</th><th className="n">Resultado</th><th /></tr></thead>
        <tbody>{dados.por_projeto.map((p) => (
          <tr key={p.orcamento}><td><button className="link" onClick={() => irProjeto(p.orcamento)}>{p.orcamento}</button> {p.projeto} {p.tipo === "receita" && <span className="tag ok">orçamento de receita</span>}</td><td>{p.origem}</td><td>{p.gerente}</td>
            <td className="n"><strong>{fmtN(p.receita)}</strong></td><td className="n">{fmtN(p.despesa)}</td><td className="n"><Resultado v={p.resultado} /></td>
            <td>{p.receita === 0 && <span className="tag aviso">sem receita</span>}</td></tr>))}</tbody>
      </table></div>
    </>
  );
}

export default function Receitas({ irProjeto }) {
  const [dados, setDados] = useState(null);
  const [aba, setAba] = useState("lancamentos");
  const [erro, setErro] = useState("");
  const carregar = useCallback(() => api("/receitas").then(setDados).catch((e) => setErro(e.message)), []);
  useEffect(() => { carregar(); }, [carregar]);
  if (!dados) return erro ? <p className="erro">{erro}</p> : <p>Carregando…</p>;
  const t = dados.totais;
  const max = Math.max(1, ...dados.mensal.map((m) => Math.max(m.receita, m.despesa)));
  return (
    <>
      <h2>Gestão de receitas 2027</h2>
      <div className="kpis">
        <Kpi rotulo="Receita prevista 2027" valor={fmt(t.receita)} tom="f27" sub={t.receita_2026 ? <Delta de={t.receita_2026} para={t.receita} altaBoa /> : `${t.linhas} lançamentos`} />
        <Kpi rotulo="Despesa planejada 2027" valor={fmt(t.despesa)} tom="f27" sub={<Delta de={t.despesa_2026} para={t.despesa} />} />
        <Kpi rotulo="Resultado 2027" valor={fmt(t.resultado)} tom={t.resultado < 0 ? "rneg" : "rpos"} sub="receita menos despesa" />
        <Kpi rotulo="Receita prevista 2026" valor={fmt(t.receita_2026)} tom="f26" />
        {t.intercompany > 0 && <Kpi rotulo="Transferências intercompany" valor={fmt(t.intercompany)} tom="f27" sub="já incluídas na receita 2027" />}
      </div>
      <section className="cartao"><h3>Receita e despesa por mês</h3>
        {t.intercompany > 0 && <p className="mudo">A receita por mês não inclui {fmt(t.intercompany)} de transferências intercompany, que não são calendarizadas.</p>}
        <div className="legenda"><span><i style={{ background: "var(--laranja)" }} />Receita 2027</span><span><i style={{ background: "var(--azul)" }} />Despesa 2027</span></div>
        <div className="meses">{dados.mensal.map((m) => (
          <div key={m.mes} title={`${m.mes}: receita ${fmt(m.receita)} | despesa ${fmt(m.despesa)} | saldo ${fmt(m.receita - m.despesa)}`}><div className="col" style={{ gap: 2 }}>
            <span style={{ height: (m.receita / max) * 100 + "%" }} /><span style={{ height: (m.despesa / max) * 100 + "%", background: "var(--azul)" }} /></div><small>{m.mes.slice(0, 3)}</small></div>))}</div>
      </section>
      {erro && <p className="erro" role="alert">{erro}</p>}
      <Passos ativo={aba} onMudar={setAba} itens={[["lancamentos", "Lançamentos de receita"], ["origem", "Resultado por origem"], ["projeto", "Resultado por projeto"]]} />
      {aba === "lancamentos" && <Lancamentos dados={dados} recarregar={carregar} setErro={setErro} />}
      {aba === "origem" && <PorOrigem dados={dados} />}
      {aba === "projeto" && <PorProjeto dados={dados} irProjeto={irProjeto} />}
    </>
  );
}
