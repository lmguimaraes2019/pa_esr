import React, { useEffect, useState } from "react";
import { fmt, fmtN, fmtI, lerNumero } from "./api.js";

export function Kpi({ rotulo, valor, sub, tom }) {
  return <div className={"kpi " + (tom || "")}><span>{rotulo}</span><strong>{valor}</strong>{sub && <small>{sub}</small>}</div>;
}

export function Delta({ de, para, pct = false, altaBoa = false }) {
  const d = para - de;
  if (Math.abs(d) < 0.005) return <span className="mudo">igual</span>;
  return <span className={(d > 0) !== altaBoa ? "up" : "down"}>{d > 0 ? "+" : ""}{fmt(d)}{pct && de ? ` (${((d / de) * 100).toFixed(1).replace(".", ",")}%)` : ""}</span>;
}

export const pct = (a, b) => (b > 0 ? ((a / b) * 100).toFixed(0) + "%" : "-");

/** Previsão dos gestores para o executado até 31/12/2026. Soma só os projetos que já informaram e compara com o aprovado deles. */
export function previsaoDe(lista) {
  const ok = lista.filter((p) => p.previsao_2026 !== null && p.previsao_2026 !== undefined);
  return { n: ok.length, de: lista.length, valor: ok.reduce((a, p) => a + p.previsao_2026, 0), base: ok.reduce((a, p) => a + p.total_2026, 0) };
}
export const celPrevisao = (lista) => {
  const q = previsaoDe(lista);
  return q.n === 0 ? <><td className="n mudo">-</td><td className="n mudo">-</td></>
    : <><td className="n" title={`${q.n} de ${q.de} informaram`}>{fmt(q.valor)}</td><td className="n" title={`${q.n} de ${q.de} informaram`}>{pct(q.valor, q.base)}</td></>;
};

export function Passos({ itens, ativo, onMudar }) {
  return (
    <div className="passos" role="tablist">
      {itens.map(([k, t], i) => (
        <button key={k} role="tab" aria-selected={ativo === k} className={ativo === k ? "on" : ""} onClick={() => onMudar(k)}>
          <span className="n">{i + 1}</span>{t}
        </button>))}
    </div>
  );
}

export function Selo({ ano }) {
  return <span className={"selo " + (ano === 2026 ? "s26" : "s27")}>{ano === 2026 ? "Passado 2026" : "Plano 2027"}</span>;
}

export function Celula({ valor, onSalvar, travada }) {
  const [txt, setTxt] = useState(null);
  if (travada) return <span className="n cel-fixa" title={valor ? fmtN(valor) : ""}>{fmtI(valor)}</span>;
  const mostra = txt ?? fmtI(valor);
  const fim = () => {
    if (txt === null) return;
    const n = lerNumero(txt);
    setTxt(null);
    if (!Number.isNaN(n) && Math.abs(n - valor) > 0.004) onSalvar(Math.max(0, Math.round(n * 100) / 100));
  };
  return <input className="cel" inputMode="decimal" value={mostra} onFocus={(e) => { setTxt(valor ? String(valor).replace(".", ",") : ""); e.target.select(); }}
    onChange={(e) => setTxt(e.target.value)} title={valor ? fmtN(valor) : ""} onBlur={fim}
    onKeyDown={(e) => {
      if (e.key === "Escape") { setTxt(null); e.target.blur(); }
      if (e.key === "Enter") {      // grava e desce para a mesma coluna da linha de baixo
        const el = e.target, col = el.closest("td")?.cellIndex;
        const todas = [...(el.closest("table")?.querySelectorAll("input.cel") || [])].filter((x) => x.closest("td")?.cellIndex === col);
        const prox = todas[todas.indexOf(el) + 1];
        el.blur();
        if (prox) setTimeout(() => prox.focus(), 0);
      }
    }} />;
}

