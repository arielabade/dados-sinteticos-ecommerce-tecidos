# Modeling notebooks

Each notebook answers a business question. They read from the repository's MySQL (`make mysql`; connection in
[`utils_nb.py`](utils_nb.py)) and run in sequence with `make notebooks`.

| Notebook | Question | Areas used |
|---|---|---|
| [`01_previsao_demanda_receita`](01_previsao_demanda_receita.ipynb) | How many orders and how much revenue to expect in the coming months, including Black Friday 2026? Uses the demand lost to stockouts so as not to underestimate. | [1](#1-catalog-and-inventory) · dbt marts |
| [`02_churn_propensao_recompra`](02_churn_propensao_recompra.ipynb) | Which customers are most likely not to buy again within 90 days, and how much is it worth acting on them? | [2](#2-customers-and-orders) · [3](#3-tracking-and-attribution) |
| [`03_segmentacao_clientes`](03_segmentacao_clientes.ipynb) | What customer groups exist based on purchase behavior, and do they match the declared type? | [1](#1-catalog-and-inventory) · [2](#2-customers-and-orders) |
| [`04_ltv_preditivo`](04_ltv_preditivo.ipynb) | How much will each customer generate in 12 months, and what is the maximum CAC per channel? | [2](#2-customers-and-orders) · [3](#3-tracking-and-attribution) |
| [`05_incrementalidade_mmm`](05_incrementalidade_mmm.ipynb) | How many orders does each channel really drive? Geo test + calibrated MMM, compared with the generator's answer key. | [6](#6-regional-mmm-and-other-channels) |

## Tables the notebooks use

### 1. Catalog and inventory
![Catalog and inventory](../docs/diagramas/01_catalogo_estoque.svg)

### 2. Customers and orders
![Customers, orders and after-sales](../docs/diagramas/02_clientes_pedidos.svg)

### 3. Tracking and attribution
![Website tracking and attribution](../docs/diagramas/03_tracking_atribuicao.svg)

### 6. Regional MMM and other channels
![Regional MMM, geo tests and other channels](../docs/diagramas/06_mmm_outros_canais.svg)

The answer key used to validate notebook 05 (each channel's true effect) is in `data/ground_truth/` and is not loaded
into MySQL.
