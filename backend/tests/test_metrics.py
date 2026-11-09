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


def test_equal_parameter_values_keep_the_route_template(make_client):
    with make_client() as client:
        route = "/api/v2/courses/{course_id}/modules/{module_id}"
        before = REGISTRY.get_sample_value("tutor_http_requests_total",
                                           {"method": "PATCH", "route": route, "status": "401"}) or 0.0
        client.patch("/api/v2/courses/1/modules/1", json={})  # both parameters are 1
        client.patch("/api/v2/courses/1/modules/2", json={})
        after = REGISTRY.get_sample_value("tutor_http_requests_total",
                                          {"method": "PATCH", "route": route, "status": "401"})
        assert after == before + 2
        assert "{module_id}/modules" not in client.get("/metrics").text


def test_a_streamed_response_is_timed_to_its_last_byte():
    import asyncio

    from fastapi import FastAPI
    from fastapi.responses import StreamingResponse
    from fastapi.testclient import TestClient

    from app.platform.metrics import MetricsMiddleware

    app = FastAPI()

    @app.get("/test-stream")
    def stream():
        async def body():
            yield b"first event\n"  # headers and this event go out at once
            await asyncio.sleep(0.3)
            yield b"last event\n"

        return StreamingResponse(body(), media_type="text/event-stream")

    app.add_middleware(MetricsMiddleware)
    labels = {"method": "GET", "route": "/test-stream"}
    before = REGISTRY.get_sample_value("tutor_http_request_duration_seconds_sum", labels) or 0.0
    assert TestClient(app).get("/test-stream").text.endswith("last event\n")
    took = REGISTRY.get_sample_value("tutor_http_request_duration_seconds_sum", labels) - before
    assert took >= 0.3
