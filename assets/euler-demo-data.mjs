/** CSV de entrada, sem coerção silenciosa. Separadores , e ;, aspas e linhas internas. */
export function parseCSV(text) {
  text = text.replace(/^\uFEFF/, '');
  const first = text.split(/\r?\n/, 1)[0];
  const delimiter = first.includes(';') ? ';' : ',';
  const rows = []; let row = [], cell = '', quoted = false, endedQuote = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quoted) {
      if (c === '"' && text[i + 1] === '"') { cell += '"'; i++; }
      else if (c === '"') { quoted = false; endedQuote = true; }
      else cell += c;
    } else if (c === '"' && !cell && !endedQuote) quoted = true;
    else if (c === delimiter) { row.push(cell); cell = ''; endedQuote = false; }
    else if (c === '\n' || c === '\r') {
      if (c === '\r' && text[i + 1] === '\n') i++;
      row.push(cell); if (row.some(v => v !== '')) rows.push(row);
      row = []; cell = ''; endedQuote = false;
    } else if (endedQuote && c.trim()) throw new Error('Confira as aspas do CSV. Há texto após o fechamento de um campo.');
    else cell += c;
  }
  if (quoted) throw new Error('O CSV tem um campo com aspas não fechadas.');
  row.push(cell); if (row.some(v => v !== '')) rows.push(row);
  if (!rows.length) throw new Error('O arquivo está vazio.');
  const headers = rows.shift().map(h => h.trim());
  if (headers.some(h => !h) || new Set(headers).size !== headers.length) throw new Error('O cabeçalho contém colunas vazias ou repetidas.');
  if (rows.some(r => r.length !== headers.length)) throw new Error('Há linhas com quantidade de colunas diferente do cabeçalho.');
  return { headers, rows: rows.map(r => Object.fromEntries(headers.map((h, i) => [h, r[i]]))) };
}

export function toCSV(headers, rows = []) {
  const escape = v => `"${String(v ?? '').replaceAll('"', '""')}"`;
  return '\uFEFF' + [headers, ...rows.map(r => headers.map(h => r[h] ?? ''))].map(r => r.map(escape).join(';')).join('\r\n');
}

export function validateTables(tables, schema) {
  const errors = [];
  for (const [name, rows] of Object.entries(tables)) {
    rows.forEach((row, index) => {
      for (const col of schema[name].columns) {
        const raw = String(row[col.nome] ?? '').trim();
        let message = '';
        if (!raw && col.obrigatoria) message = 'Preencha este campo obrigatório.';
        if (raw && col.tipo === 'numero' && !Number.isFinite(Number(raw.replace(',', '.')))) message = 'Informe um número válido, sem separador de milhar.';
        if (raw && col.tipo === 'categoria' && !col.categorias.includes(raw)) message = 'Escolha uma das opções disponíveis.';
        if (message) errors.push({ table: name, row: index, field: col.nome, message });
      }
    });
  }
  return errors;
}

export function validatePeriods(reference, comparison) {
  const dates = [...reference, ...comparison].map(v => new Date(v).getTime());
  if (dates.some(v => !Number.isFinite(v))) return 'Preencha as quatro datas e horários.';
  if (dates[0] >= dates[1] || dates[2] >= dates[3]) return 'O início de cada período deve ser anterior ao fim.';
  if (!(dates[1] <= dates[2] || dates[3] <= dates[0])) return 'Os períodos não podem se sobrepor.';
  return '';
}
