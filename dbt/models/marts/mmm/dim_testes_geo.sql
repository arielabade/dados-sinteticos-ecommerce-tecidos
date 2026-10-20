-- Geographic tests, one row per (test, state), with the group and the windows.
select t.teste_id, t.nome, t.canal_id, t.canal, t.canal_mmm, t.tipo_mudanca, t.multiplicador_investimento,
       t.pre_inicio, t.inicio, t.fim, t.resfriamento_fim, t.metrica_principal,
       g.uf, g.grupo
from {{ ref('stg_testes_geo') }} t
join {{ ref('stg_testes_geo_regioes') }} g on g.teste_id = t.teste_id
