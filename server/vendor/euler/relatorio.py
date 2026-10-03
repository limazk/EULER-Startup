"""JSON de investigação → relatório em linguagem simples (HTML; PDF pelo navegador) — T14.

Cinco blocos fixos, sempre nesta ordem:
    1. O que mudou · 2. O que os dados sustentam · 3. Explicações possíveis ·
    4. O que falta saber · 5. Próxima verificação
Rodapé de segurança obrigatório. O texto só traz **verificações**, nunca comandos
operacionais (testado com uma lista de verbos proibidos).
O HTML é autossuficiente (CSS embutido) e pronto para imprimir em A4.
"""

from __future__ import annotations

import re
from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

from euler.formato import num, pct
from euler.textos import PERGUNTA_CENTRAL, RODAPE_SEGURANCA, SITUACAO_MODELO

BLOCOS = (
    "O que mudou",
    "O que os dados sustentam",
    "Explicações possíveis",
    "O que falta saber",
    "Próxima verificação",
)

VERBOS_PROIBIDOS = (
    "abrir", "abra", "fechar", "feche", "ajustar", "ajuste", "aumentar", "aumente",
    "reduzir", "reduza", "diminuir", "diminua", "regular", "regule", "ligar", "ligue",
    "desligar", "desligue", "acionar", "acione", "elevar", "eleve", "baixar", "baixe",
    "trocar", "troque", "substituir", "substitua", "purgar", "purgue", "setpoint",
    "operar", "opere", "alterar", "altere",
)  # fmt: skip
"""Verbos de comando operacional que nunca podem aparecer num relatório (regra 1)."""

ROTULO_STATUS = {
    "sustentada": "Explicação compatível com os dados (não comprovada)",
    "oposta": "Mudou no sentido contrário (compensou parte da mudança)",
    "possivel": "Continua possível",
    "descartada": "Descartada pelos dados",
    "nao_avaliavel": "Não dá para avaliar com os dados atuais",
}

MARCA_SVG = (
    '<svg viewBox="0 0 32 32" aria-hidden="true">'
    '<rect x="8" y="6" width="2.4" height="20" rx="0.4" fill="#1d1d1b"/>'
    '<rect x="8" y="6" width="16" height="2.4" rx="0.4" fill="#1d1d1b"/>'
    '<rect x="12.6" y="14.8" width="9.4" height="2.4" rx="0.4" fill="#1d1d1b"/>'
    '<rect x="8" y="23.6" width="16" height="2.4" rx="0.4" fill="#1d1d1b"/></svg>'
)
"""Marca EULER (D61, a mesma de app/imagens/euler_marca.svg, em tinta escura para o papel)."""

