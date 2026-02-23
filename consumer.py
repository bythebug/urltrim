"""
Background worker: consume click events from RabbitMQ and bump click counts in Postgres.
Run with: python -m consumer
"""
import json

import pika
from sqlalchemy import create_engine, text

from config import settings

QUEUE = "urltrim.clicks"

# sync engine for consumer (same DB, different driver)
# use psycopg dialect so we can use the psycopg[binary] wheel
_sync_url = settings.database_url.replace("postgresql+asyncpg", "postgresql+psycopg")
engine = create_engine(_sync_url)


def run_consumer():
    params = pika.URLParameters(settings.rabbitmq_url)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    channel.queue_declare(queue=QUEUE, durable=True)
    channel.basic_qos(prefetch_count=1)

    def callback(ch, method, properties, body):
        try:
            data = json.loads(body)
            code = data.get("short_code")
            if not code:
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return
            with engine.connect() as conn:
                conn.execute(text("UPDATE links SET clicks = clicks + 1 WHERE short_code = :code"), {"code": code})
                conn.commit()
        except Exception:
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
            return
        ch.basic_ack(delivery_tag=method.delivery_tag)

    channel.basic_consume(queue=QUEUE, on_message_callback=callback)
    channel.start_consuming()


if __name__ == "__main__":
    run_consumer()
