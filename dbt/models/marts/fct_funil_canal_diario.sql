select
    data_local as data,
    canal,
    dispositivo,
    count(*)                     as sessoes,
    sum(engajada)                as sessoes_engajadas,
    sum(viu_produto)             as sessoes_view_item,
    sum(adicionou_carrinho)      as sessoes_add_to_cart,
    sum(iniciou_checkout)        as sessoes_begin_checkout,
    sum(informou_pagamento)      as sessoes_add_payment_info,
    sum(comprou)                 as sessoes_purchase
from {{ ref('int_sessoes_funil') }}
group by 1, 2, 3
