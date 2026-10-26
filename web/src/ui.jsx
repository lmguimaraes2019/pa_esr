import React from "react";
import { fmt } from "./api.js";

export function Kpi({ rotulo, valor, sub, tom }) {
  return <div className={"kpi " + (tom || "")}><span>{rotulo}</span><strong>{valor}</strong>{sub && <small>{sub}</small>}</div>;
}

export function Delta({ de, para, pct = false }) {
  const d = para - de;
  if (Math.abs(d) < 0.005) return <span className="mudo">igual</span>;
  return <span className={d > 0 ? "up" : "down"}>{d > 0 ? "+" : ""}{fmt(d)}{pct && de ? ` (${((d / de) * 100).toFixed(1).replace(".", ",")}%)` : ""}</span>;
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
