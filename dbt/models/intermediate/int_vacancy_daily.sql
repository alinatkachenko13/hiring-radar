-- Гранулярность факта: объявление × дата наблюдения.
-- Пропавшие добавляются отдельной строкой в день, когда их не стало в выдаче.
-- Если страна в этот день не пришла совсем, gone по ней не считаем:
-- это сбой сбора, а не закрытие рынка.

with present as (
    select * from {{ ref('int_vacancies_enriched') }}
),

observation_dates as (
    select distinct observed_on from present
),

date_seq as (
    select
        observed_on,
        lag(observed_on) over (order by observed_on) as prev_on
    from observation_dates
),

countries_on_date as (
    select distinct
        observed_on,
        country_code
    from present
),

first_seen as (
    select
        source_id,
        min(observed_on) as first_seen_on
    from present
    group by source_id
),

gone as (
    select
        p.source_id,
        d.observed_on,
        p.country_code,
        p.role_queries,
        p.title,
        p.description,
        p.posted_at,
        p.company_name,
        p.salary_min,
        p.salary_max,
        p.is_salary_disclosed,
        p.contract_type,
        p.contract_time,
        p.location_display_name,
        p.location_region,
        p.location_city,
        p.latitude,
        p.longitude,
        p.redirect_url,
        p.role_key,
        p.grade,
        p.remote_type,
        p.is_relevant,
        p.is_remote,
        p.position_id,
        false as is_new,
        true as is_gone,
        f.first_seen_on,
        d.prev_on as last_present_on
    from date_seq as d
    inner join present as p
        on p.observed_on = d.prev_on
    inner join countries_on_date as today
        on today.observed_on = d.observed_on
        and today.country_code = p.country_code
    inner join first_seen as f
        on f.source_id = p.source_id
    left join present as curr
        on curr.source_id = p.source_id
        and curr.observed_on = d.observed_on
    where d.prev_on is not null
      and curr.source_id is null
),

present_flagged as (
    select
        p.source_id,
        p.observed_on,
        p.country_code,
        p.role_queries,
        p.title,
        p.description,
        p.posted_at,
        p.company_name,
        p.salary_min,
        p.salary_max,
        p.is_salary_disclosed,
        p.contract_type,
        p.contract_time,
        p.location_display_name,
        p.location_region,
        p.location_city,
        p.latitude,
        p.longitude,
        p.redirect_url,
        p.role_key,
        p.grade,
        p.remote_type,
        p.is_relevant,
        p.is_remote,
        p.position_id,
        p.observed_on = f.first_seen_on as is_new,
        false as is_gone,
        f.first_seen_on,
        p.observed_on as last_present_on
    from present as p
    inner join first_seen as f
        on f.source_id = p.source_id
),

unioned as (
    select * from present_flagged
    union all
    select * from gone
)

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
    coalesce((salary_min + salary_max) / 2, salary_min) as salary_mid,
    is_salary_disclosed,
    contract_type,
    contract_time,
    location_display_name,
    location_region,
    location_city,
    latitude,
    longitude,
    redirect_url,
    role_key,
    grade,
    remote_type,
    is_relevant,
    is_remote,
    position_id,
    is_new,
    is_gone,
    first_seen_on,
    {{ days_between('first_seen_on', 'last_present_on') }} + 1 as days_open,
    case
        when posted_at is null then null
        else greatest({{ days_between('posted_at', 'last_present_on') }}, 0)
    end as days_since_posted
from unioned