CSS = """
@page { size: A4; margin: 18mm 16mm 20mm; }
:root { --tinta: #1d1d1b; --tinta-2: #52514e; --linha: #e2e1dc; --fundo: #ffffff;
        --destaque: #262626; --ok: #1d6b3a; --ok-fundo: #e8f3ec; --alerta: #8a5a00;
        --alerta-fundo: #fdf3dc; --info-fundo: #eef4fb; }
* { box-sizing: border-box; }
body { font-family: "Source Sans 3", "Segoe UI", Arial, sans-serif; color: var(--tinta);
       background: var(--fundo); margin: 0; line-height: 1.5; font-size: 15px; }
main { max-width: 820px; margin: 0 auto; padding: 32px 24px 24px; }
header { border-bottom: 3px solid var(--destaque); padding-bottom: 12px; margin-bottom: 20px; }
.marca { font-weight: 600; letter-spacing: .2em; color: var(--destaque); font-size: 13px;
         display: flex; align-items: center; gap: 8px; }
.marca svg { width: 22px; height: 22px; flex: none; }
h1 { font-size: 26px; margin: 4px 0 6px; line-height: 1.2; }
.meta { color: var(--tinta-2); font-size: 13px; margin: 2px 0; }
.selo { display: inline-block; font-size: 12px; font-weight: 700; padding: 2px 8px;
        border-radius: 4px; background: var(--alerta-fundo); color: var(--alerta); }
.pergunta { color: var(--tinta-2); font-style: italic; border-left: 3px solid var(--linha);
            padding-left: 10px; margin: 14px 0 18px; }
.conclusao { padding: 12px 16px; border-radius: 6px; margin: 0 0 22px; font-weight: 600; }
.conclusao p { margin: 0 0 4px; }
.conclusao p:last-child { margin: 0; }
.conclusao.ok { background: var(--ok-fundo); color: var(--ok); }
.conclusao.abstencao { background: var(--alerta-fundo); color: var(--alerta); }
section { margin: 0 0 22px; }
h2 { font-size: 18px; margin: 0 0 8px; padding-bottom: 4px; border-bottom: 1px solid var(--linha);
     break-after: avoid-page; }
tr, .conclusao, li { break-inside: avoid; }
h2 .n { color: var(--destaque); margin-right: 6px; }
table { width: 100%; border-collapse: collapse; font-size: 14px; margin: 8px 0; }
th, td { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--linha); vertical-align: top; }
th { color: var(--tinta-2); font-weight: 600; }
.hipotese { border: 1px solid var(--linha); border-radius: 6px; padding: 10px 14px; margin: 8px 0;
            break-inside: avoid; }
.hipotese .titulo { font-weight: 700; }
.hipotese .status { font-size: 12px; font-weight: 700; color: var(--tinta-2); text-transform: uppercase;
                    letter-spacing: .04em; }
.verificacao { color: var(--tinta-2); font-size: 14px; margin-top: 4px; }
.nota { color: var(--tinta-2); font-size: 13px; }
.valor { font-size: 20px; font-weight: 700; }
.proxima { background: var(--info-fundo); border-radius: 6px; padding: 12px 16px; }
.proxima .acao { font-weight: 700; }
footer { margin-top: 28px; padding-top: 10px; border-top: 1px solid var(--linha); color: var(--tinta-2);
         font-size: 12px; }
ul { margin: 6px 0; padding-left: 20px; }
"""


def _e(texto: object) -> str:
    return escape(str(texto))


def _valor(v: float | None, unidade: str) -> str:
    if v is None:
        return "—"
    if unidade == "fração":
        return pct(v)
    casas = 3 if unidade in ("MJ/kg", "t/t") else 1
    return f"{num(v, casas)} {unidade}"


ROTULO_DETECCAO = {
    "sim": "sim",
    "condicional": "só se o erro do mesmo instrumento se repetir",
    "nao": "não (variação normal)",
    None: "sem incerteza para dizer",
}
"""Os quatro estados da detecção (D37, A3); 'condicional' e 'sem incerteza' são diferentes."""


def mudou_detectavel(c: dict) -> str:
    """Coluna "Mudou de forma detectável?" (tabela do relatório e da tela)."""
    if c["variacao"] is None:
        return "—"
    texto = ROTULO_DETECCAO[c["detectabilidade"]]
    if c.get("faltam_na_incerteza") and c["detectabilidade"] == "condicional":
        texto += " (falta cadastrar a incerteza)"
    return texto


def _hipotese_html(h: dict) -> str:
    efeito = h["efeito"]["consumo_pct"]
    linha_efeito = (
        f'<div class="nota">Efeito estimado no consumo: {"+" if efeito >= 0 else ""}{num(efeito, 1)}%</div>'
        if efeito is not None and h["status"] in ("sustentada", "possivel")
        else ""
    )
    return (
        '<div class="hipotese">'
        f'<div class="status">{_e(ROTULO_STATUS[h["status"]])}</div>'
        f'<div class="titulo">{_e(h["titulo"])}</div>'
        f"<div>{_e(h['porque'])}</div>{linha_efeito}"
        f'<div class="verificacao">Como verificar: {_e(h["verificacao"])}</div>'
        "</div>"
    )


