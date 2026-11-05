-- Гранулярность факта: объявление × дата наблюдения.
-- Пропавшие добавляются отдельной строкой в день, когда стало ясно, что их сняли.
--
-- Три условия, без которых пропажа ничего не значит (NOTES, GAP 3-7):
--   1. вакансию видели переписью, то есть сбором без окна свежести. При сборе
--      с окном объявление уходит из выдачи по возрасту, а не потому, что снято;
--   2. та пара страна × роль, которой её видели, переписывалась и в день
--      пропажи, и в предыдущий: иначе это сбой сбора или смена режима пары, а
--      не рынок. Проверка по стране целиком не годится: когда одна пара страны
--      перешла на поток, остальные продолжают перепись, и все объявления
--      перешедшей пары разом выглядели бы снятыми;
--   3. объявления нет два наблюдения подряд, ни в переписи, ни в потоке. Выдача
--      шевелится во время сбора, и одиночный пропуск ничего не доказывает; а
--      объявление, которое сегодня видно в выдаче другой пары (страна собирает
--      часть ролей потоком), открыто, и второй строки за этот день у него быть
--      не может.

with present as (
    select * from {{ ref('int_vacancies_enriched') }}
),

observation_dates as (
    select distinct observed_on from present
),

date_seq as (
    select
        observed_on,
        lag(observed_on, 1) over (order by observed_on) as prev_on,
        lag(observed_on, 2) over (order by observed_on) as prev2_on
    from observation_dates
),

-- Пары страна × роль, переписанные в конкретный день. Пропажу засчитываем только
-- на фоне переписи той же пары: нет переписи — нет и вывода о том, что объявление
-- сняли.
census_pair_days as (
    select distinct
        observed_on,
        country_code,
        role_query
    from {{ ref('stg_vacancies') }}
    where is_census
),

-- Какими переписанными парами видели объявление в каждый день.
ad_census_pairs as (
    select distinct
        source_id,
        observed_on,
        country_code,
        role_query
    from {{ ref('stg_vacancies') }}
    where is_census
),

-- Объявление, которое можно признать снятым в день d: в позавчерашний день его
-- видели переписью пары, и эта же пара переписывалась и вчера, и сегодня.
closable as (
    select distinct
        c.source_id,
        d.observed_on
    from date_seq as d
    inner join ad_census_pairs as c
        on c.observed_on = d.prev2_on
    inner join census_pair_days as gap_day
        on gap_day.observed_on = d.prev_on
        and gap_day.country_code = c.country_code
        and gap_day.role_query = c.role_query
    inner join census_pair_days as today
        on today.observed_on = d.observed_on
        and today.country_code = c.country_code
        and today.role_query = c.role_query
    where d.prev2_on is not null
),

first_seen as (
    select
        source_id,
        min(observed_on) as first_seen_on
    from present
    group by source_id
),

-- Последний день, когда объявление видели переписью. Если позже оно вернулось,
-- дата сдвигается, и строка пропажи не появляется вовсе: вернувшаяся вакансия
-- не считается снятой (GAP 4).
last_census_day as (
    select
        source_id,
        max(observed_on) as last_present_on
    from present
    where seen_in_census
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
        p.seen_in_census,
        false as is_new,
        true as is_gone,
        f.first_seen_on,
        d.prev2_on as last_present_on
    from date_seq as d
    -- Последний раз объявление видели через одно наблюдение от текущего:
    -- значит, его нет уже дважды подряд.
    inner join present as p
        on p.observed_on = d.prev2_on
        and p.seen_in_census
    inner join last_census_day as l
        on l.source_id = p.source_id
        and l.last_present_on = d.prev2_on
    inner join closable as k
        on k.source_id = p.source_id
        and k.observed_on = d.observed_on
    inner join first_seen as f
        on f.source_id = p.source_id
    -- Анти-соединение: любое появление в выдаче за вчера или сегодня отменяет пропажу.
    left join present as later
        on later.source_id = p.source_id
        and later.observed_on in (d.prev_on, d.observed_on)
    where d.prev2_on is not null
        and later.source_id is null
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
        p.seen_in_census,
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
    -- Срок жизни объявления считается только там, где пропажа что-то значит.
    -- В остальных странах это возраст объявления в момент, когда оно вышло за
    -- окно сбора, то есть ширина нашего окна, а не поведение рынка.
    seen_in_census as is_lifetime_tracked,
    first_seen_on,
    {{ days_between('first_seen_on', 'last_present_on') }} + 1 as days_open,
    case
        when posted_at is null then null
        else greatest({{ days_between('posted_at', 'last_present_on') }}, 0)
    end as days_since_posted,
    -- Сколько объявление продержалось от публикации до снятия. Известно только
    -- у снятых: у висящих это «не меньше чем», и смешивать их нельзя.
    case
        when is_gone and seen_in_census and posted_at is not null
            then greatest({{ days_between('posted_at', 'last_present_on') }}, 0)
    end as listing_lifetime_days
from unioned
