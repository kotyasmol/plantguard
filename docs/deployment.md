# Production-развёртывание

Production-контур рассчитан на обычный Linux VPS, включая сервер в Amnesia Host, с Docker Engine, Compose plugin, открытыми портами `80` и `443`, доменным именем и минимум 4 ГБ RAM. Для комфортной одновременной работы Kafka и ksqlDB рекомендуется 6 ГБ RAM.

## 1. Подготовка DNS и сервера

1. Создайте `A`-запись домена на IPv4 сервера и при наличии `AAAA`-запись на IPv6.
2. Установите Docker Engine и Compose plugin из официального репозитория Docker.
3. Клонируйте репозиторий в `/opt/plantguard` под отдельным непривилегированным пользователем.
4. Разрешите входящий TCP-трафик на `80` и `443`, UDP на `443`; SSH ограничьте доверенными адресами, если это возможно.

PostgreSQL, Kafka, ksqlDB и API не публикуют порты на хосте. Caddy является единственной внешней точкой входа и автоматически получает TLS-сертификат после корректного обновления DNS.

## 2. Секреты

```bash
cd /opt/plantguard
cp deploy/env.production.example deploy/.env.production
chmod 600 deploy/.env.production
```

Замените домен, пароль PostgreSQL и ключ подписания фотографий. Случайные значения можно создать командой `openssl rand -hex 32`. Параметры LLM необязательны: без них объяснения формируются локально в безопасном режиме. Ключ Pl@ntNet также необязателен: с ним доступен широкий каталог видов, без него используется встроенная локальная модель. Ключ получают на `https://my.plantnet.org/` и хранят только в production environment file.

Файл `deploy/.env.production` игнорируется Git и не должен передаваться в issue, логи или резервную копию репозитория.

## 3. Первый запуск и обновление

```bash
./deploy/deploy.sh
```

Скрипт проверяет итоговую Compose-конфигурацию, собирает единственный собственный образ `plantguard-app`, применяет миграции, запускает инфраструктуру, создаёт ksqlDB-объекты и проверяет readiness API. Повторный запуск безопасно обновляет уже работающий экземпляр.

Проверка после запуска:

```bash
curl --fail https://plantguard.example.com/health/ready
curl --fail https://plantguard.example.com/metrics
docker compose --env-file deploy/.env.production -f deploy/compose.production.yaml ps
```

## 4. Резервные копии

```bash
sudo PLANTGUARD_BACKUP_DIR=/var/backups/plantguard ./deploy/backup.sh
```

Скрипт создаёт сжатый dump PostgreSQL, архив фотографий и SHA-256 checksums. Копии необходимо переносить в отдельное хранилище и периодически проверять восстановление на тестовом сервере. Скрипт намеренно не удаляет старые архивы; политику retention настраивает оператор.

Восстановление выполняют только на остановленном экземпляре: сначала разворачивают чистый PostgreSQL из dump, затем возвращают каталог `photos` в volume `plantguard_photo-data`, запускают `deploy.sh` и проверяют историю через UI. Перед восстановлением всегда сохраняйте текущие volumes.

## 5. Автоматическое обновление

Workflow `Deploy` запускается вручную из GitHub Actions. Для environment `production` нужны секреты:

- `DEPLOY_HOST` — IP или имя сервера;
- `DEPLOY_PORT` — SSH-порт;
- `DEPLOY_USER` — непривилегированный пользователь;
- `DEPLOY_SSH_KEY` — закрытый deploy key;
- `DEPLOY_KNOWN_HOSTS` — заранее проверенная строка `known_hosts` сервера.

На сервере репозиторий должен уже находиться в `/opt/plantguard`, а `deploy/.env.production` — быть заполнен. Workflow делает только fast-forward обновление `main` и запускает тот же проверяемый deploy script.

## Наблюдаемость

- `/health` — liveness процесса;
- `/health/ready` — готовность API и соединения с PostgreSQL;
- `/metrics` — Prometheus-совместимые счётчики HTTP-ответов и суммарное время;
- API и Caddy пишут структурированные access logs в stdout, доступные через `docker compose logs`.
