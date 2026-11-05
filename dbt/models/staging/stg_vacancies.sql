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
    max_days_old,
    -- Перепись — это окна нет и пара собрана до конца. Без окна в выдаче весь
    -- запас, и пропажа объявления означает, что его сняли, а не что оно
    -- состарилось. Но запас, упёршийся в потолок выдачи (truncated), полным не
    -- считается: часть объявлений в него просто не попала. Пустой pair_status у
    -- старых партиций: тогда грузились только полные дни.
    pair_status,
    (max_days_old is null and coalesce(pair_status, 'complete') = 'complete') as is_census,
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
  -- Дни до начала истории отсекаются здесь, чтобы ни одна модель ниже
  -- не знала про пробный сбор. Переменная в dbt_project.yml.
  and run_date >= date '{{ var("history_starts_on") }}'
