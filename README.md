# simplified-auction

CRM de leilão de imóveis da **Caixa Econômica Federal**: coleta o catálogo, guarda
histórico, pontua oportunidades, calcula viabilidade, organiza a due diligence e
analisa documentos do imóvel com IA (sob demanda).

> Uso pessoal/analítico. O app **não** faz propostas, **não** arremata e **não**
> redistribui a base. Antes de arrematar, valide tudo com um advogado.

## Fontes de dados (o que foi realmente verificado)

| Dado | Como | Proteção anti-bot |
| --- | --- | --- |
| Lista oficial completa | `GET /listaweb/Lista_imoveis_{UF}.csv` (ou `geral`) | Sem sessão; pode ser bloqueada temporariamente por excesso de requisições |
| Ficha do imóvel | `GET /sistema/detalhe-imovel.asp?hdnimovel=<id>` | Radware Bot Manager — exige ritmo baixo (ou o modo navegador) |
| Matrícula (PDF) | `GET /editais/matricula/{UF}/{id:013d}.pdf` | **Sem** anti-bot (asset estático) — derivável do id |
| Fotos | `GET /fotos/F....jpg` (via ficha) | Sem anti-bot |
| Editais/avisos (PDF) | `POST carregaPesquisaDocumentos.asp` → `/editais/{arq}` | Listagem protegida; PDFs são estáticos |
| Busca ativa | `POST carregaPesquisaImoveis.asp` | Protegida |

O CSV é o **caminho principal e confiável**. A ficha enriquece (matrícula,
comarca, formas de pagamento, regras de despesas, fotos) e a matrícula em PDF é
derivável do id — então os documentos mais valiosos para a análise jurídica
saem sem depender de burlar proteção.

### Proteção anti-bot (o que foi descoberto na prática)

- É o **Radware Bot Manager** (via `validate.perfdrive.com`), que pontua o
  **conjunto inteiro de cabeçalhos** — não só o User-Agent. Testes reais:
  - UA com o nome do app → **bloqueado**;
  - só o UA de Chrome (sem os demais cabeçalhos) → **bloqueado**;
  - UA de Chrome **+** `Accept`, `Accept-Language`, `Sec-Fetch-*`,
    `Upgrade-Insecure-Requests` → **passa**.
- Por isso o cliente envia, por padrão, um **fingerprint de navegador**
  (`config.browser_headers`). Dá para trocar o UA com `AUCTION_USER_AGENT`.
- Também é **adaptativo por comportamento/ritmo**: rajadas de requisições
  disparam um bloqueio temporário (que pode atingir até o CSV por alguns
  minutos). O app nasce com **rate-limit** (`AUCTION_MIN_INTERVAL`, 1,5s),
  retry com backoff e cache. Em bloqueio, **espere alguns minutos** — não insista.
- Para páginas `/sistema/` que exigem o desafio JS existe o **modo navegador**
  opcional (Playwright/Chromium): `AUCTION_BROWSER=1` ou `--browser`.

## Instalação (desenvolvimento)

```bash
cd /Users/lucasdavi/IA/simplified-auction
uv venv --python-preference only-managed --python 3.12 .venv
uv pip install --python .venv/bin/python -e ".[gui,dev]"
```

Opcional (modo navegador para as páginas `/sistema/`):

```bash
uv pip install --python .venv/bin/python -e ".[browser]"
.venv/bin/playwright install chromium
```

## Uso (CLI)

```bash
# 1) Lista oficial (base do catalogo) — incremental
.venv/bin/auction sync --uf AC
.venv/bin/auction sync --uf geral     # Brasil inteiro

# 2) Matriculas (PDF) dos imoveis com desconto >= 40%
.venv/bin/auction matricula --uf AC --min-desconto 40 --limit 20

# 3) Ficha (matricula, comarca, formas de pagamento, fotos)
.venv/bin/auction enrich --uf AC --limit 30
.venv/bin/auction enrich --uf AC --limit 30 --browser   # se bloqueado

# 4) Oportunidades
.venv/bin/auction list --uf AC --min-desconto 40 --top 20
.venv/bin/auction show 10005120
.venv/bin/auction export --uf AC --out oportunidades.csv

# 5) Editais/avisos (PDF)
.venv/bin/auction docs list  --uf AC --ano 2026 --mes 10 --tipo 9
.venv/bin/auction docs fetch --uf AC --ano 2026 --mes 10 --tipo 9 --limit 10

# 6) Busca ativa no site (resolve ids; dados saem do catalogo local)
.venv/bin/auction search --uf AC --cidade "RIO BRANCO"

# 7) Analise por IA (manual por padrao; veja abaixo)
.venv/bin/auction analyze 10005120 --documento 1 --manual --out prompt.txt
```

## GUI

```bash
.venv/bin/python -m simplified_auction.gui
```

