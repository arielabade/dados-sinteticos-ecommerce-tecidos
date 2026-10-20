# Camada analítica (dbt)

Os modelos limpam as tabelas brutas do MySQL e montam as tabelas de análise. Rode com `make dbt` (dentro de um container,
com os testes). Os testes de cada camada estão nos arquivos `_*.yml` e em [`tests/`](tests/).

| Camada | Modelo | O que faz | Área de origem |
|---|---|---|---|
| staging | `stg_clientes` | E-mail normalizado, telefone em E.164 e contas duplicadas da mesma pessoa (mesmo CPF) unificadas | [2](#2-clientes-e-pedidos) |
| staging | `stg_pedidos`, `stg_itens_pedido` | Pedidos reais (sem teste), horário local e UTC lado a lado; itens com produto e categoria | [1](#1-catálogo-e-estoque) · [2](#2-clientes-e-pedidos) |
| staging | `stg_sessoes`, `stg_eventos` | UTMs normalizadas; eventos sem duplicata (`event_id` e `transaction_id`) e com fuso corrigido | [3](#3-tracking-e-atribuição) |
| staging | `stg_midia_diaria` | Meta, Google, TikTok e afiliados empilhados no grão data × plataforma × campanha | [4](#4-meta-ads) · [5](#5-google-ads) · [6](#6-mmm-regional-e-outros-canais) |
| staging | `mmm/stg_*` | Canais, regiões, mídia regional, calendário e testes geográficos | [6](#6-mmm-regional-e-outros-canais) |
| intermediate | `int_sessoes_funil` | Uma linha por sessão, com o canal padrão e as etapas do funil | [3](#3-tracking-e-atribuição) |
| marts | `fct_pedidos`, `dim_clientes` | Pedido com sequência do cliente, coorte, margem e canal de last click; cliente unificado | [2](#2-clientes-e-pedidos) |
| marts | `fct_midia_diaria`, `fct_kpis_diarios`, `fct_funil_canal_diario` | Investimento ao lado das conversões reportadas e atribuídas; KPIs diários (receita, MER, CAC); funil por canal | [3](#3-tracking-e-atribuição) · [4](#4-meta-ads) · [5](#5-google-ads) |
| marts | `mmm/fct_mmm_*`, `mmm/dim_testes_geo` | Vendas e mídia por UF e dia, controles (calendário, preço) e os testes geográficos | [6](#6-mmm-regional-e-outros-canais) |

## Tabelas de origem

![Visão geral das áreas](../docs/diagramas/00_visao_geral.svg)

### 1. Catálogo e estoque
![Catálogo e estoque](../docs/diagramas/01_catalogo_estoque.svg)

### 2. Clientes e pedidos
![Clientes, pedidos e pós-venda](../docs/diagramas/02_clientes_pedidos.svg)

### 3. Tracking e atribuição
![Tracking do site e atribuição](../docs/diagramas/03_tracking_atribuicao.svg)

### 4. Meta Ads
![Meta Ads](../docs/diagramas/04_meta_ads.svg)

### 5. Google Ads
![Google Ads](../docs/diagramas/05_google_ads.svg)

### 6. MMM regional e outros canais
![MMM regional, testes geográficos e outros canais](../docs/diagramas/06_mmm_outros_canais.svg)
