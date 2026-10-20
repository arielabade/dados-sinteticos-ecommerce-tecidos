-- UFs atendidas pela loja, com macrorregião e peso populacional.
select uf, nome, macrorregiao, sigla_macrorregiao, peso_populacional, entrega_disponivel = 1 as entrega_disponivel
from {{ source('raw', 'regioes') }}
