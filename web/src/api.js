export class ApiError extends Error { constructor(msg, status) { super(msg); this.status = status; } }

export async function api(path, { method = "GET", body } = {}) {
  const r = await fetch("/api" + path, {
    method, credentials: "same-origin",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) {
    let msg = "Erro inesperado.";
    try {
      const j = await r.json();
      msg = typeof j.detail === "string" ? j.detail : "Verifique os valores informados.";
    } catch { /* corpo vazio */ }
    throw new ApiError(msg, r.status);
  }
  return r.json();
}

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const num = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
export const fmt = (v) => brl.format(v || 0);
export const fmtN = (v) => num.format(v || 0);
export const mi = (v) => (v / 1e6).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " mi";

// aceita "1.234,56", "1234,56" ou "1234.56"
export function lerNumero(txt) {
  const t = String(txt).trim().replace(/\s/g, "");
  if (t === "") return 0;
  const n = t.includes(",") ? Number(t.replace(/\./g, "").replace(",", ".")) : Number(t);
  return Number.isFinite(n) ? n : NaN;
}
export const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
