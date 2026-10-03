/** Recorte didático do Euler. Massas em kg; umidade em fração de base úmida. */
export const REFERENCE = Object.freeze({ fuelKg: 100000, steamKg: 400000, moisture: 0.4, dryPci: 18 });

/** E5, euler/combustivel.py::pci_umido. PCI em MJ/kg, vaporização a 25 °C. */
export function wetPci(dryPci, moisture) {
  if (!Number.isFinite(dryPci) || dryPci <= 0 || !Number.isFinite(moisture) || moisture < 0 || moisture >= 1) return null;
  const pci = (1 - moisture) * dryPci - 2.442 * moisture;
  return pci > 0 ? pci : null;
}

/** E15: massa de combustível / massa de vapor, exibida em kg/t de vapor.
 * Não reproduz detectabilidade, incerteza, IF97 ou investigação multivariada.
 * Efeito teórico do PCI: mesma energia útil e eficiência entre períodos.
 */
export function investigate({ fuelKg, steamKg, moisture = null }) {
  if (!Number.isFinite(fuelKg) || fuelKg <= 0 || !Number.isFinite(steamKg) || steamKg <= 0) {
    return { available: false, specific: null, changePct: null, pci: null, moistureEffectPct: null };
  }
  const specific = fuelKg / steamKg * 1000;
  const referenceSpecific = REFERENCE.fuelKg / REFERENCE.steamKg * 1000;
  const pci = wetPci(REFERENCE.dryPci, moisture);
  return {
    available: true,
    specific,
    changePct: (specific / referenceSpecific - 1) * 100,
    pci,
    moistureEffectPct: pci === null ? null : (wetPci(REFERENCE.dryPci, REFERENCE.moisture) / pci - 1) * 100,
  };
}
