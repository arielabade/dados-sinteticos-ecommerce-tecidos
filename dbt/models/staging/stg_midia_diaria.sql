-- Meta, Google, TikTok e afiliados empilhados no mesmo grão: data x plataforma x campanha
-- (para afiliados, a "campanha" é o parceiro).
select
    m.data,
    'meta'                          as plataforma,
    cp.campanha_id,
    cp.nome                         as campanha,
    cp.estrategia                   as tipo_campanha,
    sum(m.investimento)             as investimento,
    sum(m.impressoes)               as impressoes,
    sum(m.cliques_link)             as cliques,
    sum(m.compras)                  as conversoes_plataforma,
    sum(m.valor_compras)            as valor_conversao_plataforma
from {{ source('raw', 'meta_metricas_diarias') }} m
join {{ source('raw', 'meta_anuncios') }} a   on a.anuncio_id = m.anuncio_id
join {{ source('raw', 'meta_conjuntos') }} cj on cj.conjunto_id = a.conjunto_id
join {{ source('raw', 'meta_campanhas') }} cp on cp.campanha_id = cj.campanha_id
group by 1, 2, 3, 4, 5
union all
select
    g.data,
    'google',
    c.campanha_id,
    c.nome,
    case when c.campanha_marca = 1 then 'SEARCH_MARCA' else c.tipo_canal end,
    sum(g.investimento),
    sum(g.impressoes),
    sum(g.cliques),
    sum(g.conversoes),
    sum(g.valor_conversao)
from {{ source('raw', 'google_metricas_diarias') }} g
join {{ source('raw', 'google_grupos_anuncio') }} gr on gr.grupo_id = g.grupo_id
join {{ source('raw', 'google_campanhas') }} c       on c.campanha_id = gr.campanha_id
group by 1, 2, 3, 4, 5
union all
select
    t.data,
    'tiktok',
    c.campanha_id,
    c.nome,
    c.objetivo,
    sum(t.investimento),
    sum(t.impressoes),
    sum(t.cliques),
    sum(t.conversoes),
    sum(t.valor_conversoes)
from {{ source('raw', 'tiktok_metricas_diarias') }} t
join {{ source('raw', 'tiktok_campanhas') }} c on c.campanha_id = t.campanha_id
group by 1, 2, 3, 4, 5
union all
select
    a.data,
    'afiliados',
    p.parceiro_id,
    p.nome,
    upper(p.tipo),
    sum(a.investimento),
    null,
    sum(a.cliques),
    sum(a.pedidos_atribuidos),
    sum(a.receita_atribuida)
from {{ source('raw', 'afiliados_metricas_diarias') }} a
join {{ source('raw', 'afiliados_parceiros') }} p on p.parceiro_id = a.parceiro_id
group by 1, 2, 3, 4, 5
