-- Витрина экрана «обзор рынка» и «спрос и динамика».
-- Только релевантные роли: без фильтра dim_role объём завышен.

select
    observed_on,
    country_code,
    role_key,
    count(distinct case when not is_gone then source_id end) as n_ads,
    count(distinct case when not is_gone then position_id end) as n_positions,
    count(distinct case when is_new and not is_gone then source_id end) as n_new,
    count(distinct case when is_gone then source_id end) as n_gone,
    count(distinct case
        when not is_gone and is_salary_disclosed then source_id
    end) as n_salary_disclosed,
    count(distinct case
        when not is_gone and is_remote then source_id
    end) as n_remote_or_hybrid,
    count(distinct case
        when not is_gone and contract_type = 'permanent' then source_id
    end) as n_permanent,
    count(distinct case
        when not is_gone and contract_type = 'contract' then source_id
    end) as n_contract,
    count(distinct case
        when not is_gone and contract_time = 'full_time' then source_id
    end) as n_full_time,
    count(distinct case
        when not is_gone and contract_time = 'part_time' then source_id
    end) as n_part_time,
    count(distinct case when not is_gone and grade = 'intern' then source_id end)
        as n_intern,
    count(distinct case when not is_gone and grade = 'junior' then source_id end)
        as n_junior,
    count(distinct case when not is_gone and grade = 'mid' then source_id end)
        as n_mid,
    count(distinct case when not is_gone and grade = 'senior' then source_id end)
        as n_senior,
    count(distinct case when not is_gone and grade = 'lead' then source_id end)
        as n_lead
from {{ ref('fct_vacancy_daily') }}
where is_relevant
group by observed_on, country_code, role_key
