-- Одна вакансия в одну дату наблюдения, сколько бы запросов её ни вернули.
-- Атрибуты должны совпадать между ролями; any_value — на случай расхождения.

select
    source_id,
    observed_on,
    {{ list_roles('role_query') }} as role_queries,
    any_value(country_code) as country_code,
    any_value(title) as title,
    any_value(description) as description,
    any_value(posted_at) as posted_at,
    any_value(company_name) as company_name,
    any_value(salary_min) as salary_min,
    any_value(salary_max) as salary_max,
    any_value(is_salary_disclosed) as is_salary_disclosed,
    any_value(contract_type) as contract_type,
    any_value(contract_time) as contract_time,
    any_value(location_display_name) as location_display_name,
    any_value(location_region) as location_region,
    any_value(location_city) as location_city,
    any_value(latitude) as latitude,
    any_value(longitude) as longitude,
    any_value(redirect_url) as redirect_url,
    -- Одну вакансию возвращают несколько запросов. Достаточно одного
    -- переписного: значит, в этот день мы видели весь запас её пары.
    {{ any_true('is_census') }} as seen_in_census
from {{ ref('stg_vacancies') }}
group by source_id, observed_on
