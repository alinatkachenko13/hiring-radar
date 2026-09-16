select
    country_code,
    country_name,
    currency,
    salary_charts = 1 as show_salary
from (
    select 'gb' as country_code, 'United Kingdom' as country_name, 'GBP' as currency, 1 as salary_charts
    union all
    select 'de', 'Germany', 'EUR', 0
    union all
    select 'nl', 'Netherlands', 'EUR', 0
    union all
    select 'pl', 'Poland', 'PLN', 0
    union all
    select 'us', 'United States', 'USD', 1
    union all
    select 'ca', 'Canada', 'CAD', 0
) as countries
