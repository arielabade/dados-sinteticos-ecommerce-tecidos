# Consultas analíticas

Nove consultas comentadas, prontas para rodar no MySQL do repositório (`make mysql`). Cada uma explica no cabeçalho a
definição usada e as limpezas aplicadas.

| Consulta | Pergunta | Áreas usadas |
|---|---|---|
| [`01_cac_roas_mer.sql`](01_cac_roas_mer.sql) | CAC, ROAS (da plataforma e last click) e MER por mês | [2](#2-clientes-e-pedidos) · [3](#3-tracking-e-atribuição) · [4](#4-meta-ads) · [5](#5-google-ads) |
| [`02_ltv_coorte_retencao.sql`](02_ltv_coorte_retencao.sql) | LTV e retenção por coorte da 1ª compra, com clientes unificados pelo CPF | [2](#2-clientes-e-pedidos) |
| [`03_funil_por_canal.sql`](03_funil_por_canal.sql) | Funil GA4 por canal, com eventos deduplicados por `event_id` | [3](#3-tracking-e-atribuição) · [5](#5-google-ads) |
| [`04_rfm.sql`](04_rfm.sql) | Segmentação RFM em quintis | [2](#2-clientes-e-pedidos) |
| [`05_curva_abc.sql`](05_curva_abc.sql) | Curva ABC de produtos nos últimos 12 meses | [1](#1-catálogo-e-estoque) · [2](#2-clientes-e-pedidos) |
| [`06_comparacao_atribuicao.sql`](06_comparacao_atribuicao.sql) | Modelos de atribuição lado a lado e o que cada plataforma reporta | [3](#3-tracking-e-atribuição) · [4](#4-meta-ads) · [5](#5-google-ads) |
| [`07_investimento_vs_conversoes.sql`](07_investimento_vs_conversoes.sql) | Investimento, conversões reportadas e pedidos atribuídos por campanha | [4](#4-meta-ads) · [5](#5-google-ads) |
| [`08_limpeza_tracking.sql`](08_limpeza_tracking.sql) | Diagnóstico das imperfeições do tracking (as mesmas regras viram `stg_eventos` e `stg_sessoes` no dbt) | [3](#3-tracking-e-atribuição) |
| [`09_ruptura_estoque.sql`](09_ruptura_estoque.sql) | Dias sem saldo e demanda perdida por subcategoria e mês | [1](#1-catálogo-e-estoque) |

## Tabelas que as consultas usam

### 1. Catálogo e estoque
![Catálogo e estoque](../../docs/diagramas/01_catalogo_estoque.svg)

### 2. Clientes e pedidos
![Clientes, pedidos e pós-venda](../../docs/diagramas/02_clientes_pedidos.svg)

### 3. Tracking e atribuição
![Tracking do site e atribuição](../../docs/diagramas/03_tracking_atribuicao.svg)

### 4. Meta Ads
![Meta Ads](../../docs/diagramas/04_meta_ads.svg)

### 5. Google Ads
![Google Ads](../../docs/diagramas/05_google_ads.svg)

Leitura dos diagramas e regras de cardinalidade: [`docs/diagrama_er.md`](../../docs/diagrama_er.md).
