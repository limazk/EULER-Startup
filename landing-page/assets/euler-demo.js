import { parseCSV, toCSV, validateTables, validatePeriods } from './euler-demo-data.mjs';

const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num = (value, digits = 1) => Number(value).toLocaleString('pt-BR', { minimumFractionDigits: digits, maximumFractionDigits: digits });
const signed = value => `${value > 0 ? '+' : ''}${num(value)}%`;
const EMPTY = () => ({ diario: [], combustivel: [], amostras: [], eventos: [], instrumentos: [] });
const NAMES = { diario: 'Operação', combustivel: 'Combustível', amostras: 'Amostras', eventos: 'Eventos', instrumentos: 'Instrumentos' };
function exitSceneExploration() {
  // Use the scene's controls so its camera and scroll locks are also released.
  if (document.body.classList.contains('is-focus')) document.querySelector('.eq-panel [data-back]')?.click();
  if (document.body.classList.contains('is-explore')) document.querySelector('.explore-bar [data-exit]')?.click();
}
const CORE = {
  diario: ['caldeira_id','instante_observado','regime','totalizador_vapor_t','p_vapor_bar_man','estado_vapor','t_agua_alim_c','t_gases_c','ponto_gases_id','o2_seco_pct','instrumento_o2_id','t_ar_c'],
  combustivel: ['data','tipo','fornecedor_id','lote_id','massa_kg','volume_m3','densidade_kg_m3','origem_densidade','preco_brl','origem_dado'],
  amostras: ['amostra_id','lote_id','data','umidade_bu_frac','pci_seco_mj_kg','metodo'],
  eventos: ['instante','tipo','descricao','autorizado_por','origem_dado'],
  instrumentos: ['instrumento_id','tipo','ponto','unidade','resolucao','incerteza_declarada','incerteza_tipo','incerteza_k','ultima_verificacao','observacao'],
};

