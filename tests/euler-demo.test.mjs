import test from 'node:test';
import assert from 'node:assert/strict';
import { investigate, wetPci } from '../assets/euler-demo-core.mjs';

const close = (actual, expected) => assert.ok(Math.abs(actual - expected) < 1e-10, `${actual} != ${expected}`);
test('E5: PCI seco, referência úmida e amostra do exemplo', () => {
  close(wetPci(18, 0), 18);
  close(wetPci(18, 0.4), 9.8232);
  close(wetPci(18, 0.45), 8.8011);
});
test('E5: ausentes, não finitos, unidades erradas e energia não positiva bloqueiam', () => {
  for (const moisture of [null, undefined, NaN, Infinity, -0.1, 1, 40, 0.99]) assert.equal(wetPci(18, moisture), null);
  for (const pci of [null, undefined, NaN, Infinity, 0, -18]) assert.equal(wetPci(pci, 0.4), null);
});
test('Mesmo vapor com 11% mais combustível: 277,5 kg/t', () => {
  const result = investigate({ fuelKg: 111000, steamKg: 400000 });
  close(result.specific, 277.5);
  close(result.changePct, 11);
  assert.equal(result.pci, null);
  assert.equal(result.moistureEffectPct, null);
});
test('Produção e combustível +20%: indicador permanece igual', () => {
  const result = investigate({ fuelKg: 120000, steamKg: 480000 });
  close(result.specific, 250);
  close(result.changePct, 0);
});
test('Queda no consumo permanece negativa', () => {
  close(investigate({ fuelKg: 80000, steamKg: 400000 }).changePct, -20);
});
test('Ausência ou massa inválida bloqueia e não produz zero ou infinito', () => {
  for (const value of [null, undefined, NaN, Infinity, 0, -1]) {
    for (const input of [{ fuelKg: 111000, steamKg: value }, { fuelKg: value, steamKg: 400000 }]) {
      const result = investigate(input);
      assert.equal(result.available, false);
      assert.equal(result.changePct, null);
      assert.equal(result.specific, null);
    }
  }
});
test('Cenário de umidade é separado da variação observada', () => {
  const result = investigate({ fuelKg: 111000, steamKg: 400000, moisture: 0.45 });
  close(result.changePct, 11);
  close(result.moistureEffectPct, (9.8232 / 8.8011 - 1) * 100);
  close(investigate({ fuelKg: 111000, steamKg: 400000, moisture: 0.4 }).moistureEffectPct, 0);
});
