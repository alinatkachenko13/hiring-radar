{% macro as_text(expr) %}
  {%- if target.type == 'bigquery' -%}
    cast({{ expr }} as string)
  {%- else -%}
    cast({{ expr }} as varchar)
  {%- endif -%}
{% endmacro %}

{% macro sk(fields) %}
  {%- set parts = [] -%}
  {%- for field in fields -%}
    {%- do parts.append("coalesce(" ~ as_text(field) ~ ", '')") -%}
  {%- endfor -%}
  {%- if target.type == 'bigquery' -%}
    to_hex(md5(concat({{ parts | join(", '|', ") }})))
  {%- else -%}
    md5({{ parts | join(" || '|' || ") }})
  {%- endif -%}
{% endmacro %}
