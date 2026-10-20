-- Normalized UTMs (lowercase, no spaces) + Google campaign type via the click.
select
    s.sessao_id,
    s.client_id,
    s.cliente_id,
    s.iniciada_em                                  as iniciada_em_utc,
    {{ para_local('s.iniciada_em') }}              as iniciada_em_local,
    date({{ para_local('s.iniciada_em') }})        as data_local,
    s.duracao_seg,
    s.dispositivo,
    s.uf,
    s.landing_page,
    s.referrer,
    nullif(lower(trim(s.utm_source)), '')          as utm_source_norm,
    nullif(lower(trim(s.utm_medium)), '')          as utm_medium_norm,
    s.utm_campaign,
    s.utm_content,
    s.utm_term,
    s.gclid,
    s.fbclid,
    s.fbp,
    s.fbc,
    s.clique_id,
    c.plataforma                                   as plataforma_clique,
    ma.conjunto_id                                 as meta_conjunto_id,
    mc.campanha_id                                 as meta_campanha_id,
    c.google_grupo_id,
    gg.campanha_id                                 as google_campanha_id,
    gc.tipo_canal                                  as tipo_campanha_google,
    s.consent_analytics_storage,
    s.consent_ad_storage,
    s.consent_ad_user_data,
    s.primeira_visita,
    s.engajada
from {{ source('raw', 'sessoes') }} s
left join {{ source('raw', 'cliques_midia') }} c          on c.clique_id = s.clique_id
left join {{ source('raw', 'meta_anuncios') }} ma         on ma.anuncio_id = c.meta_anuncio_id
left join {{ source('raw', 'meta_conjuntos') }} mc        on mc.conjunto_id = ma.conjunto_id
left join {{ source('raw', 'google_grupos_anuncio') }} gg on gg.grupo_id = c.google_grupo_id
left join {{ source('raw', 'google_campanhas') }} gc      on gc.campanha_id = gg.campanha_id
