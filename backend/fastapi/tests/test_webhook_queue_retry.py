from app.services.payment.webhook_queue import WebhookQueue


class FakeRedis:
    def __init__(self):
        self.data = {}
        self.lists = {}

    def rpush(self, key, value):
        self.lists.setdefault(key, []).append(value)

    def lpop(self, key):
        arr = self.lists.get(key, [])
        return arr.pop(0) if arr else None

    def setex(self, key, ttl, value):
        self.data[key] = value

    def get(self, key):
        return self.data.get(key)


def test_retry_then_dlq(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr("app.services.payment.webhook_queue.redis_sync", fake)

    payload = {"provider": "stripe", "retry_count": 0}
    for _ in range(5):
        WebhookQueue.requeue_or_dlq(payload)
        assert len(fake.lists.get(WebhookQueue.QUEUE_KEY, [])) >= 1
        payload = {"provider": "stripe", "retry_count": payload["retry_count"]}

    payload = {"provider": "stripe", "retry_count": 5}
    WebhookQueue.requeue_or_dlq(payload)
    assert len(fake.lists.get(WebhookQueue.DLQ_KEY, [])) == 1


def test_duplicate_webhook_idempotency(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr("app.services.payment.webhook_queue.redis_sync", fake)
    WebhookQueue.mark_processed("abc")
    assert WebhookQueue.is_processed("abc") is True
