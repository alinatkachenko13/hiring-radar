-- Для проверки блока 1: тайтлы, которые фильтр роли выкинул.
-- Если здесь окажется настоящий Data Engineer — править int_vacancies_enriched.

select
    title,
    country_code,
    role_queries,
    count(*) as n
from {{ ref('int_vacancies_enriched') }}
where role_key = 'other'
group by title, country_code, role_queries
