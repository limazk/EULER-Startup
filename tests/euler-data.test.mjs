import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { parseCSV, toCSV, validateTables, validatePeriods } from '../assets/euler-demo-data.mjs';
const schema = JSON.parse(readFileSync(new URL('../assets/euler-schema.json', import.meta.url)));

test('CSV preserves quoted separators, multiline observations, decimal commas and blank cells', () => {
  const rows = [{a:'0,345',b:'linha 1\nlinha 2; "observação"',c:''}];
  assert.deepEqual(parseCSV(toCSV(['a','b','c'],rows)).rows,rows);
  assert.equal(parseCSV('a,b\n0.345,"texto, com vírgula"').rows[0].a,'0.345');
});
test('Malformed CSV is rejected without silently shifting columns', () => {
  for(const text of ['a,b\n1','a,a\n1,2','a,b\n"incompleto,2','a,b\n"x"y,2']) assert.throws(()=>parseCSV(text));
});
test('Both original examples satisfy form validation across all five schemas', () => {
  for(const name of ['complete','limited']) {
    const rows=JSON.parse(readFileSync(new URL(`../assets/euler-example-${name}.json`,import.meta.url)));
    assert.deepEqual(validateTables(rows,schema),[]);
  }
  assert.equal(Object.values(schema).reduce((n,t)=>n+t.columns.length,0),78);
});
test('Missing required identifiers and invalid numbers map to the field and row', () => {
  const errors=validateTables({diario:[{caldeira_id:'',instante_observado:'2026-08-01T08:00:00-03:00',t_gases_c:'abc'}]},schema);
  assert.deepEqual(errors.map(e=>e.field),['caldeira_id','t_gases_c']);
  assert(errors.every(e=>e.table==='diario'&&e.row===0));
});
test('Zero and absent optional numbers are distinct; both are accepted as input', () => {
  assert.deepEqual(validateTables({instrumentos:[{instrumento_id:'I1',tipo:'termopar',unidade:'C',resolucao:'0',incerteza_declarada:''}]},schema),[]);
});
test('Dates must be valid, increasing and non-overlapping; adjacent intervals are allowed', () => {
  assert.equal(validatePeriods(['2026-08-01','2026-08-02'],['2026-08-02','2026-08-03']),'');
  assert(validatePeriods(['',''],['','']));
  assert(validatePeriods(['2026-08-01','2026-08-03'],['2026-08-02','2026-08-04']));
  assert(validatePeriods(['2026-08-03','2026-08-01'],['2026-08-04','2026-08-05']));
});
