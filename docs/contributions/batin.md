# История работ над уведомлениями

| Дата | Что сделано | Коммиты | Файлы |
| --- | --- | --- | --- |
| 2026-11-27 | Добавлено хранение ручных показаний и алертов, подготовлена обратимая миграция и проверки схемы и каскадов. | `ce8c3ea` — `feat: add environment reading and alert storage` | `database/models.py`, `alembic/versions/0005_environment_alerts.py`, `migration_test.py`, `tests/test_database_models.py` в `services/api`. |
| 2026-11-27 | Добавлен приём ручных показаний с проверкой владельца и транзакционной записью события в outbox. | `965e3b6` — `feat: accept manual environment readings` | `plant_history.py`, `schemas.py`, `test_plant_history_api.py` |
| 2026-11-27 | Добавлена история последних показаний по растению с ограничением числа записей. | `feat: expose recent environment readings` | `plant_history.py`, `test_plant_history_api.py` |
| 2026-11-27 | Добавлен обработчик событий ksqlDB с сохранением алертов и защитой от повторной доставки. | `feat: consume plant alerts from Kafka` | `alert_consumer.py`, `test_alert_consumer.py` |
| 2026-11-27 | Подключён процесс обработки алертов в обоих окружениях Compose. | `build: run the alert consumer in compose` | `compose.yaml`, `deploy/compose.production.yaml` |
| 2026-11-27 | Добавлен список уведомлений владельца с фильтром непрочитанных. | `feat: list plant alerts` | `alerts.py`, `main.py`, `schemas.py`, `test_plant_history_api.py` |
| 2026-11-27 | Добавлена отметка о прочтении с сохранением времени первого прочтения. | `feat: acknowledge plant alerts` | `alerts.py`, `test_plant_history_api.py` |
| 2026-11-28 | Добавлены счётчик непрочитанных, список уведомлений и отметка о прочтении в веб-интерфейсе. | `feat: show and acknowledge plant alerts` | `App.tsx`, `Sidebar.tsx`, `AlertList.tsx`, `api.ts`, `styles.css`, `App.test.tsx` |
| 2026-11-28 | Добавлены ручной ввод температуры и влажности и график последних показаний в карточке растения. | `feat: record and chart environment readings` | `EnvironmentPanel.tsx`, `EnvironmentPanel.test.tsx`, `App.tsx`, `PlantWorkspace.tsx`, `api.ts`, `styles.css` |
| 2026-11-28 | Расширена потоковая проверка: отправка показания по HTTP, получение предупреждения и отметка о прочтении. | `test: verify environment alerts end to end` | `Makefile`, `deploy/compose.test-streams.yaml`, `scripts/test_stream_processing.py` |

## В планах

- Обновление документации по показаниям и уведомлениям.
