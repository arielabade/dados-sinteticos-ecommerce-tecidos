-- Platforms' geographic report: one record per day, channel and state.
select
    m.data,
    m.canal_id,
    c.canal,
    c.canal_mmm,
    c.tipo_investimento,
    m.uf,
    m.investimento,
    m.impressoes,
    m.cliques,
    m.conversoes_plataforma
from {{ source('raw', 'midia_regional_diaria') }} m
join {{ ref('stg_canais_midia') }} c on c.canal_id = m.canal_id
