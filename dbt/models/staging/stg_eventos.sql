-- Limpeza do log de eventos:
--   1) remove duplicatas pelo event_id (mesmo evento chegando do navegador e do
--      servidor, ou retry de rede), mantendo a primeira ocorrência;
--   2) em purchase, mantém um evento por transaction_id (a recarga da página de
--      obrigado gera event_id novo para a mesma compra);
--   3) corrige o fuso do container v2.3 (gravou horário local em vez de UTC).
--
-- Desempenho: MIN(evento_id) por event_id usa o índice ix_eventos_event_id
-- (event_id, evento_id) sem ordenar a tabela inteira em disco. evento_id segue a
-- ordem de chegada dentro da sessão, então o menor id é a primeira ocorrência.
-- Uma janela ROW_NUMBER() sobre os ~15 milhões de linhas completas exigiria
-- vários GB de arquivo temporário.
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
