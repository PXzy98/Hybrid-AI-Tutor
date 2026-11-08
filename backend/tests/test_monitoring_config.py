"""Task Z13: the monitoring files (deploy/monitoring) match the metrics the app exports and stay internal.
CI also checks them with promtool and amtool (.github/workflows/ci.yml)."""
import json
import re
from pathlib import Path

import yaml

from app.platform.metrics import REGISTRY

ROOT = Path(__file__).resolve().parents[2]
MON = ROOT / "deploy" / "monitoring"
# vLLM's own metric names (served by the vLLM server)
VLLM = {"vllm:num_requests_waiting", "vllm:num_requests_running", "vllm:generation_tokens_total"}


def _exported() -> set[str]:
    names = set()
    for family in REGISTRY.collect():
        names |= {family.name, f"{family.name}_total", f"{family.name}_bucket", f"{family.name}_sum",
                  f"{family.name}_count"}
    return names


def _metrics(expr: str) -> set[str]:
    return set(re.findall(r"\b(tutor_[a-z_]+|vllm:[a-z_]+)", expr))


def test_alerts_and_dashboard_use_only_metrics_that_exist():
    alerts = yaml.safe_load((MON / "alerts.yml").read_text(encoding="utf-8"))
    exprs = [r["expr"] for g in alerts["groups"] for r in g["rules"]]
    dashboard = json.loads((MON / "grafana" / "dashboards" / "tutor.json").read_text(encoding="utf-8"))
    exprs += [t["expr"] for p in dashboard["panels"] for t in p["targets"]]
    used = set().union(*(_metrics(e) for e in exprs))
    unknown = {m for m in used if m.startswith("tutor_") and m not in _exported()} | (
        {m for m in used if m.startswith("vllm:")} - VLLM)
    assert not unknown, unknown
    assert {"TutorApiDown", "VllmDown"} <= {r["alert"] for g in alerts["groups"] for r in g["rules"]}


def test_prometheus_scrapes_the_api_inside_the_stack():
    config = yaml.safe_load((MON / "prometheus.yml").read_text(encoding="utf-8"))
    jobs = {j["job_name"]: j for j in config["scrape_configs"]}
    assert jobs["tutor-api"]["static_configs"][0]["targets"] == ["api:8000"]
    assert yaml.safe_load((MON / "targets" / "vllm.yml").read_text(encoding="utf-8")) == []


def test_monitoring_is_opt_in_and_grafana_is_local_only():
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    services = compose["services"]
    for name in ("prometheus", "alertmanager", "grafana"):
        assert services[name]["profiles"] == ["monitoring"], name
    assert "ports" not in services["prometheus"] and "ports" not in services["alertmanager"]
    assert all(p.startswith("127.0.0.1:") for p in services["grafana"]["ports"])
    # Grafana refuses to start without a password (never the default admin one)
    assert "GF_SECURITY_ADMIN_PASSWORD" in " ".join(services["grafana"]["entrypoint"])
