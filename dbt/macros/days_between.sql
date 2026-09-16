{% macro days_between(start_date, end_date) %}
  {%- if target.type == 'bigquery' -%}
    date_diff(date({{ end_date }}), date({{ start_date }}), day)
  {%- else -%}
    datediff('day', date({{ start_date }}), date({{ end_date }}))
  {%- endif -%}
{% endmacro %}
