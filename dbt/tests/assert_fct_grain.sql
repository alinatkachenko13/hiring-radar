-- На факте тоже одна строка на объявление в дату, включая день исчезновения.

select
    source_id,
    observed_on,
    count(*) as n
from {{ ref('fct_vacancy_daily') }}
group by source_id, observed_on
having count(*) > 1
