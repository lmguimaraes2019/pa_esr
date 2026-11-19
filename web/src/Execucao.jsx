import OutrosProjetos from "./OutrosProjetos.jsx";
import React, { useEffect, useMemo, useState } from "react";
import { api, fmtN } from "./api.js";
import { Kpi } from "./ui.jsx";

// Formas de agrupar os lançamentos. "chave" separa os grupos; "nome" é o que aparece na linha do grupo.
const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
const GRUPOS = {
  gerencia: { rotulo: "Gerência", chave: (x) => x.gerencia || "Sem gerência", nome: (x) => x.gerencia || "Sem gerência" },
  gerente: { rotulo: "Gerente do projeto", chave: (x) => x.gerente || "-", nome: (x) => x.gerente || "Sem gerente" },
  projeto: { rotulo: "Projeto", chave: (x) => x.orcamento, nome: (x) => `${x.orcamento} | ${x.projeto}` },
  centro_custo: { rotulo: "Centro de custo", chave: (x) => x.centro_custo || "-", nome: (x) => x.centro_custo || "Sem centro de custo" },
  edt: { rotulo: "EDT (meta)", chave: (x) => x.edt || "-", nome: (x) => x.edt || "Sem EDT" },
  tarefa: { rotulo: "Tarefa", chave: (x) => x.edt + "|" + x.tarefa, nome: (x) => x.tarefa || "Sem tarefa" },
  grupo: { rotulo: "Grupo de despesa", chave: (x) => x.grupo || "-", nome: (x) => x.grupo || "Sem grupo" },
  conta: { rotulo: "Conta contábil", chave: (x) => x.conta || "-", nome: (x) => x.conta || "Sem conta" },
  fornecedor: { rotulo: "Fornecedor", chave: (x) => x.fornecedor || "-", nome: (x) => x.fornecedor || "Sem fornecedor" },
  origem: { rotulo: "Origem do recurso", chave: (x) => x.origem || "-", nome: (x) => x.origem || "Sem origem" },
  mes: { rotulo: "Mês", chave: (x) => (x.digitacao || "").slice(5, 7) || "00", nome: (x) => MESES[Number((x.digitacao || "").slice(5, 7)) - 1] ? MESES[Number(x.digitacao.slice(5, 7)) - 1] + "/2026" : "Sem data" },
};
const CAMPOS = [
  ["digitacao", "Data", (x) => dataBr(x.digitacao)], ["tipo", "Tipo", (x) => x.tipo], ["orcamento", "Orçamento", (x) => x.orcamento], ["projeto", "Projeto", (x) => x.projeto],
  ["gerencia", "Gerência", (x) => x.gerencia], ["centro_custo", "Centro de custo", (x) => x.centro_custo], ["edt", "EDT", (x) => x.edt], ["tarefa", "Tarefa", (x) => x.tarefa],
  ["conta", "Conta contábil", (x) => x.conta], ["fornecedor", "Fornecedor", (x) => x.fornecedor], ["nota_fiscal", "Nota fiscal", (x) => x.nota_fiscal], ["sc", "SC e item", (x) => x.sc],
  ["produto", "Produto", (x) => x.produto], ["solicitante", "Solicitante", (x) => x.solicitante], ["contrato", "Contrato", (x) => x.contrato], ["vencimento", "Vencimento", (x) => dataBr(x.vencimento)],
  ["baixa", "Baixa", (x) => dataBr(x.baixa)], ["obs", "Observação", (x) => x.obs], ["valor", "Valor (R$)", (x) => x.valor],
];
function dataBr(s) { return s ? s.split("-").reverse().join("/") : ""; }

const soma = (l, t) => l.reduce((a, x) => a + (x.tipo === t ? x.valor : 0), 0);

function agrupar(lista, niveis) {
  if (!niveis.length) return null;
  const g = GRUPOS[niveis[0]], mapa = new Map();
  for (const x of lista) { const k = g.chave(x); if (!mapa.has(k)) mapa.set(k, { k, nome: g.nome(x), itens: [] }); mapa.get(k).itens.push(x); }
  const grupos = [...mapa.values()].sort((a, b) => (niveis[0] === "mes" ? a.k.localeCompare(b.k) : soma(b.itens, "Realizado") + soma(b.itens, "Empenhado") - soma(a.itens, "Realizado") - soma(a.itens, "Empenhado")));
  return grupos.map((x) => ({ ...x, filhos: agrupar(x.itens, niveis.slice(1)) }));
}

