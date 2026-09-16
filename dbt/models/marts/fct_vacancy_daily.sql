select
    {{ sk(['d.source_id', 'd.observed_on']) }} as vacancy_daily_sk,
    d.source_id,
    d.observed_on,
    v.vacancy_sk,
    {{ sk(["lower(coalesce(d.company_name, ''))"]) }} as company_sk,
    {{ sk(['d.country_code', 'd.location_region', 'd.location_city']) }} as location_sk,
    d.country_code,
    d.role_key,
    d.position_id,
    d.title,
    d.company_name,
    d.location_region,
    d.location_city,
    d.salary_min,
    d.salary_max,
    d.salary_mid,
    d.is_salary_disclosed,
    d.contract_type,
    d.contract_time,
    d.grade,
    d.remote_type,
    d.is_remote,
    d.is_relevant,
    d.is_new,
    d.is_gone,
    d.days_open,
    d.days_since_posted,
    d.first_seen_on,
    d.posted_at,
    d.redirect_url,
    d.role_queries
from {{ ref('int_vacancy_daily') }} as d
left join {{ ref('dim_vacancy') }} as v
    on d.source_id = v.source_id
    and d.observed_on >= v.valid_from
    and (v.valid_to is null or d.observed_on < v.valid_to)
