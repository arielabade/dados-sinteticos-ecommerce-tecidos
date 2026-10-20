-- Channel dimension: buying channel (platform grain) and MMM grouping.
select canal_id, canal, canal_mmm, plataforma, tipo_investimento
from {{ source('raw', 'canais_midia') }}
