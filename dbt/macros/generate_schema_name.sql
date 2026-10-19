{# Em MySQL schema = database. Gera tecidos_staging, tecidos_intermediate, tecidos_marts. #}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}{{ target.schema }}{%- else -%}tecidos_{{ custom_schema_name | trim }}{%- endif -%}
{%- endmacro %}
