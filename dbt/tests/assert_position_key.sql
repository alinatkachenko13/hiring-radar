-- position_id склеивает lower(компания) + lower(тайтл) + страна.
-- Разный регистр («IMR Soft Llc» / «IMR Soft LLC») — одна позиция, так и задумано.

select
    position_id,
    count(distinct lower(coalesce(company_name, ''))) as n_companies,
    count(distinct lower(coalesce(title, ''))) as n_titles
from {{ ref('int_vacancies_enriched') }}
group by position_id
having count(distinct lower(coalesce(company_name, ''))) > 1
    or count(distinct lower(coalesce(title, ''))) > 1
