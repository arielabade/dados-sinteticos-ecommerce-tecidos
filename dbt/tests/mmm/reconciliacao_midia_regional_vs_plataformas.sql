-- The sum over states of the geographic report matches each platform's national report (to the cent).
with regional as (
    select data, plataforma, sum(investimento) inv
    from {{ ref('stg_midia_regional_diaria') }} m
    join {{ ref('stg_canais_midia') }} c using (canal_id)
    group by 1, 2
),
nacional as (
    select data, 'meta' plataforma, sum(investimento) inv from {{ source('raw', 'meta_metricas_diarias') }} group by 1
    union all
    select data, 'google', sum(investimento) from {{ source('raw', 'google_metricas_diarias') }} group by 1
    union all
    select data, 'tiktok', sum(investimento) from {{ source('raw', 'tiktok_metricas_diarias') }} group by 1
    union all
    select data, 'afiliados', sum(investimento) from {{ source('raw', 'afiliados_metricas_diarias') }} group by 1
    union all
    select data, 'crm', sum(custo) from {{ source('raw', 'crm_disparos') }} group by 1
)
select n.data, n.plataforma, n.inv as nacional, r.inv as regional
from nacional n
left join regional r on r.data = n.data and r.plataforma = n.plataforma
where n.inv > 0 and abs(n.inv - coalesce(r.inv, 0)) > 0.011
