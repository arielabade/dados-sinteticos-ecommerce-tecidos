{#
  Channel grouping from what is observable in the session (UTM, click id,
  referrer). Same rule as the generator (gerador/tracking.py::canal_padrao).
  Expects the columns: utm_source_norm, utm_medium_norm, referrer, gclid, fbclid,
  tipo_campanha_google (via click -> ad group -> campaign).
#}
{% macro canal_padrao() -%}
case
    when gclid is not null then
        case tipo_campanha_google
            when 'SHOPPING' then 'Paid Shopping'
            when 'PERFORMANCE_MAX' then 'Cross-network'
            when 'DEMAND_GEN' then 'Paid Video'
            else 'Paid Search' end
    when fbclid is not null
      or (utm_source_norm in ('fb','ig','an','facebook','instagram','igshopping','tiktok','tiktok_ads')
          and utm_medium_norm in ('paid_social','paid','cpc')) then 'Paid Social'
    when utm_source_norm = 'google' and utm_medium_norm = 'cpc' then 'Paid Search'
    when utm_medium_norm in ('afiliados','affiliate') then 'Affiliates'
    when utm_medium_norm = 'email' or utm_source_norm in ('newsletter','email','rdstation') then 'Email'
    when utm_source_norm in ('whatsapp','wpp') then 'WhatsApp'
    when utm_medium_norm in ('social','bio') or utm_source_norm in ('ig','instagram','linktree')
      or referrer regexp 'instagram\\.com|facebook\\.com|pinterest\\.com|tiktok\\.com|youtube\\.com' then 'Organic Social'
    when referrer regexp 'google\\.|bing\\.com|duckduckgo\\.com|search\\.yahoo' then 'Organic Search'
    when referrer is not null then 'Referral'
    when utm_source_norm is null and utm_medium_norm is null then 'Direct'
    else 'Unassigned'
end
{%- endmacro %}

{% macro para_local(coluna) -%}
date_add({{ coluna }}, interval {{ var('utc_offset_horas') }} hour)
{%- endmacro %}

{% macro para_utc(coluna) -%}
date_sub({{ coluna }}, interval {{ var('utc_offset_horas') }} hour)
{%- endmacro %}
