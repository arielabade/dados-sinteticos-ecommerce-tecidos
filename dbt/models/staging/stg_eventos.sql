-- Event log cleanup:
--   1) removes duplicates by event_id (the same event arriving from the browser and the
--      server, or a network retry), keeping the first occurrence;
--   2) for purchases, keeps one event per transaction_id (reloading the thank-you
--      page generates a new event_id for the same purchase);
--   3) fixes the time zone of container v2.3 (it wrote local time instead of UTC).
--
-- Performance: MIN(evento_id) per event_id uses the ix_eventos_event_id index
-- (event_id, evento_id) without sorting the whole table on disk. evento_id follows
-- arrival order within the session, so the smallest id is the first occurrence.
-- A ROW_NUMBER() window over the full ~15 million rows would require
-- several GB of temporary files.
with primeiros as (
    select min(evento_id) as evento_id
    from {{ source('raw', 'eventos') }}
    group by event_id
),
purchase_repetido as (
    select evento_id
    from (
        select evento_id,
               row_number() over (partition by transaction_id order by evento_id) as rn
        from {{ source('raw', 'eventos') }}
        where event_name = 'purchase'
    ) x
    where rn > 1
)
select
    e.evento_id,
    e.event_id,
    e.sessao_id,
    e.cliente_id,
    e.event_name,
    case when e.versao_container = 'v2.3'
         then date_add(e.event_timestamp, interval 3 hour)
         else e.event_timestamp end                       as event_timestamp_utc,
    case when e.versao_container = 'v2.3'
         then e.event_timestamp
         else {{ para_local('e.event_timestamp') }} end   as event_timestamp_local,
    e.page_location,
    e.variante_id,
    e.quantidade,
    e.valor,
    e.moeda,
    e.transaction_id,
    e.pedido_id,
    e.fonte,
    e.versao_container
from {{ source('raw', 'eventos') }} e
join primeiros p on p.evento_id = e.evento_id
where e.evento_id not in (select evento_id from purchase_repetido)
