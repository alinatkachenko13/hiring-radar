select
    role_key,
    role_name,
    priority
from (
    select 'analytics_engineer' as role_key, 'analytics engineer' as role_name, 1 as priority
    union all
    select 'ml_engineer', 'ml engineer', 2
    union all
    select 'data_scientist', 'data scientist', 3
    union all
    select 'data_engineer', 'data engineer', 4
    union all
    select 'data_analyst', 'data analyst', 5
    union all
    select 'other', 'other', 9
) as roles
