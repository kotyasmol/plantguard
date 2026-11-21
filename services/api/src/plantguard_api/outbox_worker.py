from __future__ import annotations

import logging
import time

from sqlalchemy.orm import Session

from .config import get_settings
from .database import get_engine
from .outbox import KafkaEventProducer, OutboxPublisher

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    settings = get_settings()
    producer = KafkaEventProducer(settings.kafka_bootstrap_servers)
    publisher = OutboxPublisher(producer, batch_size=settings.outbox_batch_size)
    try:
        while True:
            try:
                with Session(get_engine()) as session:
                    published = publisher.publish_batch(session)
                if published:
                    logger.info("Published %s outbox event(s)", published)
            except Exception:
                logger.exception("Outbox polling failed; retrying")
            time.sleep(settings.outbox_poll_interval_seconds)
    except KeyboardInterrupt:
        logger.info("Outbox worker stopped")
    finally:
        producer.close()


if __name__ == "__main__":
    main()
