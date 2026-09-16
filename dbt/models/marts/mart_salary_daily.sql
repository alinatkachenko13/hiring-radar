-- Зарплаты только там, где вилку указал работодатель.
-- Медиана и квартили считаются по середине вилки. Страны не складываются:
-- gb и us в разных валютах, это два ряда, не одна цифра.

select
    f.observed_on,
    f.country_code,
    f.role_key,
    c.currency,
    count(*) as n_disclosed,
    {{ median_expr('f.salary_mid') }} as salary_mid_p50,
    {{ percentile_expr('f.salary_mid', 25) }} as salary_mid_p25,
    {{ percentile_expr('f.salary_mid', 75) }} as salary_mid_p75,
    {{ median_expr('f.salary_min') }} as salary_min_p50,
    {{ median_expr('f.salary_max') }} as salary_max_p50
from {{ ref('fct_vacancy_daily') }} as f
inner join {{ ref('dim_country') }} as c
    on f.country_code = c.country_code
where f.is_relevant
  and not f.is_gone
  and f.is_salary_disclosed
  and c.show_salary
group by f.observed_on, f.country_code, f.role_key, c.currency