const svg = (children) => <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{children}</svg>;
export const Lapis = () => svg(<><path d="M12 20h9" /><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" /></>);
export const Lixeira = () => svg(<><path d="M3 6h18" /><path d="M8 6V4h8v2" /><path d="M19 6l-1 14H6L5 6" /><path d="M10 11v6M14 11v6" /></>);
export const Mais = () => svg(<><path d="M12 5v14M5 12h14" /></>);
export const Transferir = () => svg(<><path d="M4 8h14" /><path d="M14 4l4 4-4 4" /><path d="M20 16H6" /><path d="M10 12l-4 4 4 4" /></>);
export const Desfazer = () => svg(<><path d="M3 7v6h6" /><path d="M21 17a9 9 0 0 0-15-6.7L3 13" /></>);

/** Botão de ícone com dica (title) e rótulo acessível. tom: "perigo" deixa vermelho. */
export function BotaoIcone({ icone, dica, tom, onClick, desligado }) {
  return <button type="button" className={"icone" + (tom ? " " + tom : "")} title={dica} aria-label={dica} disabled={desligado} onClick={onClick}>{icone}</button>;
}

/** Escolha da tarefa do orçamento que recebe o valor (Eventos e Headcount). Sugere sozinha quando só uma combina. */
export function TarefaOrc({ dados, orcamento, edt, tarefa, onChange, rotulo, ajuda, opcional, semSugestao }) {
  const info = dados.tarefas?.[orcamento];
  const lista = info?.lista || [];
  useEffect(() => { if (!semSugestao && orcamento && !edt && !tarefa && info?.sugestao) onChange(info.sugestao.edt, info.sugestao.tarefa); }, [orcamento]); // eslint-disable-line
  const valor = edt || tarefa ? JSON.stringify([edt, tarefa]) : "";
  return (
    <label><span>{rotulo || "Tarefa do orçamento que recebe o valor"} {!opcional && <span className="obrig" title="Informação obrigatória">*</span>}</span>
      <select value={valor} disabled={!orcamento} onChange={(e) => { const [a, b] = e.target.value ? JSON.parse(e.target.value) : ["", ""]; onChange(a, b); }}>
        <option value="">{orcamento ? (opcional ? "Tarefa padrão (criada no projeto)" : "Selecione…") : "Escolha o projeto primeiro"}</option>
        {lista.map((t) => <option key={t.edt + t.tarefa} value={JSON.stringify([t.edt, t.tarefa])}>{t.edt} | {t.tarefa}</option>)}
      </select>
      <small className="mudo">{ajuda || "O valor entra no orçamento 2027 do projeto, nesta tarefa, como linha bloqueada."}</small>
    </label>
  );
}

export const FINALIDADES = [["caixa", "Fluxo de caixa"], ["headcount", "Headcount"], ["sustentacao", "Sustentação"], ["investimento", "Investimento"], ["crescimento", "Crescimento ou projeto"], ["capacitacao", "Capacitação e eventos"], ["gestao", "Gestão da área"]];
export const nomeFinalidade = (k) => (FINALIDADES.find(([v]) => v === k) || FINALIDADES[0])[1];
export const classeFinalidade = (k) => (k === "headcount" ? "hc" : k === "caixa" || !k ? "cx" : "nat");


/** Filtro por gerência, igual em todas as páginas. `opcoes`: nomes das gerências. */
export function FiltroGerencia({ valor, onChange, opcoes, largura = 250 }) {
  const lista = [...new Set(opcoes.filter(Boolean))].sort((a, b) => (a === "Diretoria Adjunta" ? -1 : b === "Diretoria Adjunta" ? 1 : a.localeCompare(b, "pt-BR")));
  return (
    <select style={{ width: largura }} value={valor} onChange={(e) => onChange(e.target.value)} aria-label="Filtrar por gerência" className={valor ? "filtro-ativo" : ""}>
      <option value="">Todas as gerências</option>{lista.map((g) => <option key={g} value={g}>{g}</option>)}
    </select>
  );
}

/** O item entra no filtro? `ger_filtro` é a lista de gerências do item (a do projeto, quando o item não informa). */
export const nasGer = (item, g) => !g || (item.ger_filtro || (item.gerencia ? [item.gerencia] : [])).includes(g);

/** Escolha de uma ou mais gerências (caixas de marcação). */
export function GerenciasCheck({ valor, onChange, opcoes }) {
  const marca = (g) => onChange(valor.includes(g) ? valor.filter((x) => x !== g) : [...valor, g]);
  return (
    <div className="gerencias-check">{opcoes.map((g) => (
      <label key={g} className="ent-check"><input type="checkbox" checked={valor.includes(g)} onChange={() => marca(g)} /> {g}</label>))}</div>
  );
}
