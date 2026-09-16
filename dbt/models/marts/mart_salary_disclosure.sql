-- Доля раскрытия зарплаты по всем странам, не только gb/us.
-- Отдельный ряд на дашборде, не подпись мелким шрифтом.

select
    observed_on,
    country_code,
    count(distinct case when not is_gone then source_id end) as n_ads,
    count(distinct case
        when not is_gone and is_salary_disclosed then source_id
    end) as n_salary_disclosed
from {{ ref('fct_vacancy_daily') }}
where is_relevant
group by observed_on, country_code
