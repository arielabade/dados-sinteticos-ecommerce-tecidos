# Analytical queries

Nine commented queries, ready to run on the repository's MySQL (`make mysql`). Each header explains the definitions used
and the cleaning applied.

| Query | Question | Areas used |
|---|---|---|
| [`01_cac_roas_mer.sql`](01_cac_roas_mer.sql) | CAC, ROAS (platform and last click) and MER by month | [2](#2-customers-and-orders) · [3](#3-tracking-and-attribution) · [4](#4-meta-ads) · [5](#5-google-ads) |
| [`02_ltv_coorte_retencao.sql`](02_ltv_coorte_retencao.sql) | LTV and retention by first-purchase cohort, with customers unified by CPF | [2](#2-customers-and-orders) |
| [`03_funil_por_canal.sql`](03_funil_por_canal.sql) | GA4 funnel by channel, with events deduplicated by `event_id` | [3](#3-tracking-and-attribution) · [5](#5-google-ads) |
| [`04_rfm.sql`](04_rfm.sql) | RFM segmentation in quintiles | [2](#2-customers-and-orders) |
| [`05_curva_abc.sql`](05_curva_abc.sql) | ABC curve of products over the last 12 months | [1](#1-catalog-and-inventory) · [2](#2-customers-and-orders) |
| [`06_comparacao_atribuicao.sql`](06_comparacao_atribuicao.sql) | Attribution models side by side and what each platform reports | [3](#3-tracking-and-attribution) · [4](#4-meta-ads) · [5](#5-google-ads) |
| [`07_investimento_vs_conversoes.sql`](07_investimento_vs_conversoes.sql) | Spend, reported conversions and attributed orders by campaign | [4](#4-meta-ads) · [5](#5-google-ads) |
| [`08_limpeza_tracking.sql`](08_limpeza_tracking.sql) | Diagnosis of the tracking imperfections (the same rules become `stg_eventos` and `stg_sessoes` in dbt) | [3](#3-tracking-and-attribution) |
| [`09_ruptura_estoque.sql`](09_ruptura_estoque.sql) | Days without stock and lost demand by subcategory and month | [1](#1-catalog-and-inventory) |

## Tables the queries use

### 1. Catalog and inventory
![Catalog and inventory](../../docs/diagramas/01_catalogo_estoque.svg)

### 2. Customers and orders
![Customers, orders and after-sales](../../docs/diagramas/02_clientes_pedidos.svg)

### 3. Tracking and attribution
![Website tracking and attribution](../../docs/diagramas/03_tracking_atribuicao.svg)

### 4. Meta Ads
![Meta Ads](../../docs/diagramas/04_meta_ads.svg)

### 5. Google Ads
![Google Ads](../../docs/diagramas/05_google_ads.svg)

How to read the diagrams and the cardinality rules: [`docs/diagrama_er.md`](../../docs/diagrama_er.md).