def gerar_html(investigacao: dict, gerado_em: datetime | None = None) -> str:
    """Relatório HTML completo (5 blocos + rodapé de segurança) a partir do JSON."""
    j = investigacao
    gerado_em = gerado_em or datetime.now(ZoneInfo("America/Sao_Paulo"))
    ref, comp = j["periodos"]["referencia"], j["periodos"]["comparacao"]
    origens = set(j.get("origem_dados", []))
    selo = (
        '<span class="selo">DADOS SINTÉTICOS</span>'
        if origens == {"sintetico"}
        else '<span class="selo">CONTÉM DADOS SINTÉTICOS</span>'
        if "sintetico" in origens
        else ""
    )
    conclusao = j["conclusao"]
    # resultado em até três frases (D63); a conclusão completa abre o bloco 2
    resumo = "".join(f"<p>{_e(f)}</p>" for f in j["resumo"]["frases"])
    hips = j["hipoteses"]

    # 1. o que mudou
    linhas = "".join(
        f"<tr><td>{_e(c['nome'][0].upper() + c['nome'][1:])}</td>"
        f"<td>{_e(_valor(c['referencia'], c['unidade']))}</td>"
        f"<td>{_e(_valor(c['comparacao'], c['unidade']))}</td>"
        f"<td>{_e(mudou_detectavel(c))}</td></tr>"
        for c in j["o_que_mudou"]["indicadores"]
        if c["referencia"] is not None or c["comparacao"] is not None
    )
    custo = j["o_que_mudou"]["custo_vapor"]
    valor = j["valor_em_jogo"]
    if valor:
        incerteza = (
            f" (± R$ {num(valor['incerteza_brl'], 0)})"
            if valor["incerteza_brl"] is not None
            else ""
        )
        bloco_valor = (
            f'<p><span class="valor">R$ {num(valor["valor_brl"], 0)}</span>{_e(incerteza)} '
            f"em jogo no período de comparação (estimado).</p>"
            f'<p class="nota">{_e(valor["base"])}</p>'
        )
    else:
        bloco_valor = f'<p class="nota">{_e(j["valor_em_jogo_motivo"])}</p>'
    bloco1 = (
        f"<p><strong>{_e(j['o_que_mudou']['frase'])}</strong></p>"
        + (f"<p>{_e(custo['frase'])}</p>" if custo else "")
        + "<table><thead><tr><th>Indicador</th><th>Referência</th><th>Comparação</th>"
        "<th>Mudou de forma detectável?</th></tr></thead>"
        f"<tbody>{linhas}</tbody></table>" + bloco_valor
    )

    # 2. o que os dados sustentam
    sustentadas = [h for h in hips if h["status"] == "sustentada"]
    opostas = [h for h in hips if h["status"] == "oposta"]
    descartadas = [h for h in hips if h["status"] == "descartada"]
    bloco2 = f"<p>{_e(conclusao['texto'])}</p>"
    bloco2 += "".join(_hipotese_html(h) for h in sustentadas) or (
        "<p>Nenhuma explicação é sustentada pelos dados.</p>"
    )
    bloco2 += "".join(_hipotese_html(h) for h in opostas)
    fechamento = j["o_que_mudou"].get("fechamento")
    if fechamento:
        bloco2 += f'<p class="nota">{_e(fechamento["frase"])}</p>'
        if fechamento.get("frase_com_condicionais"):
            bloco2 += f'<p class="nota">{_e(fechamento["frase_com_condicionais"])}</p>'
    bloco2 += (
        '<p class="nota">"Compatível com os dados" não é causa comprovada: cada explicação '
        "precisa da verificação indicada.</p>"
    )
    if descartadas:
        bloco2 += (
            "<p><strong>Também verificamos e descartamos:</strong></p><ul>"
            + "".join(
                f"<li><strong>{_e(h['titulo'])}.</strong> {_e(h['porque'])}</li>"
                for h in descartadas
            )
            + "</ul>"
        )

    # 3. explicações possíveis
    abertas = [h for h in hips if h["status"] in ("possivel", "nao_avaliavel")]
    bloco3 = "".join(_hipotese_html(h) for h in abertas) or (
        "<p>Nenhuma outra explicação continua em aberto.</p>"
    )

    # 4. o que falta saber
    falta = j["o_que_falta"]
    bloco4 = (
        "<ul>" + "".join(f"<li>{_e(f)}</li>" for f in falta) + "</ul>"
        if falta
        else "<p>Nada essencial faltando para esta comparação.</p>"
    ) + f'<p class="nota">{_e(j["independencia"]["nota"])}</p>'

    # 5. próxima verificação
    prox = j["proxima_verificacao"]
    bloco5 = (
        f'<div class="proxima"><div class="acao">{_e(prox["acao"])}</div>'
        f"<div>{_e(prox['porque'])}</div></div>"
    )

    blocos = (bloco1, bloco2, bloco3, bloco4, bloco5)
    secoes = "".join(
        f'<section><h2><span class="n">{i}.</span>{_e(titulo)}</h2>{conteudo}</section>'
        for i, (titulo, conteudo) in enumerate(zip(BLOCOS, blocos, strict=True), start=1)
    )
    classe = "abstencao" if conclusao["abstencao"] else "ok"
    caldeira = j.get("caldeira_id") or "caldeira"
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>EULER · Relatório de investigação · {_e(caldeira)}</title>
<style>{CSS}</style>
</head>
<body>
<main>
<header>
  <div class="marca">{MARCA_SVG}EULER</div>
  <h1>Relatório de investigação · {_e(caldeira)}</h1>
  <p class="meta">Referência: {_e(ref["rotulo"])} · Comparação: {_e(comp["rotulo"])}</p>
  <p class="meta">Gerado em {gerado_em:%d/%m/%Y %H:%M} · EULER v{_e(j["versao_euler"])}</p>
  {selo}
  <p class="meta">{_e(SITUACAO_MODELO)}</p>
