{# Testes genéricos sem dependência externa (o adaptador dbt-mysql 1.7 não roda dbt_utils atual). #}

{# Valores fora de [minimo, maximo] falham. Nulos são ignorados (use not_null para eles). #}
{% test valor_entre(model, column_name, minimo, maximo) %}
select {{ column_name }}
from {{ model }}
where {{ column_name }} is not null
  and ({{ column_name }} < {{ minimo }} or {{ column_name }} > {{ maximo }})
{% endtest %}

{# Linhas em que a expressão é falsa falham (nulos na expressão são ignorados). #}
{% test expressao_verdadeira(model, column_name, expressao) %}
select *
from {{ model }}
where not ({{ expressao }})
{% endtest %}
