select teste_id, uf, grupo
from {{ source('raw', 'testes_geo_regioes') }}
