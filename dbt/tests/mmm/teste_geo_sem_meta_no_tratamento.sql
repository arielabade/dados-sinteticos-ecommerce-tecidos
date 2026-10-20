-- During the test, the tested channel cannot have spend in the treatment states.
select m.data, m.uf, m.canal, m.investimento
from {{ ref('fct_mmm_midia_canal_regiao_diario') }} m
join {{ ref('dim_testes_geo') }} t
  on t.uf = m.uf and t.grupo = 'tratamento' and t.canal_mmm = m.canal_mmm
 and m.data between t.inicio and t.fim
where t.multiplicador_investimento = 0 and m.investimento > 0
