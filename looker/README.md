# Looker Studio

Источник: `hiring-radar-508720.marts.looker_vacancies`.

Отчёт: https://lookerstudio.google.com/reporting/eebbe33b-bce8-4727-91bf-9ac8544d2850

Редактор: https://lookerstudio.google.com/reporting/eebbe33b-bce8-4727-91bf-9ac8544d2850/page/tEnnC/edit

Общие фильтры отчёта: `country_name`, `role_name`, `contract_type`, `observed_on`.

Меры: `COUNT_DISTINCT(source_id)` — объявления, `COUNT_DISTINCT(position_id)` — позиции. Для открытых на снимке включи `is_open`. Зарплаты: `is_salary_disclosed` и `show_salary`. Remote на графике подписать как оценку.

Экраны:

1. Обзор рынка — https://lookerstudio.google.com/reporting/eebbe33b-bce8-4727-91bf-9ac8544d2850/page/tEnnC
   KPI: объявления, позиции, новые, ушедшие, доля с зарплатой. Состав `contract_type`×`grade` и `contract_time`×`remote_type`. Столбцы по `country_name`.
2. Спрос и динамика — https://lookerstudio.google.com/reporting/eebbe33b-bce8-4727-91bf-9ac8544d2850/page/p_x2lky0oh7d
   Столбцы `observed_on` × объявления и позиции (`is_open`). Таблица `city_group`×`country_name`. Поток: новые / ушедшие.
3. Зарплаты — https://lookerstudio.google.com/reporting/eebbe33b-bce8-4727-91bf-9ac8544d2850/page/p_y9l78zoh7d
   Таблица `country_name`×`role_name` × медиана `salary_mid`, фильтры `is_open` и `is_salary_disclosed`.
4. Компании и время жизни — https://lookerstudio.google.com/reporting/eebbe33b-bce8-4727-91bf-9ac8544d2850/page/p_6mj650oh7d
   Таблица `company_name`×`role_name` × `COUNT_DISTINCT(position_id)` и медиана `days_open`, фильтр `is_open`.
