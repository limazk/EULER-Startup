"""Integration of the original engine and the public preview boundary (synthetic data only)."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'server'))
from app import analyze, validate, InputError


def example(name='complete'):
    return {
        'tables': json.loads((ROOT / f'assets/euler-example-{name}.json').read_text()),
        'altitude': 1000,
        'reference': ['2026-08-03T07:30:00-03:00', '2026-08-31T07:30:00-03:00'],
        'comparison': ['2026-08-31T07:30:00-03:00', '2026-09-14T07:30:00-03:00'],
    }


class PreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.complete = analyze(example())
        cls.limited = analyze(example('limited'))

    def test_complete_matches_original_demo(self):
        result = self.complete
        self.assertEqual(result['status'], 'supported')
        self.assertAlmostEqual(result['consumption']['referencia'], 0.3206748415232244)
        self.assertAlmostEqual(result['consumption']['comparacao'], 0.35319356530921114)
        self.assertEqual(len(result['hypotheses']), 2)
        self.assertTrue(any('úmido' in h for h in result['hypotheses']))

    def test_same_measurements_missing_instrument_uncertainty(self):
        self.assertEqual(self.limited['consumption'], self.complete['consumption'])
        self.assertEqual(self.limited['status'], 'limited')
        self.assertIn('incerteza', self.limited['reason'])
        self.assertIn('umidade', self.limited['reason'])

    def test_decimal_comma_and_point_are_equivalent(self):
        payload = example()
        for row in payload['tables']['amostras']:
            row['umidade_bu_frac'] = row['umidade_bu_frac'].replace('.', ',')
        result = analyze(payload)
        self.assertEqual(result['status'], self.complete['status'])
        self.assertEqual(result['hypotheses'], self.complete['hypotheses'])
        self.assertEqual(result['consumption'], self.complete['consumption'])

    def test_actual_input_changes_result(self):
        payload = example()
        for row in payload['tables']['combustivel']:
            if row['tipo'] == 'recebimento' and '2026-08-31' <= row['data'] < '2026-09-14':
                row['massa_kg'] = str(float(row['massa_kg']) * 1.2)
        result = analyze(payload)
        self.assertGreater(result['consumption']['comparacao'], self.complete['consumption']['comparacao'])

    def test_missing_vapor_is_not_zero(self):
        payload = example()
        for row in payload['tables']['diario']:
            row['totalizador_vapor_t'] = ''
        result = analyze(payload)
        self.assertEqual(result['status'], 'insufficient')
        self.assertIsNone(result['consumption']['comparacao'])
        self.assertTrue(result['reason'])

    def test_only_preview_is_returned_and_limits_are_kept(self):
        for result in [self.complete, self.limited]:
            for private in ['hipoteses', 'periodos', 'valor_em_jogo', 'resumo', 'fechamento']:
                self.assertNotIn(private, result)
            self.assertTrue(result['limits'])
            self.assertTrue(result['warnings'])
            self.assertTrue(result['criteria'])
        self.assertTrue(any('saturado seco' in item for item in self.complete['limits']))

    def test_mixed_boilers_and_overlap_are_rejected(self):
        payload = example()
        payload['tables']['diario'][0]['caldeira_id'] = 'OUTRA'
        with self.assertRaises(InputError): validate(payload)
        payload = example()
        payload['comparison'][0] = '2026-08-10T07:30:00-03:00'
        with self.assertRaises(InputError): validate(payload)

    def test_malformed_and_nonfinite_inputs_are_rejected(self):
        for payload in [None, {}, {'tables': []}]:
            with self.assertRaises(InputError): validate(payload)
        payload = example(); payload['altitude'] = float('nan')
        with self.assertRaises(InputError): validate(payload)
        payload = example(); payload['tables']['diario'][0]['t_gases_c'] = 'Infinity'
        with self.assertRaises(InputError): analyze(payload)


if __name__ == '__main__': unittest.main()
