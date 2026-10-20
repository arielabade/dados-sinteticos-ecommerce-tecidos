{# Generic tests with no external dependency (the dbt-mysql 1.7 adapter does not run current dbt_utils). #}

{# Values outside [minimo, maximo] fail. Nulls are ignored (use not_null for them). #}
{% test valor_entre(model, column_name, minimo, maximo) %}
select {{ column_name }}
from {{ model }}
where {{ column_name }} is not null
  and ({{ column_name }} < {{ minimo }} or {{ column_name }} > {{ maximo }})
{% endtest %}

{# Rows where the expression is false fail (nulls in the expression are ignored). #}
{% test expressao_verdadeira(model, column_name, expressao) %}
select *
from {{ model }}
where not ({{ expressao }})
{% endtest %}
