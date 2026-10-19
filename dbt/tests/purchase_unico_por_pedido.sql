-- Depois da limpeza, cada pedido rastreado tem exatamente um purchase.
select pedido_id, count(*) as n
from {{ ref('stg_eventos') }}
where event_name = 'purchase'
group by pedido_id
having count(*) <> 1