function baixarCsv(lista) {
  const esc = (v) => { const s = String(v ?? ""); return /[;"\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; };
  const linhas = [CAMPOS.map((c) => c[1]).join(";"), ...lista.map((x) => CAMPOS.map(([, , f]) => { const v = f(x); return esc(typeof v === "number" ? v.toFixed(2).replace(".", ",") : v); }).join(";"))];
  const url = URL.createObjectURL(new Blob(["﻿" + linhas.join("\r\n")], { type: "text/csv;charset=utf-8" }));
  const a = document.createElement("a"); a.href = url; a.download = "execucao_2026_detalhada.csv"; a.click(); URL.revokeObjectURL(url);
}

function Detalhe({ itens }) {
  const [max, setMax] = useState(100);
  const ord = [...itens].sort((a, b) => (a.digitacao || "").localeCompare(b.digitacao || ""));
  return (
    <div className="exe-det rolagem"><table className="tab compacta">
      <thead><tr><th>Data</th><th>Tipo</th><th>Fornecedor</th><th>Nota fiscal</th><th>SC</th><th>Conta</th><th>Produto / observação</th><th>Solicitante</th><th className="n">Valor</th></tr></thead>
      <tbody>{ord.slice(0, max).map((x) => (
        <tr key={x.id}><td>{dataBr(x.digitacao)}</td><td><span className={"tag " + (x.tipo === "Empenhado" ? "aviso" : "ok")}>{x.tipo}</span></td><td>{x.fornecedor || "-"}</td><td>{x.nota_fiscal || "-"}</td><td>{x.sc || "-"}</td>
          <td>{x.conta}</td><td title={x.obs}>{x.produto}{x.obs && <span className="mudo"> | {x.obs.length > 70 ? x.obs.slice(0, 70) + "…" : x.obs}</span>}</td><td>{x.solicitante || "-"}</td><td className="n">{fmtN(x.valor)}</td></tr>))}</tbody>
    </table>
      {ord.length > max && <button className="link" onClick={() => setMax(max + 200)}>mostrar mais ({ord.length - max} lançamentos restantes)</button>}
    </div>
  );
}

function No({ g, nivel, niveis, abertos, alternar, caminho }) {
  const id = caminho + "/" + g.k, aberto = abertos.has(id);
  return (
    <>
      <tr className={"exe-g n" + nivel} onClick={() => alternar(id)} tabIndex={0} onKeyDown={(e) => e.key === "Enter" && alternar(id)}>
        <td style={{ paddingLeft: 10 + nivel * 22 }}><span className="seta">{aberto ? "▾" : "▸"}</span> <strong>{g.nome}</strong> <span className="tag">{g.itens.length}</span></td>
        <td className="n">{fmtN(soma(g.itens, "Realizado"))}</td><td className="n mudo">{fmtN(soma(g.itens, "Empenhado"))}</td>
      </tr>
      {aberto && (g.filhos
        ? g.filhos.map((f) => <No key={f.k} g={f} nivel={nivel + 1} niveis={niveis} abertos={abertos} alternar={alternar} caminho={id} />)
        : <tr className="exe-d"><td colSpan={3} style={{ paddingLeft: 10 + (nivel + 1) * 22 }}><Detalhe itens={g.itens} /></td></tr>)}
    </>
  );
}

export default function Execucao({ irProjeto }) {
  const [d, setD] = useState(null), [erro, setErro] = useState("");
  const [n1, setN1] = useState("gerencia"), [n2, setN2] = useState("projeto"), [n3, setN3] = useState("");
  const [tipo, setTipo] = useState(""), [ger, setGer] = useState(""), [busca, setBusca] = useState("");
  const [abertos, setAbertos] = useState(new Set());
  const [ordem, setOrdem] = useState(["digitacao", 1]), [max, setMax] = useState(300);
  useEffect(() => { api("/execucao-detalhe").then(setD).catch((e) => setErro(e.message)); }, []);
  const niveis = [n1, n2, n3].filter(Boolean).filter((v, i, a) => a.indexOf(v) === i);
  const lista = useMemo(() => {
    if (!d) return [];
    const q = busca.trim().toLowerCase();
    return d.itens.filter((x) => (!tipo || x.tipo === tipo) && (!ger || x.gerencia === ger)
      && (!q || [x.fornecedor, x.nota_fiscal, x.sc, x.produto, x.obs, x.projeto, x.orcamento, x.conta, x.solicitante, x.contrato, x.centro_custo, x.tarefa].join(" ").toLowerCase().includes(q)));
  }, [d, tipo, ger, busca]);
  const arvore = useMemo(() => agrupar(lista, niveis), [lista, niveis.join(",")]);
  const plana = useMemo(() => {
    const [k, s] = ordem, f = (CAMPOS.find((c) => c[0] === k) || CAMPOS[0])[2];
    return [...lista].sort((a, b) => { const x = f(a), y = f(b); return (typeof x === "number" ? x - y : String(x ?? "").localeCompare(String(y ?? ""))) * s; });
  }, [lista, ordem]);
  if (!d) return erro ? <p className="erro">{erro}</p> : <p>Carregando…</p>;
  const gerencias = [...new Set(d.itens.map((x) => x.gerencia))].sort();
  const alternar = (id) => setAbertos((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const todosIds = (gs, cam = "") => gs.flatMap((g) => [cam + "/" + g.k, ...(g.filhos ? todosIds(g.filhos, cam + "/" + g.k) : [])]);
  const real = soma(lista, "Realizado"), emp = soma(lista, "Empenhado");
  const cf = d.conferencia, dif = Math.abs(cf.realizado_execucao - cf.realizado_lancamentos) + Math.abs(cf.empenhado_execucao - cf.empenhado_lancamentos);
  const seletor = (v, set, rotulo, obrigatorio) => (
    <label className="exe-sel">{rotulo}<select value={v} onChange={(e) => set(e.target.value)}>{!obrigatorio && <option value="">(nenhum)</option>}{Object.entries(GRUPOS).map(([k, g]) => <option key={k} value={k}>{g.rotulo}</option>)}</select></label>);
  return (
    <>
      <h2>Execução de 2026 em detalhe</h2>
      <div className="nota">Cada linha é um lançamento da base do Protheus (realizado e empenhado de 2026). Use para conferir os valores que aparecem nas outras páginas: agrupe por gerência, projeto, centro de custo, conta ou fornecedor, busque por fornecedor, nota fiscal ou SC e baixe a planilha. O empenhado é só informativo e não entra no saldo dos projetos.</div>
      {!d.carregado && <div className="nota aviso"><strong>Os lançamentos detalhados ainda não foram carregados.</strong> O administrador precisa reimportar a base do Protheus em Administração, Realizado 2026. Depois disso o detalhe aparece aqui.</div>}
      {d.carregado && dif > 1 && <div className="nota aviso">Os lançamentos somam valores diferentes dos totais por projeto (realizado {fmtN(cf.realizado_lancamentos)} contra {fmtN(cf.realizado_execucao)}). Reimporte a base do Protheus para sincronizar.</div>}
      <div className="kpis">
        <Kpi rotulo="Realizado" valor={"R$ " + fmtN(real)} tom="f26" sub="no filtro atual" />
        <Kpi rotulo="Empenhado (informativo)" valor={"R$ " + fmtN(emp)} tom="f26" sub="não entra no saldo" />
        <Kpi rotulo="Lançamentos" valor={lista.length} tom="f26" sub={`${new Set(lista.map((x) => x.orcamento)).size} projeto(s)`} />
        <Kpi rotulo="Fornecedores" valor={new Set(lista.map((x) => x.fornecedor).filter(Boolean)).size} tom="f26" />
      </div>
      <section className="cartao exe-barra">
        <div className="exe-linha">
          {seletor(n1, setN1, "Agrupar por", false)}{seletor(n2, setN2, "e depois por", false)}{seletor(n3, setN3, "e depois por", false)}
          <label className="exe-sel">Mostrar<select value={tipo} onChange={(e) => setTipo(e.target.value)}><option value="">Realizado e empenhado</option><option value="Realizado">Só realizado</option><option value="Empenhado">Só empenhado</option></select></label>
          {gerencias.length > 1 && <label className="exe-sel">Gerência<select value={ger} onChange={(e) => setGer(e.target.value)}><option value="">Todas</option>{gerencias.map((g) => <option key={g}>{g}</option>)}</select></label>}
        </div>
        <div className="exe-linha">
          <input className="exe-busca" placeholder="Buscar fornecedor, nota fiscal, SC, produto, projeto, conta…" value={busca} onChange={(e) => setBusca(e.target.value)} />
          {arvore && <><button onClick={() => setAbertos(new Set(todosIds(arvore)))}>Expandir tudo</button><button onClick={() => setAbertos(new Set())}>Recolher tudo</button></>}
          <button className="destaque" onClick={() => baixarCsv(lista)} disabled={!lista.length}>Baixar planilha (CSV)</button>
        </div>
      </section>
      {!lista.length ? <p className="mudo">Nenhum lançamento neste filtro.</p> : arvore ? (
        <div className="rolagem"><table className="tab exe-tab">
          <thead><tr><th>{niveis.map((n) => GRUPOS[n].rotulo).join(" > ")}</th><th className="n">Realizado</th><th className="n">Empenhado (info)</th></tr></thead>
          <tbody>{arvore.map((g) => <No key={g.k} g={g} nivel={0} niveis={niveis} abertos={abertos} alternar={alternar} caminho="" />)}</tbody>
          <tfoot><tr><td>Total</td><td className="n">{fmtN(real)}</td><td className="n">{fmtN(emp)}</td></tr></tfoot>
        </table></div>
      ) : (
        <div className="rolagem exe-plana"><table className="tab compacta">
          <thead><tr>{CAMPOS.map(([k, t]) => <th key={k} className={k === "valor" ? "n" : ""} style={{ cursor: "pointer" }} onClick={() => setOrdem([k, ordem[0] === k ? -ordem[1] : 1])}>{t}{ordem[0] === k ? (ordem[1] > 0 ? " ▲" : " ▼") : ""}</th>)}</tr></thead>
          <tbody>{plana.slice(0, max).map((x) => <tr key={x.id}>{CAMPOS.map(([k, , f]) => <td key={k} className={k === "valor" ? "n" : ""}>{k === "valor" ? fmtN(x.valor) : k === "orcamento" ? <button className="link" onClick={() => irProjeto(x.orcamento)}>{x.orcamento}</button> : f(x)}</td>)}</tr>)}</tbody>
        </table>{plana.length > max && <button className="link" onClick={() => setMax(max + 500)}>mostrar mais ({plana.length - max} restantes)</button>}</div>
      )}
      <OutrosProjetos />
    </>
  );
}
