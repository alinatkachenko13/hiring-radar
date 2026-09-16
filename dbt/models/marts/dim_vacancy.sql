-- SCD Type 2 по атрибутам, которые меняются у объявления между сборами.
-- valid_to — начало следующей версии, у текущей пусто.

with daily as (
    select
        source_id,
        observed_on,
        title,
        grade,
        contract_type,
        contract_time,
        is_remote,
        {{ sk(['title', 'grade', 'contract_type', 'contract_time', 'is_remote']) }}
            as attr_hash
    from {{ ref('int_vacancies_enriched') }}
),

marked as (
    select
        *,
        lag(attr_hash) over (
            partition by source_id
            order by observed_on
        ) as prev_hash
    from daily
),

versioned as (
    select
        *,
        sum(
            case
                when prev_hash is null or prev_hash != attr_hash then 1
                else 0
            end
        ) over (
            partition by source_id
            order by observed_on
        ) as version_n
    from marked
),

grouped as (
    select
        source_id,
        version_n,
        any_value(title) as title,
        any_value(grade) as grade,
        any_value(contract_type) as contract_type,
        any_value(contract_time) as contract_time,
        any_value(is_remote) as is_remote,
        min(observed_on) as valid_from
    from versioned
    group by source_id, version_n
)

select
    {{ sk(['source_id', 'valid_from']) }} as vacancy_sk,
    source_id,
    title,
    grade,
    contract_type,
    contract_time,
    is_remote,
    valid_from,
    lead(valid_from) over (
        partition by source_id
        order by valid_from
    ) as valid_to,
    lead(valid_from) over (
        partition by source_id
        order by valid_from
    ) is null as is_current
from grouped