</header>
<p class="pergunta">{_e(PERGUNTA_CENTRAL)}</p>
<div class="conclusao {classe}">{resumo}</div>
{secoes}
<footer>
  <p><strong>{_e(RODAPE_SEGURANCA)}</strong></p>
  <p>Números marcados como estimados vêm de cálculos com hipóteses registradas no
  registro de decisões do projeto. Equações e valores de referência em revisão
  científica; as referências completas estão nos dados técnicos da investigação (JSON).</p>
</footer>
</main>
</body>
</html>
"""


def texto_visivel(html: str) -> str:
    """Texto do relatório sem tags (para verificações automáticas)."""
    sem_estilo = re.sub(r"<style>.*?</style>", " ", html, flags=re.DOTALL)
    return re.sub(r"<[^>]+>", " ", sem_estilo)


def comandos_operacionais(html: str) -> list[str]:
    """Verbos proibidos encontrados no texto visível (deve ser sempre vazio)."""
    texto = texto_visivel(html).lower()
    return [v for v in VERBOS_PROIBIDOS if re.search(rf"\b{v}\b", texto)]


CHROMIUM_ALTERNATIVO = "/opt/pw-browsers/chromium"


def gerar_pdf(html: str) -> bytes | None:
    """PDF A4 do relatório pelo Chromium (Playwright). None se o navegador não estiver
    disponível: nesse caso, abrir o HTML e usar Imprimir → Salvar como PDF (D33)."""
    try:
        from playwright.sync_api import Error as ErroNavegador
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    try:
        with sync_playwright() as p:
            try:
                navegador = p.chromium.launch()
            except ErroNavegador:
                navegador = p.chromium.launch(executable_path=CHROMIUM_ALTERNATIVO)
            pagina = navegador.new_page()
            pagina.set_content(html, wait_until="load")
            pdf = pagina.pdf(format="A4", print_background=True)
            navegador.close()
            return pdf
    except (ErroNavegador, OSError):
        return None
