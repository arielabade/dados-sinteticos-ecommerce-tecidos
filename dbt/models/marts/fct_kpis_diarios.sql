-- KPIs de negócio por dia: receita, pedidos, novos clientes, investimento, MER e CAC.
with ped as (
    select data_pedido as data,
           count(*)                         as pedidos,
           sum(total)                       as receita,
           sum(margem_bruta)                as margem_bruta,
           sum(primeira_compra)             as novos_clientes
    from {{ ref('fct_pedidos') }}
    where pago
    group by 1
),
midia as (
    select data,
           sum(investimento)                                        as investimento,
           sum(case when plataforma = 'meta' then investimento end)   as investimento_meta,
           sum(case when plataforma = 'google' then investimento end) as investimento_google,
           sum(case when plataforma = 'tiktok' then investimento end) as investimento_tiktok,
           sum(case when plataforma = 'afiliados' then investimento end) as investimento_afiliados
    from {{ ref('stg_midia_diaria') }}
    group by 1
),
sess as (
    select data_local as data, count(*) as sessoes from {{ ref('stg_sessoes') }} group by 1
)
select
    ped.data,
    ped.pedidos,
    ped.receita,
    ped.margem_bruta,
    ped.novos_clientes,
    coalesce(m.investimento, 0)        as investimento,
    coalesce(m.investimento_meta, 0)   as investimento_meta,
    coalesce(m.investimento_google, 0) as investimento_google,
    coalesce(m.investimento_tiktok, 0) as investimento_tiktok,
    coalesce(m.investimento_afiliados, 0) as investimento_afiliados,
    s.sessoes,
    ped.receita / nullif(m.investimento, 0)       as mer,
    m.investimento / nullif(ped.novos_clientes, 0) as cac_blended,
    ped.pedidos / nullif(s.sessoes, 0)             as taxa_conversao
from ped
left join midia m on m.data = ped.data
left join sess s  on s.data = ped.data
