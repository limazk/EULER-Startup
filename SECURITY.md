# Segurança da prévia pública EULER

A landing page é pública por definição. A proteção concentra-se no endpoint `POST /api/analyze`, nos arquivos internos e na configuração HTTP.

## Controles implementados

- Política CSP para restringir scripts, conexões, frames, objetos, fontes e outros recursos.
- `X-Frame-Options: DENY` e `frame-ancestors 'none'` contra clickjacking.
- `X-Content-Type-Options: nosniff`.
- `Referrer-Policy: strict-origin-when-cross-origin`.
- `Permissions-Policy` desabilitando câmera, microfone, geolocalização, pagamento, USB e serial.
- HSTS na Vercel (`max-age=31536000; includeSubDomains`).
- COOP/CORP para isolamento adicional do documento e recursos do próprio site.
- Bloqueio de acesso web a `server/`, `tests/`, fontes `.py` sob `/api`, README, SECURITY e arquivos de configuração conhecidos.
- API aceita apenas `POST` JSON e rejeita submissões browser cross-site.
- Rejeição de `Transfer-Encoding` e de corpos comprimidos.
- Limite de 3 MB por requisição.
- Limite de até 5.000 registros na prévia e validação estrita das colunas/campos.
- Erros internos não retornam traceback ao visitante.
- Rate limit local/best-effort por origem: 20 análises por 60 segundos por padrão.

## Rate limiting em produção

O limitador Python é apenas uma segunda barreira. Em Vercel Functions, memória não é compartilhada entre todas as instâncias, portanto ele **não substitui um rate limit no edge**.

Na Vercel, configure uma regra em **Project → Firewall → Configure → Custom Rule** para o caminho `/api/analyze` e aplique Rate Limit com resposta `429` (ou Challenge). Comece em modo de observação/log quando disponível e ajuste o limite à carga real antes de bloquear tráfego legítimo.

## Variáveis opcionais

- `EULER_RATE_LIMIT_MAX` — padrão `20` (1–1000).
- `EULER_RATE_LIMIT_WINDOW_SECONDS` — padrão `60` (10–3600).

## Segredos

Não coloque tokens, chaves ou senhas no HTML, JavaScript ou repositório. Use Environment Variables da Vercel. `.env` e variantes são ignorados pelo Git e pelo deploy; `.env.example` pode ser versionado desde que contenha apenas placeholders.

## Antes de um SaaS com clientes reais

A prévia atual não tem contas de usuário nem persiste dados. Para o SaaS, adicione autenticação, autorização por empresa/tenant, RBAC, trilha de auditoria, política de retenção, backups e revisão de LGPD antes de armazenar dados industriais de clientes.
