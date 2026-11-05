-- Снимок «кто нанимает сейчас»: последняя дата сбора, позиции а не объявления.

with latest as (
    select max(observed_on) as observed_on
    from {{ ref('fct_vacancy_daily') }}
)

select
    f.observed_on,
    f.country_code,
    f.role_key,
    f.company_name,
    count(distinct case when not f.is_gone then f.position_id end)
        as n_positions_open,
    count(distinct case when f.is_new and not f.is_gone then f.position_id end)
        as n_positions_new,
    {{ median_expr('f.listing_lifetime_days') }} as listing_lifetime_p50,
    count(distinct case when f.listing_lifetime_days is not null then f.source_id end)
        as n_lifetime_known,
    {{ median_expr('case when not f.is_gone and f.is_salary_disclosed then f.salary_mid end') }}
        as salary_mid_p50
from {{ ref('fct_vacancy_daily') }} as f
inner join latest as l
    on f.observed_on = l.observed_on
where f.is_relevant
  and f.company_name is not null
group by f.observed_on, f.country_code, f.role_key, f.company_name
