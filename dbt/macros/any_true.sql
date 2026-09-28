{% macro any_true(expr) %}
  {%- if target.type == 'bigquery' -%}
    logical_or({{ expr }})
  {%- else -%}
    bool_or({{ expr }})
  {%- endif -%}
{% endmacro %}
