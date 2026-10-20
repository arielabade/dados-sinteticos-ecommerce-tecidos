{# Simple equivalent of dbt_utils.unique_combination_of_columns, with no external dependency. #}
{% test dbt_utils_like_unique_combination(model, columns) %}
select {{ columns | join(', ') }}, count(*) as n
from {{ model }}
group by {{ columns | join(', ') }}
having count(*) > 1
{% endtest %}
