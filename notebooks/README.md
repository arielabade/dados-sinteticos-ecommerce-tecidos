# Notebooks de modelagem

Cada notebook responde uma pergunta de negócio. Eles leem do MySQL do repositório (`make mysql`; conexão em
[`utils_nb.py`](utils_nb.py)) e rodam em sequência com `make notebooks`.

| Notebook | Pergunta | Áreas usadas |
|---|---|---|
| [`01_previsao_demanda_receita`](01_previsao_demanda_receita.ipynb) | Quantos pedidos e quanta receita esperar nos próximos meses, incluindo a Black Friday de 2026? Usa a demanda perdida por ruptura para não subestimar. | [1](#1-catálogo-e-estoque) · marts do dbt |
| [`02_churn_propensao_recompra`](02_churn_propensao_recompra.ipynb) | Quais clientes têm mais chance de não voltar a comprar em 90 dias, e quanto vale agir sobre eles? | [2](#2-clientes-e-pedidos) · [3](#3-tracking-e-atribuição) |
| [`03_segmentacao_clientes`](03_segmentacao_clientes.ipynb) | Que grupos de clientes existem pelo comportamento de compra, e eles batem com o tipo declarado? | [1](#1-catálogo-e-estoque) · [2](#2-clientes-e-pedidos) |
| [`04_ltv_preditivo`](04_ltv_preditivo.ipynb) | Quanto cada cliente vai gerar em 12 meses e qual o CAC máximo por canal? | [2](#2-clientes-e-pedidos) · [3](#3-tracking-e-atribuição) |
| [`05_incrementalidade_mmm`](05_incrementalidade_mmm.ipynb) | Quantos pedidos cada canal gera de verdade? Teste geográfico + MMM calibrado, comparados com o gabarito do gerador. | [6](#6-mmm-regional-e-outros-canais) |

## Tabelas que os notebooks usam

### 1. Catálogo e estoque
![Catálogo e estoque](../docs/diagramas/01_catalogo_estoque.svg)

### 2. Clientes e pedidos
![Clientes, pedidos e pós-venda](../docs/diagramas/02_clientes_pedidos.svg)

### 3. Tracking e atribuição
![Tracking do site e atribuição](../docs/diagramas/03_tracking_atribuicao.svg)

### 6. MMM regional e outros canais
![MMM regional, testes geográficos e outros canais](../docs/diagramas/06_mmm_outros_canais.svg)

O gabarito usado na validação do notebook 05 (efeito real de cada canal) fica em `data/ground_truth/` e não vai para o
MySQL.
