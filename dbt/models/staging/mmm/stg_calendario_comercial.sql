-- Calendário de marketing: feriados nacionais, datas comerciais e promoções da loja.
select
    data,
    dia_semana,
    feriado_nacional = 1                         as feriado_nacional,
    nome_feriado,
    evento_comercial,
    promocao_loja = 1                            as promocao_loja,
    nome_promocao,
    evento_comercial like '%black_friday%'       as evento_black_friday,
    evento_comercial like '%natal%'              as evento_natal,
    evento_comercial like '%dia_das_maes%'       as evento_dia_das_maes,
    evento_comercial is not null                 as evento_qualquer
from {{ source('raw', 'calendario_comercial') }}
