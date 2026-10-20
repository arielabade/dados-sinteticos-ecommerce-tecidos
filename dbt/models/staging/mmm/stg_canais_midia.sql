-- Dimensão de canais: canal de compra (grão da plataforma) e agrupamento do MMM.
select canal_id, canal, canal_mmm, plataforma, tipo_investimento
from {{ source('raw', 'canais_midia') }}