class EulerDemo extends HTMLElement {
  connectedCallback() {
    if (this.shadowRoot) return;
    this.tables = EMPTY(); this.step = 0; this.table = 'diario'; this.row = 0;
    this.source = ''; this.altitude = ''; this.periods = ['', '', '', '']; this.errors = [];
    const root = this.attachShadow({ mode: 'open' });
    root.innerHTML = `
      <link rel="stylesheet" href="${new URL('./euler-demo.css', import.meta.url)}">
      <div class="wrap">
        <p class="eyebrow">EULER na prática</p>
        <div class="teaser"><div>
          <h2>Seus registros.<br><span>O começo da resposta.</span></h2>
          <p class="intro">Explore uma investigação com os dados da sua caldeira ou experimente um caso simulado. Veja o que mudou e qual é o próximo passo.</p>
          <div class="actions"><button class="btn primary" data-action="open">Experimentar a EULER</button></div>
          <p class="note">Sem cadastro. Você recebe uma prévia; a análise detalhada faz parte da experiência completa.</p>
        </div><div class="sample" aria-label="Etapas da investigação">
          <div class="bar"><span class="brand mono">EULER / INVESTIGAÇÃO</span><span class="tag">PRÉVIA INTERATIVA</span></div>
          <div class="sample-body">
            <div class="sample-line"><b>01</b><div><strong>Reúna os registros</strong><p>Operação, combustível, amostras, eventos e instrumentos.</p></div></div>
            <div class="sample-line"><b>02</b><div><strong>Compare dois períodos</strong><p>Dados próprios ou exemplos sintéticos, sempre editáveis.</p></div></div>
            <div class="sample-line"><b>03</b><div><strong>Conheça a próxima verificação</strong><p>Uma prévia útil, com as limitações da investigação à vista.</p></div></div>
          </div>
        </div></div>
        <p class="fine teaser-foot">A EULER apoia a investigação. Não emite comandos operacionais nem substitui os procedimentos da instalação ou a avaliação do responsável técnico.</p>
      </div>
      <dialog aria-labelledby="demo-title">
        <div class="dialog-head"><div><span class="brand mono">EULER</span><p id="demo-title">Sua primeira investigação</p></div><button class="close" data-action="close" aria-label="Fechar demonstração">×</button></div>
        <ol class="steps" aria-label="Progresso"><li><b>1</b>Começar</li><li><b>2</b>Registros</li><li><b>3</b>Revisar</li><li><b>4</b>Prévia</li></ol>
        <div class="viewport"><div id="message" role="alert" hidden></div><div id="content"></div></div>
        <div class="dialog-foot" id="footer"></div>
      </dialog><span class="sr-only" role="status" aria-live="polite" id="announcement"></span>`;
    this.$ = id => root.getElementById(id);
    this.dialog = root.querySelector('dialog');
    this.dialog.addEventListener('wheel', event => event.stopPropagation(), { passive: true });
    this.dialog.addEventListener('touchmove', event => event.stopPropagation(), { passive: true });
    this.dialog.addEventListener('keydown', event => event.stopPropagation());
    root.addEventListener('click', event => this.click(event));
    root.addEventListener('input', event => this.input(event));
    root.addEventListener('change', event => this.change(event));
    root.addEventListener('submit', event => event.preventDefault());
    this.dialog.addEventListener('close', () => {
      this.requestId = (this.requestId || 0) + 1;
      this.controller?.abort(); this.busy = false;
      document.body.style.overflow = this.previousOverflow ?? '';
      this.syncScene();
      root.querySelector('[data-action="open"]').focus({ preventScroll: true });
    });
    // Keep pointer effects from the existing WebGL scene out of this component.
    this.addEventListener('pointerdown', event => event.stopPropagation());
    this.addEventListener('pointermove', event => event.stopPropagation());
    this.scheduleScene = () => {
      if (this.sceneFrame) return;
      this.sceneFrame = requestAnimationFrame(() => { this.sceneFrame = 0; this.syncScene(); });
    };
    window.addEventListener('scroll', this.scheduleScene, { passive: true });
    window.addEventListener('resize', this.scheduleScene);
    this.observer = new ResizeObserver(() => {
      this.scheduleScene();
      window.dispatchEvent(new Event('resize'));
    });
    this.observer.observe(this);
    this.syncScene();
  }
  syncScene() {
    const rect = this.getBoundingClientRect();
    document.body.classList.toggle('euler-demo-active', this.isConnected && rect.top < innerHeight * .65 && rect.bottom > innerHeight * .35);
    document.body.classList.toggle('euler-demo-open', this.isConnected && this.dialog.open);
  }
  disconnectedCallback() {
    this.observer?.disconnect();
    window.removeEventListener('scroll', this.scheduleScene);
    window.removeEventListener('resize', this.scheduleScene);
    cancelAnimationFrame(this.sceneFrame);
    document.body.classList.remove('euler-demo-active', 'euler-demo-open');
    this.controller?.abort();
    if (this.dialog?.open) this.dialog.close();
  }
  message(text) {
    this.$('message').hidden = !text;
    this.$('message').className = 'notice error';
    this.$('message').textContent = text;
    if (text) this.shadowRoot.querySelector('.viewport').scrollTop = 0;
  }
  announce(text) { this.$('announcement').textContent = text; }
  async open() {
    exitSceneExploration();
    this.previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    this.dialog.showModal();
    this.syncScene();
    if (!this.schema) {
      this.$('content').innerHTML = '<div class="busy"><p>Preparando os registros…</p></div>';
      try {
        const response = await fetch(new URL('./euler-schema.json', import.meta.url));
        if (!response.ok) throw new Error();
        this.schema = await response.json();
      } catch { this.message('Não foi possível carregar o formulário. Feche e tente novamente.'); return; }
    }
    this.render();
  }
  async click(event) {
    const button = event.target.closest('[data-action]');
    if (!button || button.disabled) return;
    const action = button.dataset.action;
    if (action === 'open') return this.open();
    if (action === 'close') return this.dialog.close();
    if (this.busy) return;
    if (action === 'own') {
      this.tables = EMPTY(); this.source = 'real'; this.periods = ['','','','']; this.altitude = ''; this.result = null; this.errors = []; this.step = 1; this.table = 'diario'; this.row = 0; return this.render();
    }
    if (action === 'complete' || action === 'limited') return this.loadExample(action);
    if (action === 'table') { this.table = button.dataset.table; this.row = 0; this.errors = []; return this.render(false); }
    if (action === 'add' || action === 'duplicate') {
      const row = action === 'duplicate' ? { ...this.tables[this.table][this.row] } : {};
      if (this.schema[this.table].columns.some(c => c.nome === 'origem_dado') && !row.origem_dado) row.origem_dado = this.source === 'real' ? 'real' : 'sintetico';
      this.tables[this.table].push(row); this.row = this.tables[this.table].length - 1; this.result = null; this.errors = [];
      this.render(false); this.$('fields')?.querySelector('input,select,textarea')?.focus(); return;
    }
    if (action === 'remove') { this.tables[this.table].splice(this.row,1); this.row = Math.max(0,this.row-1); this.result = null; this.errors = []; return this.render(false); }
    if (action === 'template') return this.download(toCSV(this.schema[this.table].columns.map(c=>c.nome)), `${this.table}.csv`);
    if (action === 'next') {
      if (!this.checkRecords()) return;
      this.step = 2; return this.render();
    }
    if (action === 'back' || action === 'edit') { this.step = 1; return this.render(); }
    if (action === 'analyze') return this.analyze();
    if (action === 'reset') {
      this.$('content').innerHTML = '<h2 class="pane-title" tabindex="-1">Reiniciar demonstração?</h2><p class="pane-lead">Isso apaga os registros preenchidos nesta sessão. Fechar a demonstração mantém o preenchimento enquanto esta página estiver aberta.</p><div class="actions"><button class="btn primary" data-action="reset-confirm">Apagar preenchimento</button><button class="btn" data-action="cancel-reset">Continuar preenchimento</button></div>';
      this.$('footer').innerHTML = ''; return;
    }
    if (action === 'cancel-reset') return this.render();
    if (action === 'reset-confirm') { this.tables = EMPTY(); this.step = 0; this.source = ''; this.result = null; this.errors = []; this.periods = ['','','','']; this.altitude = ''; return this.render(); }
    if (action === 'contact') {
      event.preventDefault(); this.dialog.close();
      document.querySelector('.topbar a[href="#proposta"]')?.click();
      setTimeout(()=>document.querySelector('#proposta input')?.focus({preventScroll:true}),600);
    }
  }
  async loadExample(name) {
    const requestId = this.requestId = (this.requestId || 0) + 1;
    this.busy = true; this.message('');
    this.shadowRoot.querySelectorAll('.choice').forEach(b => b.disabled = true);
    this.announce('Carregando exemplo sintético.');
    try {
      const response = await fetch(new URL(`./euler-example-${name}.json`, import.meta.url));
      if (!response.ok) throw new Error();
      const tables = await response.json();
      if (requestId !== this.requestId) return;
      this.tables = tables; this.source = 'sintetico'; this.altitude = '1000';
      this.periods = ['2026-08-03T07:30','2026-08-31T07:30','2026-08-31T07:30','2026-09-14T07:30'];
      this.result = null; this.errors = []; this.step = 1; this.table = 'diario'; this.row = 0;
      this.busy = false; this.render(); this.announce('Exemplo carregado. Todos os registros podem ser editados.');
    } catch {
      if (requestId !== this.requestId) return;
      this.busy = false; this.render(); this.message('Não foi possível carregar o exemplo. Tente novamente.');
    }
  }
  input(event) {
    const el = event.target;
    if (el.dataset.field) {
      this.tables[this.table][this.row][el.dataset.field] = el.value;
      this.result = null;
      if (el.getAttribute('aria-invalid') === 'true') { el.removeAttribute('aria-invalid'); this.shadowRoot.getElementById(`err-${el.dataset.field}`)?.remove(); }
    }
    if (el.id === 'altitude') { this.altitude = el.value; this.result = null; }
    if (el.dataset.period !== undefined) { this.periods[Number(el.dataset.period)] = el.value; this.result = null; }
  }
  async change(event) {
    const el = event.target;
    if (el.id === 'record') { this.row = Number(el.value); this.errors = []; this.render(false); this.$('record')?.focus(); }
    if (el.id === 'csv' && el.files[0]) {
      const file = el.files[0];
      const table = this.table, tables = this.tables, requestId = this.requestId;
      const importId = this.importId = (this.importId || 0) + 1;
      const current = () => tables === this.tables && requestId === this.requestId && importId === this.importId;
      try {
        if (file.size > 3_000_000) throw new Error('Use um CSV de até 3 MB.');
        const buffer = await file.arrayBuffer();
        if (!current()) return;
        const text = new TextDecoder('utf-8', { fatal: true }).decode(buffer);
        const csv = parseCSV(text);
        const allowed = this.schema[table].columns.map(c=>c.nome);
        const unknown = csv.headers.filter(h=>!allowed.includes(h));
        if (unknown.length) throw new Error(`Colunas não reconhecidas: ${unknown.join(', ')}. Use o modelo deste grupo, com as unidades indicadas.`);
        if (csv.rows.length + Object.values(this.tables).reduce((n, rows)=>n+rows.length,0) > 5000) throw new Error('A prévia aceita até 5.000 registros por análise.');
        if (!csv.rows.length) throw new Error('O arquivo contém apenas o cabeçalho. Adicione registros.');
        // Append explicitly: previously typed data is never silently replaced.
        const firstRow = tables[table].length;
        tables[table].push(...csv.rows); this.result = null; this.errors = [];
        if (this.table === table) this.row = firstRow;
        this.render(false); this.announce(`${csv.rows.length} registros adicionados em ${NAMES[table]}. Revise antes de analisar.`);
        if (this.table === table && this.$('import-status')) this.$('import-status').textContent = `${csv.rows.length} registros adicionados. O conteúdo anterior foi mantido.`;
      } catch (error) {
        if (current()) this.message(error instanceof TypeError ? 'Salve o CSV com codificação UTF-8 e tente novamente.' : error.message);
      } finally { el.value = ''; }
    }
  }
  download(content, name) {
    const url = URL.createObjectURL(new Blob([content], {type:'text/csv;charset=utf-8'}));
    const a = document.createElement('a'); a.href=url; a.download=name; a.click(); setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  checkRecords() {
    this.errors = validateTables(this.tables,this.schema);
    if (this.errors.length) {
      const first = this.errors[0]; this.step=1; this.table=first.table; this.row=first.row; this.render(false);
      this.message(`${this.errors.length} campo(s) precisam de revisão. ${NAMES[first.table]}, registro ${first.row+1}.`);
      const field = this.$(`f-${first.field}`); field?.closest('details')?.setAttribute('open',''); field?.focus(); return false;
    }
    if (!this.tables.diario.length) { this.message('Adicione pelo menos uma leitura ao diário de operação. Você pode começar por um exemplo simulado.'); return false; }
    return true;
  }
  field(col) {
    const value = this.tables[this.table][this.row][col.nome] ?? '';
    const error = this.errors.find(e=>e.table===this.table && e.row===this.row && e.field===col.nome);
    const id = `f-${col.nome}`;
    const attrs = `id="${id}" data-field="${col.nome}" aria-describedby="help-${col.nome}${error ? ` err-${col.nome}` : ''}" ${col.obrigatoria?'aria-required="true"':''} ${error?'aria-invalid="true"':''}`;
    let control;
    if (col.tipo === 'categoria' || col.tipo === 'booleano') {
      const options = col.tipo === 'booleano' ? ['true','false'] : col.categorias;
      const unknown = value && !options.includes(String(value)) ? `<option selected value="${escape(value)}">${escape(value)} (revisar)</option>` : '';
      control = `<select ${attrs}><option value="">${col.obrigatoria?'Selecione':'Não tenho esse dado'}</option>${unknown}${options.map(v=>`<option value="${escape(v)}" ${String(value)===v?'selected':''}>${escape(v==='true'?'Sim':v==='false'?'Não':v.replaceAll('_',' '))}</option>`).join('')}</select>`;
    } else if (['descricao','observacao','ocorrencia','producao'].includes(col.nome)) {
      control = `<textarea ${attrs} maxlength="2000">${escape(value)}</textarea>`;
    } else {
      control = `<input ${attrs} type="${col.tipo==='data'?'date':'text'}" ${col.tipo==='numero'?'inputmode="decimal"':''} maxlength="2000" value="${escape(value)}" placeholder="${escape(col.exemplo || (col.tipo==='numero'?'Não tenho esse dado':''))}" autocomplete="off">`;
    }
    const description = col.nome==='origem_dado' ? 'Indique se este registro é real, público ou sintético.' : col.descricao;
    return `<label class="field" for="${id}"><span>${escape(col.label)} <span class="optional">${col.obrigatoria?'*':col.unidade==='—'?'opcional':escape(col.unidade)}</span></span>${control}<small id="help-${col.nome}">${escape(description)}${col.obrigatoria&&col.unidade!=='—'?` Unidade: ${escape(col.unidade)}.`:''}</small>${error?`<small class="field-error" id="err-${col.nome}">${escape(error.message)}</small>`:''}</label>`;
  }
  editor() {
    const rows=this.tables[this.table], schema=this.schema[this.table];
    const primaryNames = [...CORE[this.table]];
    if (this.table === 'diario') primaryNames.push('t_vapor_c', 'titulo_vapor_frac');
    const primary=schema.columns.filter(c=>primaryNames.includes(c.nome));
    const other=schema.columns.filter(c=>!primaryNames.includes(c.nome));
    return `<h2 class="pane-title" tabindex="-1">Reúna os registros da caldeira.</h2>
      <p class="pane-lead">Preencha ou importe os dados disponíveis. Campos com * são obrigatórios em cada registro; deixe os demais vazios quando não houver medição.</p>
      <div class="editor-meta"><span class="tag ${this.source==='sintetico'?'accent':''}">${this.source==='sintetico'?'EXEMPLO SINTÉTICO · EDITÁVEL':'DADOS PRÓPRIOS'}</span><button class="text-btn" data-action="reset">Reiniciar demonstração</button></div>
      <div class="tabs" role="group" aria-label="Grupos de registros">${Object.entries(NAMES).map(([key,title])=>`<button data-action="table" data-table="${key}" aria-pressed="${key===this.table}">${title} <span class="mono">${this.tables[key].length}</span></button>`).join('')}</div>
      <div class="editor-meta"><div><h3>${escape(schema.title)}</h3><p class="help">${escape(schema.description)}</p></div><button class="text-btn" data-action="template">Baixar modelo CSV</button></div>
      <div class="toolbar">${rows.length?`<label class="field"><span>Registro em edição</span><select id="record" aria-label="Registro em edição">${rows.map((row,i)=>`<option value="${i}" ${i===this.row?'selected':''}>${i+1} / ${rows.length} · ${escape(row.instante_observado || row.data || row.instante || row.instrumento_id || 'Novo registro')}</option>`).join('')}</select></label>`:''}<button class="btn" data-action="add">Adicionar registro</button>${rows.length?'<button class="btn" data-action="duplicate">Duplicar</button>':''}</div>
      ${rows.length?`<form id="record-form" novalidate><div class="fields" id="fields">${primary.map(c=>this.field(c)).join('')}</div>${other.length?`<details class="details"><summary>Todos os campos complementares (${other.length})</summary><p class="help">Inclui medições adicionais e informações de rastreabilidade, conforme o contrato do software.</p><div class="fields">${other.map(c=>this.field(c)).join('')}</div></details>`:''}</form><button class="text-btn danger" data-action="remove">Remover este registro</button>`:`<div class="empty"><h3>Nenhum registro neste grupo</h3><p>${this.table==='diario'?'Adicione as leituras que você já possui.':'Preencha se tiver essas informações. A análise indicará os limites quando faltarem dados.'}</p><button class="btn" data-action="add">Adicionar primeiro registro</button></div>`}
      <details class="details"><summary>Importar registros de um CSV</summary><p>Use o modelo deste grupo, em UTF-8, com separador vírgula ou ponto e vírgula. Os registros serão adicionados aos existentes. Limite: 5.000 registros e 3 MB por análise.</p><label class="field"><span>Arquivo de ${escape(NAMES[this.table].toLowerCase())}</span><input id="csv" type="file" accept=".csv,text/csv"></label><p class="help" id="import-status" role="status"></p></details>`;
  }
  review() {
    return `<h2 class="pane-title" tabindex="-1">Escolha o que comparar.</h2><p class="pane-lead">Use períodos distintos da mesma caldeira. Para o balanço por estoques, escolha as datas e os horários das medições de estoque nas fronteiras de cada período.</p>
      <div class="review">${Object.entries(NAMES).map(([key,title])=>`<div><strong>${this.tables[key].length}</strong><span>${title}</span></div>`).join('')}</div>
      <div class="periods">${['Referência · como era','Comparação · como ficou'].map((title,i)=>`<fieldset><legend>${title}</legend>${['Início','Fim'].map((label,j)=>`<label class="field"><span>${label}</span><input type="datetime-local" data-period="${i*2+j}" value="${escape(this.periods[i*2+j])}" aria-label="${label} ${i===0?'da referência':'da comparação'}"></label>`).join('')}</fieldset>`).join('')}</div>
      <p class="help">Horários de Brasília (UTC−03:00). O fim de um período pode coincidir com o início do seguinte.</p>
      <div class="fields"><label class="field"><span>Altitude da instalação <span class="optional">m · opcional</span></span><input id="altitude" inputmode="decimal" value="${escape(this.altitude)}" placeholder="Não tenho esse dado" aria-describedby="altitude-help"><small id="altitude-help">Usada na conversão de pressão manométrica para absoluta. Sem altitude, a referência atmosférica do motor fica identificada como assumida.</small></label></div>
      <div class="notice">Você receberá os indicadores principais, uma síntese das explicações compatíveis e a próxima verificação. Evidências detalhadas e relatório completo fazem parte da experiência completa da EULER.</div>
      <p class="help">Ao gerar a prévia, estes registros serão enviados ao serviço de análise da EULER, usados no cálculo e descartados ao final da requisição. Não são gravados em banco de dados nem enviados no contato comercial. Fechar esta janela mantém o preenchimento; recarregar a página o apaga.</p>`;
  }
  resultHTML() {
    const r=this.result, c=r.consumption;
    const available = c.referencia!==null && c.comparacao!==null && c.referencia>0;
    const pct=available?(c.comparacao/c.referencia-1)*100:null;
    const max=available?Math.max(c.referencia,c.comparacao)*1.15:1;
    const status={supported:'Explicações compatíveis',limited:'Análise com limites',insufficient:'Dados insuficientes'}[r.status];
    return `<h2 class="pane-title" tabindex="-1">O começo da sua investigação.</h2>
      <div class="editor-meta"><p class="help">${escape(r.boiler)} · ${escape((r.source||[]).map(s=>s==='sintetico'?'dados sintéticos':s==='real'?'dados reais':s==='publico'?'dados públicos':s).join(', ')||'origem não declarada')}</p><span class="tag accent">${status}</span></div>
      <div class="result-grid"><div><p class="metric" id="metric">${available?signed(pct):'—'}</p><p class="help">${available?'no consumo por tonelada de vapor':'Consumo por tonelada de vapor indisponível'}</p>
      ${available?`<div class="chart" aria-label="Comparação do consumo específico">${[['Referência',c.referencia,''],['Comparação',c.comparacao,'current']].map(([label,value,cls])=>`<div class="chart-row"><span>${label}</span><span class="track" aria-hidden="true"><i class="fill ${cls}" style="width:${value/max*100}%"></i></span><span class="chart-value">${num(value*1000)} kg/t de vapor</span></div>`).join('')}</div>`:''}
      <p class="insight">${escape(r.finding)}</p><details class="details"><summary>Como interpretar a incerteza</summary><p>${escape(r.criteria)}</p></details></div>
      <div><h3>O que os registros sustentam</h3>${r.hypotheses.length?`<ul>${r.hypotheses.map(h=>`<li class="insight">${escape(h)}</li>`).join('')}</ul><p class="help">Compatível com os dados não significa causa comprovada.</p>`:'<p class="insight">Os dados ainda não sustentam uma explicação para a mudança de consumo.</p>'}
      ${r.reason?`<div class="notice"><strong>Limite da conclusão</strong><p>${escape(r.reason)}.</p></div>`:''}
      <div class="next"><h3>Próxima verificação</h3><p>${escape(r.next.acao)}</p><p class="muted">${escape(r.next.porque)}</p></div></div></div>
      ${r.limits.length?`<details class="details"><summary>Dados e limitações que precisam de atenção (${r.limits.length})</summary><ul>${r.limits.map(t=>`<li>${escape(t)}</li>`).join('')}</ul></details>`:''}
      ${this.warningsHTML(r.warnings)}
      <div class="upgrade"><p class="eyebrow">Continue a investigação</p><h3>Quer entender os fatores por trás desse resultado?</h3><div class="upgrade-grid"><div><strong>Evidências e hipóteses</strong><p>Explore os dados que sustentam cada explicação e as verificações que as diferenciam.</p></div><div><strong>Incertezas em detalhe</strong><p>Examine os limites das medições e o que falta para avançar.</p></div><div><strong>Relatório completo</strong><p>Reúna a investigação para discutir os próximos passos com sua equipe.</p></div></div><a class="btn primary" href="#proposta" data-action="contact">Quero conhecer a EULER completa</a><p class="help">Converse sobre um piloto exploratório. O acesso completo depende da proposta; seus registros não são enviados por este botão.</p></div>
      <p class="fine" style="margin-top:20px">Ferramenta de apoio à investigação, em desenvolvimento. Não emite comandos operacionais, não substitui procedimentos, alarmes, intertravamentos ou a avaliação do responsável técnico e não constitui Registro de Segurança.</p>`;
  }
  warningsHTML(warnings=[]) {
    return warnings.length?`<details class="details"><summary>Avisos de qualidade dos registros (${warnings.length})</summary><ul class="warnings">${warnings.map(w=>`<li><strong>${escape(NAMES[w.tabela]||w.tabela)}${w.linha?` · linha ${w.linha}`:''}:</strong> ${escape(w.mensagem)}</li>`).join('')}</ul></details>`:'';
  }
  render(focus=true) {
    this.message('');
    this.shadowRoot.querySelectorAll('.steps li').forEach((li,i)=>i===this.step?li.setAttribute('aria-current','step'):li.removeAttribute('aria-current'));
    if (this.step===0) {
      this.$('content').innerHTML=`<h2 class="pane-title" tabindex="-1">Por onde você quer começar?</h2><p class="pane-lead">Conheça o fluxo completo de entrada e receba uma prévia da investigação, sem cadastro.</p><div class="choices"><button class="choice" data-action="own"><span class="mono">SEUS REGISTROS</span><strong>Usar meus dados</strong><p>Preencha os cinco grupos de informações ou importe seus arquivos CSV.</p></button><button class="choice" data-action="complete"><span class="mono">CASO SIMULADO</span><strong>Experimentar dados suficientes</strong><p>Uma caldeira sintética com registros e incertezas cadastrados. Todos os valores podem ser editados.</p></button></div><button class="text-btn" data-action="limited">Experimentar o mesmo caso com dados insuficientes</button><p class="help">Nesse segundo exemplo, faltam informações de incerteza de quatro instrumentos. Os registros de operação são os mesmos.</p><div class="notice">A prévia mostra resultados reais do motor de investigação a partir das entradas. A análise detalhada faz parte da experiência completa da EULER.</div>`;
      this.$('footer').innerHTML='<p class="fine">Seu preenchimento fica nesta sessão até você gerar a prévia.</p><button class="btn" data-action="close">Voltar ao site</button>';
    } else if(this.step===1) {
      this.$('content').innerHTML=this.editor();
      this.$('footer').innerHTML='<p class="fine">Campos vazios são tratados como informação ausente.</p><div class="actions"><button class="btn" data-action="close">Continuar depois</button><button class="btn primary" data-action="next">Revisar e comparar</button></div>';
    } else if(this.step===2) {
      this.$('content').innerHTML=this.review();
      this.$('footer').innerHTML='<p class="fine">Os registros serão processados sem armazenamento.</p><div class="actions"><button class="btn" data-action="back">Editar registros</button><button class="btn primary" data-action="analyze">Gerar prévia</button></div>';
    } else {
      this.$('content').innerHTML=this.resultHTML();
      this.$('footer').innerHTML='<p class="fine">Prévia da investigação · motor EULER</p><div class="actions"><button class="btn" data-action="reset">Reiniciar</button><button class="btn primary" data-action="edit">Editar e analisar novamente</button></div>';
    }
    if(focus) { this.shadowRoot.querySelector('.viewport').scrollTop=0; this.$('content').querySelector('.pane-title')?.focus({preventScroll:true}); }
  }
  async analyze() {
    if(!this.checkRecords()) return;
    const dates=this.periods.map(v=>v?`${v}:00-03:00`:'');
    const error=validatePeriods(dates.slice(0,2),dates.slice(2));
    if(error) { this.message(error); return; }
    const altitude=this.altitude.trim()===''?null:Number(this.altitude.replace(',','.'));
    if(altitude!==null && (!Number.isFinite(altitude)||altitude < -500||altitude > 5000)) { this.message('Informe uma altitude entre −500 e 5.000 m, ou deixe em branco.'); this.$('altitude').focus(); return; }
    this.result=null; this.busy=true; this.message(''); this.controller=new AbortController();
    const controller=this.controller, requestId=this.requestId=(this.requestId||0)+1;
    this.$('content').innerHTML='<div class="busy" role="status"><div class="pulse" aria-hidden="true"></div><h2 class="pane-title">Investigando os registros…</h2><p class="pane-lead">Comparando os períodos e verificando o que as medições permitem concluir.</p></div>';
    this.$('footer').innerHTML='<p class="fine">Se precisar sair, o preenchimento permanece nesta página.</p><button class="btn" data-action="close">Cancelar análise</button>';
    const timeout=setTimeout(()=>controller.abort(),60000);
    try {
      const response=await fetch(new URL('./api/analyze',document.baseURI),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({tables:this.tables,altitude,reference:dates.slice(0,2),comparison:dates.slice(2)}),signal:controller.signal});
      if(!response.headers.get('content-type')?.includes('application/json')) throw new Error('O serviço de investigação não está disponível nesta instalação. Seus registros foram mantidos. Tente novamente quando o serviço estiver ativo.');
      const result=await response.json();
      if (requestId!==this.requestId) return;
      if(!response.ok) throw new Error(result.message||'Não foi possível concluir a análise.');
      this.busy=false;
      if(result.validation) {
        this.step=1; this.render(); this.message(result.message);
        this.$('content').insertAdjacentHTML('afterbegin',this.warningsHTML(result.warnings).replace('<details class="details">','<details class="details" open>')); return;
      }
      this.result=result; this.step=3; this.render(); this.announce('Prévia pronta. Confira o resultado e as limitações.');
    } catch(error) {
      if (requestId!==this.requestId) return;
      this.busy=false; this.step=2; this.render();
      if(this.dialog.open) this.message(error.name==='AbortError'?'A análise foi interrompida. Seus registros foram mantidos; tente novamente.':error.message==='Failed to fetch'?'Não foi possível acessar o serviço de investigação. Seus registros foram mantidos.':error.message);
    } finally { clearTimeout(timeout); if(requestId===this.requestId) this.busy=false; }
  }
}
if(!customElements.get('euler-demo')) customElements.define('euler-demo',EulerDemo);
// The original navigation knows only .beat destinations. Handle this added anchor alone.
document.addEventListener('click',event=>{
  if(event.button!==0||event.ctrlKey||event.metaKey||event.shiftKey||event.altKey) return;
  const anchor=event.target.closest?.('a[href="#euler-demo"]');
  const target=document.getElementById('euler-demo');
  if(!anchor||!target) return;
  event.preventDefault(); event.stopImmediatePropagation();
  exitSceneExploration();
  document.body.classList.remove('menu-open');
  document.getElementById('menuToggle')?.setAttribute('aria-expanded', 'false');
  target.style.scrollMarginTop='90px'; target.scrollIntoView({behavior:'instant',block:'start'});
  target.querySelector('euler-demo')?.shadowRoot?.querySelector('[data-action="open"]')?.focus({preventScroll:true});
  history.replaceState(null,'','#euler-demo');
},true);
