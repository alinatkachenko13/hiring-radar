-- Города внутри страны. Для ca и gb это рабочий разрез, не карта всех точек US.

select
    observed_on,
    country_code,
    location_city,
    location_region,
    role_key,
    count(distinct case when not is_gone then source_id end) as n_ads,
    count(distinct case when not is_gone then position_id end) as n_positions
from {{ ref('fct_vacancy_daily') }}
where is_relevant
  and location_city is not null
group by
    observed_on,
    country_code,
    location_city,
    location_region,
    role_key
