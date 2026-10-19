-- Uma linha por sessão: canal padrão + etapas do funil.
-- Lê a tabela bruta em vez de stg_eventos: as etapas são MAX() e não mudam com
-- eventos duplicados, e page_views conta event_id distintos. Passar pela view
-- deduplicada levaria horas nos ~15 milhões de eventos.
with ev as (
    select
        sessao_id,
        max(event_name = 'view_item')        as viu_produto,
        max(event_name = 'add_to_cart')      as adicionou_carrinho,
        max(event_name = 'begin_checkout')   as iniciou_checkout,
        max(event_name = 'add_payment_info') as informou_pagamento,
        max(event_name = 'purchase')         as comprou,
        count(distinct case when event_name = 'page_view' then event_id end) as page_views
    from {{ source('raw', 'eventos') }}
    group by sessao_id
)
select
    s.sessao_id,
    s.data_local,
    s.iniciada_em_utc,
    s.client_id,
    s.cliente_id,
    s.dispositivo,
    s.uf,
    {{ canal_padrao() }} as canal,
    s.meta_campanha_id,
    s.google_campanha_id,
    s.consent_analytics_storage,
    s.consent_ad_storage,
    s.engajada,
    coalesce(ev.page_views, 0)          as page_views,
    coalesce(ev.viu_produto, 0)         as viu_produto,
    coalesce(ev.adicionou_carrinho, 0)  as adicionou_carrinho,
    coalesce(ev.iniciou_checkout, 0)    as iniciou_checkout,
    coalesce(ev.informou_pagamento, 0)  as informou_pagamento,
    coalesce(ev.comprou, 0)             as comprou
from {{ ref('stg_sessoes') }} s
left join ev on ev.sessao_id = s.sessao_id
