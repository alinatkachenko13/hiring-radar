select
    company_sk,
    min(company_name) as company_name
from (
    select
        {{ sk(["lower(coalesce(company_name, ''))"]) }} as company_sk,
        company_name
    from {{ ref('int_vacancies_enriched') }}
    where company_name is not null
) as companies
group by company_sk
