-- Paid clicks >= orders attributed by last click to the same channel, per day.
-- 'Paid Social' combines Meta and TikTok (the website's channel grouping does not separate them).
-- E-mail is left out: e-mail sessions also come from transactional e-mails, which
-- are not in crm_disparos, so there is not 1 campaign click per session.
with cliques as (
    select data,
           case when canal_mmm in ('meta', 'tiktok') then 'Paid Social'
                when canal_mmm = 'google_search' then 'Paid Search'
                when canal_mmm = 'google_shopping' then 'Shopping'
                when canal_mmm = 'youtube' then 'Paid Video'
                when canal_mmm = 'afiliados' then 'Affiliates' end as grupo,
           sum(cliques) as cliques
    from {{ ref('fct_mmm_midia_canal_regiao_diario') }}
    where canal_mmm <> 'email_crm'
    group by 1, 2
),
atrib as (
    select data_pedido as data,
           case when canal_last_click in ('Paid Shopping', 'Cross-network') then 'Shopping'
                else canal_last_click end as grupo,
           count(*) as pedidos
    from {{ ref('fct_pedidos') }}
    where pago and canal_last_click in ('Paid Social', 'Paid Search', 'Paid Shopping', 'Cross-network',
                                        'Paid Video', 'Affiliates')
    group by 1, 2
)
select a.data, a.grupo, a.pedidos, coalesce(c.cliques, 0) as cliques
from atrib a
left join cliques c on c.data = a.data and c.grupo = a.grupo
where a.pedidos > coalesce(c.cliques, 0)
