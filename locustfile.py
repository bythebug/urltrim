"""
Load test: shorten, redirect, analytics.
Start API + consumer, then: locust -f locustfile.py --host http://localhost:8000
"""
import random
import string

from locust import HttpUser, task, between


def random_url():
    path = "".join(random.choices(string.ascii_lowercase, k=8))
    return f"https://example.com/{path}"


class UrlTrimUser(HttpUser):
    wait_time = between(0.1, 0.5)
    short_codes: list[str] = []

    def on_start(self):
        # create a few short links for this user to hit
        for _ in range(3):
            r = self.client.post(
                "/shorten",
                json={"url": random_url()},
                name="/shorten",
            )
            if r.ok:
                data = r.json()
                self.short_codes.append(data["short_code"])

    @task(3)
    def redirect(self):
        if not self.short_codes:
            return
        code = random.choice(self.short_codes)
        self.client.get(f"/{code}", name="/[code] redirect", allow_redirects=False)

    @task(1)
    def analytics(self):
        if not self.short_codes:
            return
        code = random.choice(self.short_codes)
        self.client.get(f"/analytics/{code}", name="/analytics/[code]")

    @task(1)
    def shorten(self):
        self.client.post(
            "/shorten",
            json={"url": random_url()},
            name="/shorten",
        )
