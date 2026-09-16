-- Раскрытая зарплата = оба условия сразу. Иначе правило разъедется по витринам.

select *
from {{ ref('stg_vacancies') }}
where is_salary_disclosed
    != (salary_is_predicted = '0' and salary_min is not null)
