// mesmas fórmulas da planilha CUSTO_PESSOAL (colunas K a Y) e de app/pessoal.py
export function custoMensal(j, p) {
  const encargos = j + (j * (24.5 + p.rat)) / 100 + (j * p.fgts) / 100 + (j * p.pis) / 100;
  const beneficios = p.vr_dia * p.vr_dias + p.vr_extra + p.vt + p.plano_saude + (j * p.seguro_vida) / 100 + p.internet;
  const abono = (j / 30 * 10) / 12;
  const provisoes = abono + (j / 12 + abono) / 3 + j / 12;
  const mensal = encargos + beneficios + provisoes;
  return { encargos, beneficios, provisoes, mensal, anual: mensal * 12 };
}