Abas: **Oportunidades** (tabela por score, filtros, exportar CSV),
**Ficha** (dados + ficha, viabilidade, due diligence, fotos, baixar matrícula,
analisar com IA), **Pipeline**, **Editais**, **Config** (sincronizar/enriquecer)
e **IA** (cadastro de provedores).

## Análise por IA (híbrida, nunca automática)

### Cadastro de provedor dentro do app (aba **IA**)

Cadastre um ou mais provedores pela própria tela (ou pela CLI) e escolha o
**ativo**. A análise passa a rodar de dentro do app:

- Botão **Testar conexão** (mostra OK ou o erro — nunca falha em silêncio).
- A chave fica só no seu computador, em `providers.json` com permissão `0600`.
- Sem provedor ativo, o app cai no **modo manual** (gera o prompt para colar).

```bash
.venv/bin/auction ai list
.venv/bin/auction ai add --kind anthropic --model claude-sonnet-4-5 --key sk-... --label "Meu Claude"
.venv/bin/auction ai add --kind openai    --model gpt-4o-mini      --key sk-...
.venv/bin/auction ai use <id>
.venv/bin/auction ai test
.venv/bin/auction ai rm <id>
```

Tipos aceitos: `anthropic`, `openai`, `gemini` e `compatible` (qualquer endpoint
compatível com OpenAI, informando `--base-url`).

### Modo manual (funciona sem provedor)

O app monta um prompt com o checklist jurídico (matrícula, ônus, ocupação,
débitos propter rem, prazos, riscos) + o texto do documento. Você cola no
ChatGPT/Claude/Gemini web e cola a resposta de volta; o app interpreta o JSON e
guarda. Sem custo.

### Fallback por ambiente

Se não houver provedor cadastrado, valem as variáveis:

```bash
export AUCTION_AI_PROVIDER=anthropic    # anthropic | openai | gemini | compatible
export AUCTION_AI_MODEL=claude-sonnet-4-5
export AUCTION_AI_KEY=sk-...
# export AUCTION_AI_BASE_URL=https://...   # provedores compativeis (OpenAI)
```

> LGPD: editais/matrículas podem conter dados pessoais (ex.: CPF do devedor).
> O modo manual é o padrão justamente para você decidir o que enviar.

## Configuração (variáveis de ambiente)

| Variável | Padrão | Para quê |
| --- | --- | --- |
| `AUCTION_HOME` | diretório de dados do SO | onde ficam `auction.db` e os documentos |
| `AUCTION_MIN_INTERVAL` | `1.5` | segundos entre requisições (rate-limit) |
| `AUCTION_USER_AGENT` | UA de navegador | identificar/ajustar o cliente |
| `AUCTION_BROWSER` | `0` | `1` liga o modo navegador (Playwright) |
| `AUCTION_AI_*` | — | provedor/modelo/chave (fallback; prefira a aba IA) |

## Qualidade

```bash
.venv/bin/ruff check .
.venv/bin/mypy
.venv/bin/pytest
```

## Build local (macOS)

```bash
cd /Users/lucasdavi/IA/simplified-auction
./scripts/build_macos.sh        # gera dist/simplified-auction-gui.app e dist/simplified-auction
open dist/simplified-auction-gui.app
```

## Releases

Binários **públicos** (sem login) em:
https://github.com/ldmaster/simplified-auction/releases

Para publicar, crie e envie uma tag:

```bash
git tag v0.1.0
git push origin v0.1.0
```

O workflow compila em Windows/Linux/macOS e anexa os zips ao Release.
`COMO-USAR.txt` acompanha cada pacote (linguagem simples para o usuário final).

## Base legal (o que o app organiza, e o que você precisa conferir)

Índice de due diligence usado no checklist e no prompt da IA:

- **Registral:** matrícula, CRI/comarca, áreas, averbação de construção, ônus e
  gravames (hipoteca, alienação fiduciária, penhora, usufruto, indisponibilidade).
- **Procedimento:** modalidade, 1º/2º/único leilão, data, edital, leiloeiro.
- **Valores:** avaliação, valor mínimo, desconto, comissão (~5%).
- **Ocupação:** quem ocupa, existe locação oponível ao arrematante?
- **Passivo que gruda no imóvel:** IPTU/ITR (CTN art. 130), condomínio
  (CC art. 1.345), água/luz; **ler a cláusula do edital sobre quem paga**.
- **Riscos:** nulidade por falha de intimação para purgar (Lei 9.514/97, red. Lei
  14.711/2023), anulatória/embargos, preço vil, desocupação (art. 30 da Lei
  9.514/97), regularidade (habite-se, uso do solo, áreas de risco).

Nada aqui é parecer jurídico: o app organiza informação pública; a decisão e a
validação são do advogado.
