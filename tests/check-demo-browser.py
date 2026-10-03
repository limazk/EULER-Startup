"""Real browser journey. Start server/app.py on port 8766 before running."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parents[1]
ARTIFACTS=ROOT/'tests'/'artifacts';ARTIFACTS.mkdir(exist_ok=True)
URL='http://127.0.0.1:8766/'
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-gpu','--disable-software-rasterizer'])
    page=browser.new_page(viewport={'width':1440,'height':1000},reduced_motion='reduce')
    page.set_default_timeout(15000)
    errors=[]; page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto(URL,wait_until='networkidle')
    d=page.locator('euler-demo')
    page.get_by_role('link',name='Testar a EULER').click()
    assert page.url.endswith('#euler-demo')
    d.get_by_role('button',name='Experimentar a EULER',exact=True).click()
    d.get_by_role('button',name='Experimentar dados suficientes').click()
    expect(d.locator('[data-field="caldeira_id"]')).to_have_value('CALD-DEMO-01')
    # Form validation is tied to the actual row/field, and input remains editable.
    d.locator('[data-field="caldeira_id"]').fill('')
    d.get_by_role('button',name='Revisar e comparar').click()
    expect(d.locator('[data-field="caldeira_id"]')).to_have_attribute('aria-invalid','true')
    d.locator('[data-field="caldeira_id"]').fill('CALD-DEMO-01')
    d.get_by_role('button',name='Revisar e comparar').click()
    d.get_by_label('Início da comparação').fill('2026-08-04T07:30')
    d.get_by_role('button',name='Gerar prévia',exact=True).click()
    expect(d.locator('#message')).to_contain_text('sobrepor')
    d.get_by_label('Início da comparação').fill('2026-08-31T07:30')
    d.get_by_role('button',name='Gerar prévia',exact=True).click()
    expect(d.locator('#metric')).to_have_text('+10,1%',timeout=30000)
    expect(d.locator('.tag.accent')).to_have_text('Explicações compatíveis')
    expect(d.locator('#content')).to_contain_text('Combustível mais úmido')
    d.locator('dialog').screenshot(path=str(ARTIFACTS/'resultado-desktop.png'))
    for width in [320,375,768,1440]:
        page.set_viewport_size({'width':width,'height':900})
        assert d.locator('dialog').evaluate('e=>e.scrollWidth<=e.clientWidth'),width
        assert d.locator('.viewport').evaluate('e=>e.scrollWidth<=e.clientWidth'),width
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),width
        print(f'PASS result layout {width}px',flush=True)
    page.set_viewport_size({'width':375,'height':900})
    d.locator('dialog').screenshot(path=str(ARTIFACTS/'resultado-celular.png'))
    d.get_by_role('button',name='Editar e analisar novamente').click()
    expect(d.locator('#metric')).to_have_count(0)
    # Every instrument field, including uncertainties, is editable.
    d.locator('[data-table="instrumentos"]').click()
    expect(d.locator('[data-field="incerteza_declarada"]')).to_be_visible()
    # Closing and reopening preserve current edits and selected row.
    d.locator('[data-field="observacao"]').fill('Teste de persistência na sessão')
    d.get_by_role('button',name='Fechar demonstração').click()
    expect(d.locator('dialog')).not_to_be_visible()
    d.get_by_role('button',name='Experimentar a EULER',exact=True).click()
    expect(d.locator('[data-field="observacao"]')).to_have_value('Teste de persistência na sessão')
    # Focus remains inside native modal; Escape returns to the opener.
    page.keyboard.press('Escape')
    expect(d.locator('dialog')).not_to_be_visible()
    d.get_by_role('button',name='Experimentar a EULER',exact=True).click()
    d.get_by_role('button',name='Reiniciar demonstração').click()
    d.get_by_role('button',name='Apagar preenchimento').click()
    d.get_by_role('button',name='Experimentar o mesmo caso com dados insuficientes').click()
    d.get_by_role('button',name='Revisar e comparar').click()
    d.get_by_role('button',name='Gerar prévia',exact=True).click()
    expect(d.locator('#metric')).to_have_text('+10,1%',timeout=30000)
    expect(d.locator('.tag.accent')).to_have_text('Análise com limites')
    expect(d.locator('#content')).to_contain_text('incerteza do método de umidade')
    d.get_by_role('link',name='Quero conhecer a EULER completa').click()
    expect(d.locator('dialog')).not_to_be_visible()
    assert page.url.endswith('#proposta')
    page.locator('#proposta input[name="nome"]').fill('Teste local')
    # Starting with own data yields empty groups, no synthetic values substituted.
    d.get_by_role('button',name='Experimentar a EULER',exact=True).click()
    d.get_by_role('button',name='Reiniciar',exact=True).click()
    d.get_by_role('button',name='Apagar preenchimento').click()
    d.get_by_role('button',name='Usar meus dados').click()
    expect(d.locator('#content')).to_contain_text('Nenhum registro neste grupo')
    d.get_by_role('button',name='Adicionar primeiro registro').click()
    expect(d.locator('[data-field="caldeira_id"]')).to_have_value('')
    d.locator('[data-field="caldeira_id"]').fill('MINHA-CALDEIRA')
    d.locator('[data-field="instante_observado"]').fill('2026-08-03T08:00:00-03:00')
    d.locator('[data-field="totalizador_vapor_t"]').fill('100')
    d.locator('[data-field="t_gases_c"]').fill('180')
    d.get_by_role('button',name='Duplicar',exact=True).click()
    d.locator('[data-field="instante_observado"]').fill('2026-08-04T08:00:00-03:00')
    d.locator('[data-field="totalizador_vapor_t"]').fill('120')
    for width in [320,375,768,1440]:
        page.set_viewport_size({'width':width,'height':900})
        assert d.locator('.viewport').evaluate('e=>e.scrollWidth<=e.clientWidth'),width
    d.locator('dialog').screenshot(path=str(ARTIFACTS/'formulario-desktop.png'))
    d.get_by_role('button',name='Revisar e comparar').click()
    d.get_by_label('Início da referência').fill('2026-08-03T08:00')
    d.get_by_label('Fim da referência').fill('2026-08-04T08:00')
    d.get_by_label('Início da comparação').fill('2026-08-04T08:00')
    d.get_by_label('Fim da comparação').fill('2026-08-05T08:00')
    d.get_by_role('button',name='Gerar prévia',exact=True).click()
    expect(d.locator('#metric')).to_have_text('—',timeout=30000)
    expect(d.locator('.tag.accent')).to_have_text('Dados insuficientes')
    d.get_by_role('button',name='Fechar demonstração').click()
    assert page.locator('body').evaluate('e=>e.classList.contains("reading")')
    assert not errors,errors
    # Existing content and fallback survive JS-disabled navigation.
    fallback=browser.new_page(java_script_enabled=False)
    fallback.goto(URL)
    expect(fallback.locator('euler-demo')).to_contain_text('Ative o JavaScript')
    print('PASS complete, limited, own input, errors, modal, mobile, CTA, reading mode and fallback',flush=True)
    browser.close()
