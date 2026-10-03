import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

// Exercise asynchronous component state without requiring a browser or network.
let Component;
globalThis.HTMLElement = class {};
globalThis.customElements = { get: () => undefined, define: (_, value) => { Component = value; } };
globalThis.document = { addEventListener() {} };
await import('../assets/euler-demo.js');
const schema = JSON.parse(readFileSync(new URL('../assets/euler-schema.json', import.meta.url)));
const empty = () => Object.fromEntries(Object.keys(schema).map(key => [key, []]));
function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
function demo() {
  const d = new Component();
  Object.assign(d, {
    tables: empty(), schema, table: 'diario', row: 0, requestId: 0,
    shadowRoot: { querySelectorAll: () => [] },
    render() {}, announce() {}, message(text) { this.error = text; },
    $: () => ({ textContent: '' }),
  });
  return d;
}
function startImport(d, pending) {
  const input = { id: 'csv', value: 'file.csv', files: [{ size: 50, arrayBuffer: () => pending.promise }] };
  return { input, done: d.change({ target: input }) };
}
const csv = name => new TextEncoder().encode(`caldeira_id\n${name}`).buffer;

test('CSV remains in its original group when the visitor changes tabs', async () => {
  const d = demo(), pending = deferred();
  const { done, input } = startImport(d, pending);
  d.table = 'instrumentos';
  pending.resolve(csv('CALD-01'));
  await done;
  assert.deepEqual(d.tables.diario, [{ caldeira_id: 'CALD-01' }]);
  assert.deepEqual(d.tables.instrumentos, []);
  assert.equal(d.table, 'instrumentos');
  assert.equal(input.value, '');
});

test('Resetting or closing discards a pending CSV import', async () => {
  for (const action of ['reset', 'close']) {
    const d = demo(), pending = deferred();
    const { done, input } = startImport(d, pending);
    if (action === 'reset') d.tables = empty();
    else d.requestId++;
    pending.resolve(csv('OLD'));
    await done;
    assert.deepEqual(d.tables, empty());
    assert.equal(input.value, '');
  }
});

test('An older CSV read cannot overwrite a newer selection', async () => {
  const d = demo(), first = deferred(), second = deferred();
  const old = startImport(d, first), latest = startImport(d, second);
  second.resolve(csv('NEW')); await latest.done;
  first.resolve(csv('OLD')); await old.done;
  assert.deepEqual(d.tables.diario, [{ caldeira_id: 'NEW' }]);
});

test('Example completion or failure after closing cannot replace new input', async t => {
  for (const fail of [false, true]) {
    const d = demo(), pending = deferred();
    t.mock.method(globalThis, 'fetch', async () => ({ ok: true, json: () => pending.promise }));
    const done = d.loadExample('complete');
    d.requestId++; d.busy = false;
    const own = empty(); own.diario.push({ caldeira_id: 'MY-DATA' });
    d.tables = own;
    if (fail) pending.reject(new Error('offline'));
    else pending.resolve(empty());
    await done;
    assert.equal(d.tables, own);
    assert.equal(d.error, '');
    assert.equal(d.busy, false);
    t.mock.restoreAll();
  }
});

test('Scene layers follow scrolling and remain hidden while the modal is open', () => {
  const classes = new Set();
  document.body = { classList: { toggle(name, active) { active ? classes.add(name) : classes.delete(name); } } };
  globalThis.innerHeight = 900;
  const d = demo();
  d.isConnected = true;
  d.dialog = { open: false };
  let rect = { top: 1000, bottom: 3000 };
  d.getBoundingClientRect = () => rect;
  d.syncScene();
  assert.equal(classes.size, 0);
  // A tall mobile section can move without changing its intersection ratio.
  rect = { top: -300, bottom: 1700 };
  d.syncScene();
  assert(classes.has('euler-demo-active'));
  rect = { top: -1900, bottom: 100 };
  d.dialog.open = true;
  d.syncScene();
  assert(!classes.has('euler-demo-active'));
  assert(classes.has('euler-demo-open'));
  d.dialog.open = false;
  d.syncScene();
  assert.equal(classes.size, 0);
  d.dialog.open = true;
  d.isConnected = false;
  d.syncScene();
  assert.equal(classes.size, 0);
});
