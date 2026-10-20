-- States served by the store, with macro-region and population weight.
select uf, nome, macrorregiao, sigla_macrorregiao, peso_populacional, entrega_disponivel = 1 as entrega_disponivel
from {{ source('raw', 'regioes') }}
