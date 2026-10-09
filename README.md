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

### Proteção anti-bot (o que aprendi na prática)

- O WAF (Radware/ShieldSquare) é **adaptativo por comportamento**: rajadas de
  requisições disparam um desafio (que passou a valer até para o CSV por alguns
  minutos). O app já nasce com **rate-limit** (`AUCTION_MIN_INTERVAL`, padrão
  1,5s), retry com backoff e cache.
- O WAF **rejeita User-Agent que não comece com `Mozilla/5.0`**. O padrão do app
  é honesto e identificável, mas nesse formato:
  `Mozilla/5.0 (compatible; simplified-auction/0.1.0; +https://github.com/ldmaster/simplified-auction)`.
- Para as páginas `/sistema/` que exigem o desafio JS, há o **modo navegador**
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
analisar com IA), **Pipeline**, **Editais** e **Config** (sincronizar/enriquecer).

## Análise por IA (híbrida, nunca automática)

- **Modo manual (padrão):** o app monta um prompt com o checklist jurídico
  (matrícula, ônus, ocupação, débitos propter rem, prazos, riscos) + o texto do
  documento. Você cola no ChatGPT/Claude/Gemini web e cola a resposta de volta;
  o app interpreta o JSON e guarda. Sem custo.
- **Modo API:** configure o ambiente e a análise roda direto.

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
| `AUCTION_USER_AGENT` | UA compatível Mozilla | identificar/ajustar o cliente |
| `AUCTION_BROWSER` | `0` | `1` liga o modo navegador (Playwright) |
| `AUCTION_AI_*` | — | provedor, modelo e chave da IA |

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
