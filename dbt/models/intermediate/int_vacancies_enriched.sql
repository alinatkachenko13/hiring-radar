-- Роль — фильтр релевантности по тайтлу, не косметика и не role_query.
-- Поиск Adzuna ищет вхождение в описание, поэтому в выдаче Angular и аудит.
-- Приоритет: более узкая роль раньше. Нет совпадения → other, на витрину не попадает.

with base as (
    select
        *,
        lower(coalesce(title, '')) as title_l,
        lower(
            coalesce(title, '') || ' ' || coalesce(description, '')
        ) as search_text
    from {{ ref('int_vacancies_deduped') }}
),

classified as (
    select
        source_id,
        observed_on,
        country_code,
        role_queries,
        title,
        description,
        posted_at,
        company_name,
        salary_min,
        salary_max,
        is_salary_disclosed,
        contract_type,
        contract_time,
        location_display_name,
        location_region,
        location_city,
        latitude,
        longitude,
        redirect_url,
        case
            when title_l like '%analytics engineer%'
                then 'analytics_engineer'
            when title_l like '%machine learning engineer%'
              or title_l like '%ml engineer%'
              or title_l like '%mlops%'
                then 'ml_engineer'
            when title_l like '%data scientist%'
              or title_l like '%datenwissenschaftler%'
                then 'data_scientist'
            when title_l like '%data engineer%'
              or title_l like '%data engineering%'
              or title_l like '%dateningenieur%'
                then 'data_engineer'
            when title_l like '%data analyst%'
              or title_l like '%data analytics%'
              or title_l like '%data quality%'
              or title_l like '%data governance%'
              or title_l like '%datenanalyst%'
              or title_l like '%data analist%'
                then 'data_analyst'
            else 'other'
        end as role_key,
        case
            when title_l like '%intern%'
              or title_l like '%internship%'
              or title_l like '%werkstudent%'
              or title_l like '%working student%'
              or title_l like '%graduate%'
              or title_l like '%apprentice%'
              or title_l like '%trainee%'
                then 'intern'
            when title_l like '%junior%'
              or title_l like '%jr.%'
              or title_l like '% jr %'
              or title_l like 'jr %'
                then 'junior'
            when title_l like '%principal%'
              or title_l like '%staff %'
              or title_l like 'staff %'
              or title_l like '% lead%'
              or title_l like 'lead %'
              or title_l like '%head of%'
              or title_l like '%director%'
              or title_l like '%manager%'
                then 'lead'
            when title_l like '%senior%'
              or title_l like '%sr.%'
              or title_l like '% sr %'
                then 'senior'
            else 'mid'
        end as grade,
        case
            when search_text like '%hybrid%' then 'hybrid'
            when search_text like '%remote%'
              or search_text like '%work from home%'
              or search_text like '%wfh%'
              or search_text like '%home office%'
                then 'remote'
            else 'unknown'
        end as remote_type
    from base
)

select
    *,
    role_key != 'other' as is_relevant,
    remote_type in ('remote', 'hybrid') as is_remote,
    {{ sk([
        "lower(coalesce(company_name, ''))",
        "lower(coalesce(title, ''))",
        "country_code"
    ]) }} as position_id
from classified
