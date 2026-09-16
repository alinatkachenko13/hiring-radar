-- После дедупликации по id в одну дату одна строка.

select
    source_id,
    observed_on,
    count(*) as n
from {{ ref('int_vacancies_deduped') }}
group by source_id, observed_on
having count(*) > 1
