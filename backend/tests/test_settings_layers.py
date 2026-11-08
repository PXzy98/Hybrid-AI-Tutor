"""Task Z5: settings layers, versions, optimistic locking, history, live component switch with lock."""
from datetime import timedelta

import pytest
from sqlmodel import Session, select

from app.catalog import create_course
from app.core.services import build_services
from app.learner.knowledge.rule import RuleKnowledgeModel
from app.platform.settings import SettingsConflict, SettingsError, SettingsLocked, effective_settings
from app.storage.models import AuditLog, ConfigHistory, ProcessStatus, SystemSettings, utcnow


@pytest.fixture
def services(use_config):
    return build_services(use_config())


def _other_model(services) -> str:
    """A knowledge model that differs from the configured one (the suite also runs with `rule`)."""
    return "bkt" if services.settings.learner.knowledge == "rule" else "rule"


def _second_course(services) -> int:
    with Session(services.engine) as db:
        course = create_course(db, code="ELG 5902", title="Fictional engineering course", course_type="ece")
        db.commit()
        return course.id


def test_two_courses_do_not_affect_each_other_and_layers_merge(services):
    service, demo = services.settings_service, services.content.course_id
    other = _second_course(services)
    service.save_course(demo, {"routing_threshold": 0.3, "local_only": True}, expected_version=0,
                        account_id=1)
    a, b = effective_settings(demo), effective_settings(other)
    assert (a.routing_threshold, a.local_only) == (0.3, True)
    assert (b.routing_threshold, b.local_only) == (services.settings.routing.threshold, False)
    assert (a.course_type, b.course_type) == ("medical_science", "ece")  # from the course rows
    service.save_system({"weak_evidence": True}, expected_version=0, account_id=1)
    assert effective_settings(demo).weak_evidence is effective_settings(other).weak_evidence is True
    service.save_course(other, {"routing_threshold": 0.9}, expected_version=0, account_id=1)
    assert effective_settings(demo).routing_threshold == 0.3  # course value wins over the other course's


def test_effective_settings_are_cached_until_a_version_changes(services):
    demo = services.content.course_id
    first = effective_settings(demo)
    assert effective_settings(demo) is first
    services.settings_service.save_course(demo, {"show_routing_progress": False}, expected_version=0,
                                          account_id=None)
    second = effective_settings(demo)
    assert second is not first and second.show_routing_progress is False and second.course_version == 1


def test_a_stale_version_is_refused_and_nothing_is_half_saved(services):
    service, demo = services.settings_service, services.content.course_id
    assert service.save_course(demo, {"routing_threshold": 0.5}, expected_version=0, account_id=1) == 1
    with pytest.raises(SettingsConflict):
        service.save_course(demo, {"routing_threshold": 0.7}, expected_version=0, account_id=1)
    with pytest.raises(SettingsError):
        service.save_course(demo, {"routing_threshold": 1.5}, expected_version=1, account_id=1)
    with pytest.raises(SettingsError):
        # the required checkers cannot be switched off
        service.save_system({"checkers": ["grounding"]}, expected_version=0, account_id=1)
    assert effective_settings(demo).routing_threshold == 0.5 and service.course_values(demo)[1] == 1


def test_history_audit_and_restore(services):
    service, demo = services.settings_service, services.content.course_id
    service.save_course(demo, {"routing_threshold": 0.4}, expected_version=0, account_id=3)
    service.save_course(demo, {"routing_threshold": 0.8}, expected_version=1, account_id=3)
    older = service.history(scope="course", course_id=demo)[-1]
    assert older.values["routing_threshold"] == 0.4
    assert service.restore(older.id, account_id=3) == 3
    assert effective_settings(demo).routing_threshold == 0.4
    with Session(services.engine) as db:
        actions = [a.action for a in db.exec(select(AuditLog).order_by(AuditLog.id)).all()]
    assert actions == ["settings.course.update", "settings.course.update", "settings.course.restore"]


def test_a_component_change_is_switched_live_in_this_process(services):
    service = services.settings_service
    old, model = services.components, _other_model(services)
    service.save_system({"knowledge_model": model}, expected_version=0, account_id=1)
    services.component_manager.sync()
    assert services.components is not old and services.settings.learner.knowledge == model
    assert type(services.learner.knowledge) is not type(old.learner.knowledge)
    assert service.system_values()[2] == "applied"


def _other_process(services, version: int, error: str | None = None) -> None:
    with Session(services.engine) as db:
        row = db.get(ProcessStatus, "other") or ProcessStatus(process_id="other", kind="worker")
        row.last_seen, row.component_version, row.error = utcnow(), version, error
        db.add(row)
        db.commit()


def test_the_row_stays_locked_until_every_live_process_runs_the_new_version(services):
    service = services.settings_service
    services.component_manager.sync()
    _other_process(services, version=0)
    v = service.save_system({"knowledge_model": _other_model(services)}, expected_version=0, account_id=1)
    services.component_manager.sync()  # this process switched; the other has not
    assert service.system_values()[2] == "applying"
    with pytest.raises(SettingsLocked):
        service.save_system({"knowledge_model": "bkt"}, expected_version=v, account_id=1)
    _other_process(services, version=v)  # the other process reports the new version
    services.component_manager.sync()
    assert service.system_values()[2] == "applied"


