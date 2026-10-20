-- Register of the geographic tests with the channel tested.
select t.teste_id, t.nome, t.canal_id, c.canal, t.canal_mmm, t.tipo_mudanca, t.multiplicador_investimento,
       t.pre_inicio, t.inicio, t.fim, t.resfriamento_fim, t.metrica_principal, t.descricao
from {{ source('raw', 'testes_geo') }} t
join {{ ref('stg_canais_midia') }} c on c.canal_id = t.canal_id
