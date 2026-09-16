{% macro list_roles(expr) %}
  {%- if target.type == 'bigquery' -%}
    string_agg(distinct {{ expr }}, ', ' order by {{ expr }})
  {%- else -%}
    string_agg(distinct {{ expr }}, ', ')
  {%- endif -%}
{% endmacro %}

{% macro median_expr(expr) %}
  {%- if target.type == 'bigquery' -%}
    approx_quantiles({{ expr }}, 4)[offset(2)]
  {%- else -%}
    median({{ expr }})
  {%- endif -%}
{% endmacro %}

{% macro percentile_expr(expr, p) %}
  {%- if target.type == 'bigquery' -%}
    {%- if p == 25 -%}
      approx_quantiles({{ expr }}, 4)[offset(1)]
    {%- elif p == 75 -%}
      approx_quantiles({{ expr }}, 4)[offset(3)]
    {%- else -%}
      approx_quantiles({{ expr }}, 4)[offset(2)]
    {%- endif -%}
  {%- else -%}
    quantile({{ expr }}, {{ p / 100 }})
  {%- endif -%}
{% endmacro %}
