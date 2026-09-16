select distinct
    observed_on as date_day,
    extract(year from observed_on) as year,
    extract(month from observed_on) as month,
    extract(day from observed_on) as day
from {{ ref('stg_vacancies') }}
