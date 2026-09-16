-- Один источник для Looker Studio: релевантные вакансии + подписи стран и ролей.
-- Фильтры дашборда (страна, роль, контракт, дата) работают по этой таблице,
-- а не по заранее свёрнутым mart_*: там уже нет разреза по контракту.

select
    f.observed_on,
    f.source_id,
    f.position_id,
    f.country_code,
    c.country_name,
    f.role_key,
    r.role_name,
    f.title,
    f.company_name,
    f.location_region,
    f.location_city,
    case
        when f.country_code = 'gb' and f.location_region = 'London' then 'London'
        when f.country_code = 'gb' then 'Rest of GB'
        when f.country_code = 'ca' and lower(coalesce(f.location_city, '')) like '%toronto%' then 'Toronto'
        when f.country_code = 'ca' and lower(coalesce(f.location_city, '')) like '%vancouver%' then 'Vancouver'
        else f.location_city
    end as city_group,
    f.salary_min,
    f.salary_max,
    f.salary_mid,
    f.is_salary_disclosed,
    f.contract_type,
    f.contract_time,
    f.grade,
    f.remote_type,
    f.is_remote,
    f.is_new,
    f.is_gone,
    not f.is_gone as is_open,
    f.days_open,
    f.days_since_posted,
    c.currency,
    c.show_salary
from {{ ref('fct_vacancy_daily') }} as f
left join {{ ref('dim_country') }} as c
    on f.country_code = c.country_code
left join {{ ref('dim_role') }} as r
    on f.role_key = r.role_key
where f.is_relevant