def test_a_failing_process_rolls_the_change_back(services):
    service = services.settings_service
    services.component_manager.sync()
    _other_process(services, version=0, error="RuntimeError: cannot load model")
    before = type(services.learner.knowledge)
    service.save_system({"knowledge_model": _other_model(services)}, expected_version=0, account_id=1)
    services.component_manager.sync()
    values, version, state = service.system_values()
    assert state == "failed" and values["knowledge_model"] is None and version == 2
    with Session(services.engine) as db:
        assert "cannot load model" in db.get(SystemSettings, 1).apply_error
    services.component_manager.sync()  # this process builds the old set again
    assert type(services.learner.knowledge) is before


def test_a_change_not_applied_in_time_is_rolled_back(services):
    service = services.settings_service
    services.component_manager.sync()
    _other_process(services, version=0)
    service.save_system({"default_routing_method": "svm"}, expected_version=0, account_id=1)
    with Session(services.engine) as db:
        row = db.get(SystemSettings, 1)
        timeout = services.settings.limits.settings.apply_timeout_seconds
        row.apply_started_at = utcnow() - timedelta(seconds=timeout + 1)
        db.add(row)
        db.commit()
    services.component_manager.sync()
    assert service.system_values()[2] == "failed"
    assert effective_settings(services.content.course_id).default_routing_method == "lr"


def test_the_newest_v3_dashboard_change_is_migrated_once(use_config):
    first = build_services(use_config())  # creates the tables and the demo course
    with Session(first.engine) as db:
        db.add(ConfigHistory(values={"routing_threshold": 0.45, "show_routing_progress": False,
                                     "checkers": ["medical_safety", "pii_leak", "profile_leak"],
                                     "knowledge": "rule", "weak_evidence": True,
                                     "levels": {"basic_below": 0.3, "advanced_above": 0.8,
                                                "hysteresis": 0.05}},
                             previous={}))
        db.commit()
    services = build_services(use_config())
    eff = services.effective()
    assert (eff.routing_threshold, eff.show_routing_progress, eff.knowledge_model) == (0.45, False, "rule")
    assert eff.level_basic_below == 0.3 and eff.checkers == ("medical_safety", "pii_leak", "profile_leak")
    assert isinstance(services.learner.knowledge, RuleKnowledgeModel)
    again = build_services(use_config())
    assert again.settings_service.system_values()[1] == 1  # not migrated twice


def test_v1_dashboard_put_is_refused_while_a_change_applies(make_client):
    from tests.conftest import PASSWORD

    with make_client() as client:
        services = client.app.state.services
        services.accounts.create_instructor("prof", PASSWORD, must_change=False)
        login = client.post("/api/v1/auth/login", json={"username": "prof", "password": PASSWORD})
        assert login.status_code == 200
        _other_process(services, version=0)
        body = client.get("/api/v1/admin/config").json()["values"]
        other = "bkt" if body["knowledge"] == "rule" else "rule"
        assert client.put("/api/v1/admin/config", json={**body, "knowledge": other}).status_code == 200
        r = client.put("/api/v1/admin/config", json={**body, "knowledge": body["knowledge"]})
        assert r.status_code == 423


def test_a_local_only_course_never_calls_the_cloud_model(make_client):
    from app.llm.cloud_guard import CloudClient
    from app.llm.fake import FakeLLMClient
    from tests.conftest import PASSWORD

    with make_client({"routing": {"stub_score": 1.0}}) as client:  # the router would pick the cloud
        services = client.app.state.services
        cloud = FakeLLMClient("Cloud answer.", model="gpt-test", backend="cloud")
        services.cloud_llm = CloudClient(cloud)
        services.local_llm = FakeLLMClient("Local answer.")
        services.settings_service.save_course(services.content.course_id, {"local_only": True},
                                              expected_version=0, account_id=None)
        account, _ = services.accounts.create_student("alice", "Alice")
        services.accounts.set_password(account.id, PASSWORD, must_change=False)
        services.learner.set_consent(account.student_id, True)
        client.post("/api/v1/auth/login", json={"username": "alice", "password": PASSWORD})
        reply = client.post("/api/v1/ask", json={"topic": "asthma", "question": "What is asthma?"}).json()
    assert reply["route_target"] == "local" and cloud.calls == []


def test_level_thresholds_are_checked_as_they_will_apply(services):
    service = services.settings_service
    with pytest.raises(SettingsError):
        service.save_system({"level_basic_below": 0}, expected_version=0, account_id=1)
    with pytest.raises(SettingsError):  # above the configured advanced threshold (0.70)
        service.save_system({"level_basic_below": 0.8}, expected_version=0, account_id=1)
    assert service.save_system({"level_basic_below": 0.3}, expected_version=0, account_id=1) == 1


def test_parallel_first_saves_of_a_course_conflict_cleanly(services):
    from concurrent.futures import ThreadPoolExecutor

    service, demo = services.settings_service, services.content.course_id

    def save(value):
        try:
            return service.save_course(demo, {"routing_threshold": value}, expected_version=0, account_id=1)
        except SettingsConflict:
            return "conflict"

    with ThreadPoolExecutor(4) as pool:
        results = list(pool.map(save, [0.1, 0.2, 0.3, 0.4]))
    assert results.count(1) == 1 and results.count("conflict") == 3
