import React, { useCallback, useEffect, useMemo, useState } from "react";
import { api, fmt, fmtN, lerNumero } from "./api.js";
import { custoMensal } from "./pessoal.js";
import { TarefaOrc, Kpi, BotaoIcone, Lapis, Lixeira } from "./ui.jsx";

const MESES_N = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];
const Obrig = () => <span className="obrig" title="Informação obrigatória">*</span>;
const bonito = (s) => s.toLowerCase().replace(/(^|\s)\S/g, (m) => m.toUpperCase());

function Formulario({ inicial, dados, onSalvar, onFechar }) {
  const [f, setF] = useState(inicial);
  const [erro, setErro] = useState("");
  const set = (k, v) => setF((x) => ({ ...x, [k]: v }));
  const par = useMemo(() => Object.fromEntries(dados.parametros.map((p) => [p.chave, p.valor])), [dados]);
  const trajs = [...new Set(dados.tabela.map((t) => t.trajetoria))];
  const niveis = [...new Set(dados.tabela.filter((t) => t.trajetoria === f.trajetoria).map((t) => t.nivel))];
  const grupos = dados.tabela.filter((t) => t.trajetoria === f.trajetoria && t.nivel === f.nivel).map((t) => t.grupo);
  const faixa = dados.tabela.find((t) => t.trajetoria === f.trajetoria && t.nivel === f.nivel && t.grupo === f.grupo);
  const salTab = faixa ? faixa.inicio + ((faixa.fim - faixa.inicio) * Number(f.posicao)) / 100 : 0;
  const sal = salTab * (1 + dados.reajuste / 100);
  const c = faixa ? custoMensal(sal, par) : null;
  const q = Math.max(Number(f.quantidade) || 1, 1);
  const meses = 13 - Number(f.mes_inicio);
  const cat = dados.catalogo.itens;
  const valorEq = (tipo) => cat.find((i) => i.codigo === f[tipo] && i.tipo === tipo)?.valor || 0;
  const eqUnit = valorEq("computador") + valorEq("monitor") + valorEq("periferico");
  const opcoes = (tipo) => cat.filter((i) => i.tipo === tipo).map((i) => <option key={i.codigo} value={i.codigo}>{i.codigo} | {fmt(i.valor)} | {i.nome}</option>);
  const salvar = async (e) => {
    e.preventDefault(); setErro("");
    try { await onSalvar({ orcamento: f.orcamento, funcao: f.funcao, cargo: f.cargo, trajetoria: f.trajetoria, nivel: f.nivel, grupo: f.grupo,
      posicao: Number(f.posicao), mes_inicio: Number(f.mes_inicio), quantidade: q, justificativa: f.justificativa, edt: f.edt || "", tarefa: f.tarefa || "",
      computador: f.computador || "", monitor: f.monitor || "", periferico: f.periferico || "" }); onFechar(); } catch (x) { setErro(x.message); }
  };
  return (
    <form className="cartao" id="form-hc" onSubmit={salvar}>
      <h3>{f.id ? "Editar posição" : "Nova posição de headcount 2027"}</h3>
      <p className="mudo">Campos com <Obrig /> são necessários para a posição ser considerada completa.</p>
      <div className="grade">
        <label><span>Projeto que vai custear <Obrig /></span><select value={f.orcamento} onChange={(e) => setF((x) => ({ ...x, orcamento: e.target.value, edt: "", tarefa: "", computador: "", monitor: "", periferico: "" }))} required>
          <option value="">Selecione…</option><optgroup label="Meus projetos">{dados.projetos.filter((p) => p.meu).map((p) => <option key={p.orcamento} value={p.orcamento}>{p.orcamento} | {p.descricao}</option>)}</optgroup>
          <optgroup label="Projetos de outros gestores">{dados.projetos.filter((p) => !p.meu).map((p) => <option key={p.orcamento} value={p.orcamento}>{p.orcamento} | {p.descricao} ({p.gerente})</option>)}</optgroup></select>
          <small className="mudo">Pode ser qualquer projeto da casa, inclusive de outro gestor.</small></label>
        <TarefaOrc dados={dados} orcamento={f.orcamento} edt={f.edt} tarefa={f.tarefa} onChange={(a, b) => setF((x) => ({ ...x, edt: a, tarefa: b }))} />
        <label><span>Função <Obrig /></span><input value={f.funcao} onChange={(e) => set("funcao", e.target.value)} placeholder="ex.: Coordenador de turmas" /></label>
        <label><span>Cargo <Obrig /></span><input value={f.cargo} onChange={(e) => set("cargo", e.target.value)} placeholder="ex.: Analista de Desenvolvimento Pleno" /></label>
        <label>Quantidade de posições<input type="number" min="1" max="100" value={f.quantidade} onChange={(e) => set("quantidade", e.target.value)} /></label>
      </div>
      <h4 className="sub">Trajetória e faixa salarial <span className="mudo">Tabela Salarial 2025</span></h4>
      <div className="grade">
        <label><span>Trajetória <Obrig /></span><select value={f.trajetoria} onChange={(e) => setF((x) => ({ ...x, trajetoria: e.target.value, nivel: "", grupo: "" }))} required>
          <option value="">Selecione…</option>{trajs.map((t) => <option key={t} value={t}>{bonito(t)}</option>)}</select></label>
        <label><span>Nível <Obrig /></span><select value={f.nivel} disabled={!f.trajetoria} onChange={(e) => setF((x) => ({ ...x, nivel: e.target.value, grupo: "" }))} required>
          <option value="">Selecione…</option>{niveis.map((t) => <option key={t} value={t}>{bonito(t)}</option>)}</select></label>
        <label><span>Grupo <Obrig /></span><select value={f.grupo} disabled={!f.nivel} onChange={(e) => set("grupo", e.target.value)} required>
          <option value="">Selecione…</option>{grupos.map((t) => <option key={t} value={t}>{bonito(t)}</option>)}</select></label>
        <label>Mês de início em 2027<select value={f.mes_inicio} onChange={(e) => set("mes_inicio", e.target.value)}>{MESES_N.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}</select></label>
      </div>
      {faixa && (
        <div className="faixa">
          <div className="faixa-topo"><span>Início da faixa (80%) <strong>{fmt(faixa.inicio)}</strong></span><span>Fim da faixa (120%) <strong>{fmt(faixa.fim)}</strong></span></div>
          <input type="range" min="0" max="100" step="1" value={f.posicao} onChange={(e) => set("posicao", e.target.value)} aria-label="Posição na faixa salarial" />
          <div className="faixa-topo"><span>Posição na faixa: <strong>{f.posicao}%</strong> {Number(f.posicao) === 50 && "(ponto médio)"}</span>
            <span>Salário {dados.reajuste ? `com reajuste de ${fmtN(dados.reajuste)}%` : ""}: <strong>{fmt(sal)}</strong></span></div>
        </div>)}
      <label><span>Justificativa <Obrig /></span><textarea rows={3} value={f.justificativa} onChange={(e) => set("justificativa", e.target.value)} placeholder="Por que a posição é necessária? Qual entrega ou meta depende dela?" /></label>
      <h4 className="sub">Equipamentos <span className="mudo">Catálogo de Hardware Homologado, atualizado em {dados.catalogo.atualizado_em}</span></h4>
      <div className="grade">
        <label>Computador<select value={f.computador || ""} onChange={(e) => set("computador", e.target.value)}>
          <option value="">Sem computador</option>{opcoes("computador")}</select>
          <small className="mudo">Regular: D1 | Intermediário: N2.A ou N2.B | Avançado: N3.A ou N3.B | Diretoria e perfis aprovados: N4, N5.a, N5.b</small></label>
        <label>Monitor<select value={f.monitor || ""} onChange={(e) => set("monitor", e.target.value)}>
          <option value="">Sem monitor</option>{opcoes("monitor")}</select></label>
        <label>Periférico<select value={f.periferico || ""} onChange={(e) => set("periferico", e.target.value)}>
          <option value="">Sem periférico</option>{opcoes("periferico")}</select></label>
      </div>
      {eqUnit > 0 && <p className="mudo">Custo pontual dos equipamentos: <strong>{fmt(eqUnit)}</strong> por posição, <strong>{fmt(eqUnit * q)}</strong> para {q} posição(ões), lançado em {MESES_N[Number(f.mes_inicio) - 1]} na conta Hardware. A aquisição é solicitada à GTI, Gestão de Ativos.</p>}
      {c && (
        <div className="resumo-custo">
          <span>Salário e encargos <strong>{fmt(c.encargos)}</strong></span><span>Benefícios <strong>{fmt(c.beneficios)}</strong></span><span>Provisões (férias e 13º) <strong>{fmt(c.provisoes)}</strong></span>
          <span>Custo mensal <strong>{fmt(c.mensal)}</strong></span><span>Anualizado ({q} posição) <strong>{fmt(c.anual * q)}</strong></span><span>Em 2027 ({meses} meses{eqUnit ? " + equipamentos" : ""}) <strong>{fmt(c.mensal * meses * q + eqUnit * q)}</strong></span>
        </div>)}
      {erro && <p className="erro" role="alert">{erro}</p>}
      <div className="acoes"><button className="primario">Salvar posição</button><button type="button" onClick={onFechar}>Cancelar</button></div>
    </form>
  );
}

