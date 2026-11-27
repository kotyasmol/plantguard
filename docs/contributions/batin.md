# История работ над уведомлениями

| Дата | Что сделано | Коммиты | Файлы |
| --- | --- | --- | --- |
| 2026-11-27 | Добавлено хранение ручных показаний и алертов, подготовлена обратимая миграция и проверки схемы и каскадов. | `ce8c3ea` — `feat: add environment reading and alert storage` | `database/models.py`, `alembic/versions/0005_environment_alerts.py`, `migration_test.py`, `tests/test_database_models.py` в `services/api`. |
| 2026-11-27 | Добавлен приём ручных показаний с проверкой владельца и транзакционной записью события в outbox. | `965e3b6` — `feat: accept manual environment readings` | `plant_history.py`, `schemas.py`, `test_plant_history_api.py` |
| 2026-11-27 | Добавлена история последних показаний по растению с ограничением числа записей. | `feat: expose recent environment readings` | `plant_history.py`, `test_plant_history_api.py` |

## В планах

- Консьюмер алертов, список уведомлений и отметка о прочтении.
- Форма ручного ввода, график и уведомления в веб-интерфейсе.
- Сквозной тест от HTTP-запроса до уведомления и обновление документации.
