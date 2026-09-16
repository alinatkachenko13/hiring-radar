select distinct
    {{ sk(['country_code', 'location_region', 'location_city']) }} as location_sk,
    country_code,
    location_region,
    location_city
from {{ ref('int_vacancies_enriched') }}
