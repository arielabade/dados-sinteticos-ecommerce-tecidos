-- Grain: date x platform x campaign. Spend always next to the conversions
-- reported by the platform and those attributed by the website (paid orders).
with atrib as (
    select
        p.data_pedido as data,
        case when a.meta_campanha_id is not null then 'meta' else 'google' end as plataforma,
        coalesce(a.meta_campanha_id, a.google_campanha_id) as campanha_id,
        sum(case when a.modelo = 'last_click'  then a.peso else 0 end)              as pedidos_last_click,
        sum(case when a.modelo = 'last_click'  then a.receita_atribuida else 0 end) as receita_last_click,
        sum(case when a.modelo = 'data_driven' then a.peso else 0 end)              as pedidos_data_driven,
        sum(case when a.modelo = 'data_driven' then a.receita_atribuida else 0 end) as receita_data_driven
    from {{ source('raw', 'atribuicoes') }} a
    join {{ ref('stg_pedidos') }} p on p.pedido_id = a.pedido_id and p.pago
    where a.meta_campanha_id is not null or a.google_campanha_id is not null
    group by 1, 2, 3
)
select
    m.data,
    m.plataforma,
    m.campanha_id,
    m.campanha,
    m.tipo_campanha,
    m.investimento,
    m.impressoes,
    m.cliques,
    m.conversoes_plataforma,
    m.valor_conversao_plataforma,
    coalesce(a.pedidos_last_click, 0)   as pedidos_last_click,
    coalesce(a.receita_last_click, 0)   as receita_last_click,
    coalesce(a.pedidos_data_driven, 0)  as pedidos_data_driven,
    coalesce(a.receita_data_driven, 0)  as receita_data_driven
from {{ ref('stg_midia_diaria') }} m
left join atrib a on a.data = m.data and a.plataforma = m.plataforma and a.campanha_id = m.campanha_id
