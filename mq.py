import asyncio
import json
import pika
from config import settings

_connection = None
_channel = None
QUEUE = "urltrim.clicks"


def _sync_publish(short_code: str):
    try:
        params = pika.URLParameters(settings.rabbitmq_url)
        conn = pika.BlockingConnection(params)
        ch = conn.channel()
        ch.queue_declare(queue=QUEUE, durable=True)
        ch.basic_publish(
            exchange="",
            routing_key=QUEUE,
            body=json.dumps({"short_code": short_code}),
            properties=pika.BasicProperties(delivery_mode=2),
        )
        conn.close()
    except Exception:
        pass


async def publish_click(short_code: str):
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _sync_publish, short_code)
