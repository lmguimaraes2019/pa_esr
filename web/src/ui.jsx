import React, { useState } from "react";
import { fmt, fmtN, lerNumero } from "./api.js";

export function Kpi({ rotulo, valor, sub, tom }) {
  return <div className={"kpi " + (tom || "")}><span>{rotulo}</span><strong>{valor}</strong>{sub && <small>{sub}</small>}</div>;
}

export function Delta({ de, para, pct = false, altaBoa = false }) {
  const d = para - de;
  if (Math.abs(d) < 0.005) return <span className="mudo">igual</span>;
  return <span className={(d > 0) !== altaBoa ? "up" : "down"}>{d > 0 ? "+" : ""}{fmt(d)}{pct && de ? ` (${((d / de) * 100).toFixed(1).replace(".", ",")}%)` : ""}</span>;
}

export const pct = (a, b) => (b > 0 ? ((a / b) * 100).toFixed(0) + "%" : "-");

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
  if (travada) return <span className="n" style={{ padding: "5px 6px", display: "block", width: 106 }}>{valor ? fmtN(valor) : ""}</span>;
  const mostra = txt ?? (valor ? fmtN(valor) : "");
  const fim = () => {
    if (txt === null) return;
    const n = lerNumero(txt);
    setTxt(null);
    if (!Number.isNaN(n) && Math.abs(n - valor) > 0.004) onSalvar(Math.max(0, Math.round(n * 100) / 100));
  };
  return <input className="cel" inputMode="decimal" value={mostra} onFocus={(e) => { setTxt(valor ? String(valor).replace(".", ",") : ""); e.target.select(); }}
    onChange={(e) => setTxt(e.target.value)} onBlur={fim} onKeyDown={(e) => { if (e.key === "Enter") e.target.blur(); if (e.key === "Escape") { setTxt(null); e.target.blur(); } }} />;
}

const svg = (children) => <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{children}</svg>;
export const Lapis = () => svg(<><path d="M12 20h9" /><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" /></>);
export const Lixeira = () => svg(<><path d="M3 6h18" /><path d="M8 6V4h8v2" /><path d="M19 6l-1 14H6L5 6" /><path d="M10 11v6M14 11v6" /></>);
export const Desfazer = () => svg(<><path d="M3 7v6h6" /><path d="M21 17a9 9 0 0 0-15-6.7L3 13" /></>);

/** Botão de ícone com dica (title) e rótulo acessível. tom: "perigo" deixa vermelho. */
export function BotaoIcone({ icone, dica, tom, onClick, desligado }) {
  return <button type="button" className={"icone" + (tom ? " " + tom : "")} title={dica} aria-label={dica} disabled={desligado} onClick={onClick}>{icone}</button>;
}
