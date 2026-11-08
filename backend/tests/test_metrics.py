"""Task Z13: GET /metrics (Prometheus) counts requests by route template, never by ID or text."""
from app.platform.metrics import REGISTRY


def _count(route: str, status: str) -> float:
    """The counter now (it is per process, so other tests' requests are in it too)."""
    labels = {"method": "GET", "route": route, "status": status}
    return REGISTRY.get_sample_value("tutor_http_requests_total", labels) or 0.0


def test_metrics_count_requests_by_route_template(make_client):
    with make_client() as client:
        before = {k: _count(*k) for k in [("/api/v1/health", "200"), ("/api/v2/courses/{course_id}", "401"),
                                          ("unmatched", "404")]}
        client.get("/api/v1/health")
        client.get("/api/v2/courses/987654")  # logged out: 401, counted under the template
        client.get("/api/v1/no-such-page")
        r = client.get("/metrics")
        assert r.status_code == 200 and r.headers["content-type"].startswith("text/plain")
        for key, value in before.items():
            assert _count(*key) == value + 1, key
        body = r.text
        assert "987654" not in body and "no-such-page" not in body  # no IDs or paths as labels
        assert "tutor_http_request_duration_seconds_bucket" in body and "tutor_component_version" in body
        assert 'route="/metrics"' not in body  # scrapes are not counted
        assert "/metrics" not in client.app.openapi()["paths"]  # not part of the API
