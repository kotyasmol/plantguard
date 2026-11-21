SET 'ksql.streams.cache.max.bytes.buffering' = '0';

CREATE STREAM IF NOT EXISTS plant_observations (
    event_id VARCHAR,
    event_type VARCHAR,
    schema_version INTEGER,
    occurred_at BIGINT,
    observation_id VARCHAR,
    plant_id VARCHAR,
    photo_uri VARCHAR,
    description VARCHAR,
    humidity_pct DOUBLE,
    temperature_c DOUBLE
) WITH (
    KAFKA_TOPIC = 'plant.observations.v1',
    PARTITIONS = 3,
    VALUE_FORMAT = 'JSON',
    TIMESTAMP = 'occurred_at'
);

CREATE STREAM IF NOT EXISTS environment_readings (
    event_id VARCHAR,
    event_type VARCHAR,
    schema_version INTEGER,
    occurred_at BIGINT,
    plant_id VARCHAR,
    source VARCHAR,
    humidity_pct DOUBLE,
    temperature_c DOUBLE
) WITH (
    KAFKA_TOPIC = 'plant.environment-readings.v1',
    PARTITIONS = 3,
    VALUE_FORMAT = 'JSON',
    TIMESTAMP = 'occurred_at'
);

CREATE STREAM IF NOT EXISTS plant_observations_by_plant
    WITH (KAFKA_TOPIC = 'plant.observations.by-plant.v1', VALUE_FORMAT = 'JSON') AS
SELECT *
FROM plant_observations
PARTITION BY plant_id
EMIT CHANGES;

CREATE TABLE IF NOT EXISTS environment_reading_occurrences
    WITH (
        KAFKA_TOPIC = 'plant.environment.reading-occurrences.v1',
        VALUE_FORMAT = 'JSON'
    ) AS
SELECT
    event_id AS event_id_key,
    AS_VALUE(event_id) AS event_id,
    LATEST_BY_OFFSET(event_type) AS event_type,
    LATEST_BY_OFFSET(schema_version) AS schema_version,
    LATEST_BY_OFFSET(occurred_at) AS occurred_at,
    LATEST_BY_OFFSET(plant_id) AS plant_id,
    LATEST_BY_OFFSET(source) AS source,
    LATEST_BY_OFFSET(humidity_pct) AS humidity_pct,
    LATEST_BY_OFFSET(temperature_c) AS temperature_c,
    COUNT(*) AS occurrence_count
FROM environment_readings
WINDOW TUMBLING (SIZE 24 HOURS, RETENTION 7 DAYS, GRACE PERIOD 24 HOURS)
GROUP BY event_id
EMIT CHANGES;

CREATE STREAM IF NOT EXISTS environment_reading_occurrence_updates (
    event_id VARCHAR,
    event_type VARCHAR,
    schema_version INTEGER,
    occurred_at BIGINT,
    plant_id VARCHAR,
    source VARCHAR,
    humidity_pct DOUBLE,
    temperature_c DOUBLE,
    occurrence_count BIGINT
) WITH (
    KAFKA_TOPIC = 'plant.environment.reading-occurrences.v1',
    VALUE_FORMAT = 'JSON'
);

CREATE STREAM IF NOT EXISTS environment_readings_deduplicated
    WITH (KAFKA_TOPIC = 'plant.environment-readings.deduplicated.v1', VALUE_FORMAT = 'JSON') AS
SELECT
    event_id,
    event_type,
    schema_version,
    occurred_at,
    plant_id,
    source,
    humidity_pct,
    temperature_c
FROM environment_reading_occurrence_updates
WHERE occurrence_count = 1
EMIT CHANGES;

CREATE STREAM IF NOT EXISTS environment_readings_by_plant
    WITH (KAFKA_TOPIC = 'plant.environment-readings.by-plant.v1', VALUE_FORMAT = 'JSON') AS
SELECT *
FROM environment_readings_deduplicated
PARTITION BY plant_id
EMIT CHANGES;

CREATE TABLE IF NOT EXISTS latest_environment
    WITH (KAFKA_TOPIC = 'plant.environment.latest.v1', VALUE_FORMAT = 'JSON') AS
SELECT
    plant_id,
    LATEST_BY_OFFSET(humidity_pct) AS humidity_pct,
    LATEST_BY_OFFSET(temperature_c) AS temperature_c,
    LATEST_BY_OFFSET(occurred_at) AS occurred_at
FROM environment_readings_by_plant
GROUP BY plant_id
EMIT CHANGES;

CREATE TABLE IF NOT EXISTS environment_six_hour_summary
    WITH (KAFKA_TOPIC = 'plant.environment.6h-summary.v1', VALUE_FORMAT = 'JSON') AS
SELECT
    plant_id AS plant_id_key,
    AS_VALUE(plant_id) AS plant_id,
    AVG(humidity_pct) AS average_humidity_pct,
    AVG(temperature_c) AS average_temperature_c,
    COUNT(*) AS reading_count
FROM environment_readings_by_plant
WINDOW TUMBLING (SIZE 6 HOURS, RETENTION 7 DAYS, GRACE PERIOD 24 HOURS)
GROUP BY plant_id
EMIT CHANGES;

CREATE STREAM IF NOT EXISTS observation_context
    WITH (KAFKA_TOPIC = 'plant.observations.enriched.v1', VALUE_FORMAT = 'JSON') AS
SELECT
    observations.plant_id AS plant_id,
    observations.event_id AS observation_event_id,
    observations.observation_id AS observation_id,
    observations.occurred_at AS observation_occurred_at,
    observations.photo_uri AS photo_uri,
    observations.description AS description,
    environment.humidity_pct AS latest_humidity_pct,
    environment.temperature_c AS latest_temperature_c,
    environment.occurred_at AS environment_occurred_at
FROM plant_observations_by_plant observations
LEFT JOIN latest_environment environment
    ON observations.plant_id = environment.plant_id
EMIT CHANGES;

CREATE STREAM IF NOT EXISTS environment_alerts
    WITH (KAFKA_TOPIC = 'plant.alerts.v1', VALUE_FORMAT = 'JSON') AS
SELECT
    plant_id AS plant_id_key,
    AS_VALUE(plant_id) AS plant_id,
    CONCAT(event_id, ':environment') AS event_id,
    'plant.environment.alerted' AS event_type,
    1 AS schema_version,
    occurred_at,
    CASE
        WHEN humidity_pct < 20 THEN 'humidity_too_low'
        WHEN humidity_pct > 85 THEN 'humidity_too_high'
        WHEN temperature_c < 10 THEN 'temperature_too_low'
        ELSE 'temperature_too_high'
    END AS alert_code,
    CASE
        WHEN humidity_pct < 10 OR humidity_pct > 95
            OR temperature_c < 5 OR temperature_c > 40 THEN 'critical'
        ELSE 'warning'
    END AS severity
FROM environment_readings_by_plant
WHERE humidity_pct < 20
    OR humidity_pct > 85
    OR temperature_c < 10
    OR temperature_c > 35
EMIT CHANGES;