export default function Headcount({ admin, irProjeto }) {
  const [dados, setDados] = useState(null);
  const [form, setForm] = useState(null);
  const [proj, setProj] = useState("todos");
  const [erro, setErro] = useState("");
  const carregar = useCallback(() => api("/headcount").then(setDados).catch((e) => setErro(e.message)), []);
  useEffect(() => { carregar(); }, [carregar]);
  if (!dados) return erro ? <p className="erro">{erro}</p> : <p>Carregando…</p>;
  const t = dados.totais;
  const novo = { id: null, orcamento: proj !== "todos" ? proj : "", funcao: "", cargo: "", trajetoria: "", nivel: "", grupo: "", posicao: 50, mes_inicio: 1, quantidade: 1, justificativa: "", edt: "", tarefa: "" };
  const lista = dados.itens.filter((d) => proj === "todos" || d.orcamento === proj);
  const abrir = (d) => { setForm(d); setTimeout(() => document.getElementById("form-hc")?.scrollIntoView({ behavior: "smooth", block: "center" }), 50); };
  const salvar = async (b) => { if (form.id) await api(`/headcount/${form.id}`, { method: "PUT", body: b }); else await api("/headcount", { method: "POST", body: b }); carregar(); };
  const excluir = async (d) => {
    if (!window.confirm(`Excluir a posição "${d.funcao || d.cargo || "sem nome"}" (${fmt(d.anualizado)} por ano)?`)) return;
    try { setErro(""); await api(`/headcount/${d.id}`, { method: "DELETE" }); carregar(); } catch (x) { setErro(x.message); }
  };
  return (
    <>
      <h2>Headcount 2027</h2>
      <div className="nota">Registre cada nova posição com função, cargo, trajetória, nível e grupo da Tabela Salarial e o projeto que vai custeá-la. O valor anualizado é estimado com as faixas salariais e as fórmulas da planilha de custo de pessoal (encargos, benefícios e provisões de férias e 13º).</div>
      <div className="kpis">
        <Kpi rotulo="Posições novas" valor={t.posicoes} tom="f27" sub={t.incompletos ? `${t.incompletos} com pendências` : undefined} />
        <Kpi rotulo="Custo anualizado" valor={fmt(t.anualizado)} tom="f27" sub="12 meses" />
        <Kpi rotulo="Custo em 2027" valor={fmt(t.custo_2027)} tom="f27" sub="a partir do mês de início" />
      </div>
      <p className="mudo">O custo usa as fórmulas da planilha de custo de pessoal e as faixas da Tabela Salarial 2025{dados.reajuste ? `, com reajuste de ${fmtN(dados.reajuste)}%` : ""}. {admin ? "Os parâmetros ficam em Administração, Premissas." : "Os parâmetros são mantidos pelo administrador."}</p>
      {erro && <p className="erro" role="alert">{erro}</p>}
      <div className="barra-ferramentas">
        <div className="filtros"><select style={{ width: 320 }} value={proj} onChange={(e) => setProj(e.target.value)}>
          <option value="todos">Todos os projetos</option>{dados.projetos.map((p) => <option key={p.orcamento} value={p.orcamento}>{p.orcamento} | {p.descricao}</option>)}</select></div>
        <button className="destaque" onClick={() => abrir(novo)}>+ Nova posição</button>
      </div>
      <p className="legenda-icones"><span><Lapis /> editar a posição</span><span className="perigo"><Lixeira /> excluir</span></p>
      <div className="rolagem"><table className="tab">
        <thead><tr><th>Ações</th><th>Função e cargo</th><th>Trajetória, nível e grupo</th><th>Projeto que custeia</th><th className="n">Qtd</th><th>Início</th><th className="n">Salário</th><th>Equipamentos</th><th className="n">Custo mensal</th><th className="n">Anualizado</th><th className="n">Em 2027</th><th>Situação</th></tr></thead>
        <tbody>
          {lista.length === 0 && <tr><td colSpan={12} className="mudo">Nenhuma posição lançada. Use "+ Nova posição".</td></tr>}
          {lista.map((d) => (
            <tr key={d.id}>
              <td style={{ whiteSpace: "nowrap" }}><div className="barra-icones"><BotaoIcone icone={<Lapis />} dica="Editar a posição" onClick={() => abrir(d)} /><BotaoIcone icone={<Lixeira />} tom="perigo" dica="Excluir a posição" onClick={() => excluir(d)} /></div></td>
              <td><strong>{d.funcao || <span className="up">sem função</span>}</strong><br /><span className="mudo">{d.cargo || "cargo não informado"}</span>
                {d.justificativa && <><br /><span className="mudo" title={d.justificativa} style={{ fontSize: ".78rem" }}>{d.justificativa.length > 80 ? d.justificativa.slice(0, 80) + "…" : d.justificativa}</span></>}</td>
              <td>{bonito(d.trajetoria)}<br /><span className="mudo">{bonito(d.nivel)} | {bonito(d.grupo)} | {d.posicao}% da faixa</span></td>
              <td><button className="link" onClick={() => irProjeto(d.orcamento)}>{d.orcamento}</button><br /><span className="mudo">{d.projeto}</span>{!(dados.projetos.find((p) => p.orcamento === d.orcamento)?.meu) && <><br /><span className="tag aviso">projeto de {dados.projetos.find((p) => p.orcamento === d.orcamento)?.gerente}</span></>}{d.tarefa && <><br /><span className="mudo" style={{ fontSize: ".76rem" }}>entra em: {d.tarefa}</span></>}</td>
              <td className="n">{d.quantidade}</td><td>{MESES_N[d.mes_inicio - 1].slice(0, 3)}</td>
              <td className="n">{fmtN(d.custo.salario)}</td>
              <td style={{ fontSize: ".8rem" }}>{d.computador || d.monitor || d.periferico ? <>{[d.computador, d.monitor, d.periferico].filter(Boolean).join(" + ")}<br /><span className="mudo">{fmtN(d.equipamentos.total)}</span></> : <span className="mudo">-</span>}</td><td className="n">{fmtN(d.custo.mensal)}</td>
              <td className="n"><strong>{fmtN(d.anualizado)}</strong></td><td className="n"><strong>{fmtN(d.custo_2027)}</strong></td>
              <td>{d.faltando.length === 0 ? <span className="tag ok">completo</span> : <><span className="tag aviso">pendente</span><div className="pend-lista">{d.faltando.map((x) => <span key={x}>{x}</span>)}</div></>}</td>
            </tr>))}
        </tbody>
        <tfoot><tr><td colSpan={4}>Total do filtro</td><td className="n">{lista.reduce((a, d) => a + d.quantidade, 0)}</td><td /><td /><td /><td /><td className="n">{fmtN(lista.reduce((a, d) => a + d.anualizado, 0))}</td><td className="n">{fmtN(lista.reduce((a, d) => a + d.custo_2027, 0))}</td><td /></tr></tfoot>
      </table></div>
      {form && <Formulario key={form.id ?? "novo"} inicial={form} dados={dados} onFechar={() => setForm(null)} onSalvar={salvar} />}
      {dados.por_projeto.length > 0 && (
        <section className="cartao"><h3>Por projeto</h3><div className="rolagem"><table className="tab">
          <thead><tr><th>Projeto</th><th className="n">Posições</th><th className="n">Anualizado</th><th className="n">Em 2027</th></tr></thead>
          <tbody>{dados.por_projeto.map((p) => <tr key={p.orcamento}><td><button className="link" onClick={() => irProjeto(p.orcamento)}>{p.orcamento}</button> {p.projeto}</td><td className="n">{p.posicoes}</td><td className="n">{fmtN(p.anualizado)}</td><td className="n"><strong>{fmtN(p.custo_2027)}</strong></td></tr>)}</tbody></table></div></section>)}
    </>
  );
}
