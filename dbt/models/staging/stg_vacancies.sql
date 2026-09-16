{{ config(alias='stg_vacancies') }}

-- Имена полей уже внутренние. Adzuna остаётся только в salary_is_predicted,
-- и только здесь: правило раскрытия живёт в одном месте.
-- vacancy_json на этот слой не поднимается.

select
    run_date as observed_on,
    extracted_at,
    country as country_code,
    role_query,
    page,
    count_reported,
    source_id,
    trim(title) as title,
    description,
    posted_at,
    nullif(trim(company_name), '') as company_name,
    salary_min,
    salary_max,
    salary_is_predicted,
    (
        salary_is_predicted = '0'
        and salary_min is not null
    ) as is_salary_disclosed,
    contract_type,
    contract_time,
    location_display_name,
    location_region,
    location_city,
    latitude,
    longitude,
    redirect_url,
    source_file
from {{ source('raw', 'adzuna_results') }}
where source_id is not null
