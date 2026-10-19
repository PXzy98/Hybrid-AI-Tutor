"""Survey contract, privacy, persistence and instructor aggregate suppression."""

from sqlalchemy import inspect
from sqlmodel import Session, select

from app.storage.models import SurveyResponse
from tests.conftest import Api

FIVE = ("high_blood_pressure", "type2_diabetes", "asthma", "migraine", "pneumonia")


def payload(topic="asthma", **changes):
    values = dict(topic=topic, helpfulness=5, material_relevance=4, clarity=3, source_confidence=2)
    values.update(changes)
    return values


def test_survey_requires_login_and_student_role(make_client):
    with make_client() as client:
        api = Api(client)
        api.make_student()
        api.make_instructor()
        assert client.post("/api/v1/survey", json=payload()).status_code == 401
        assert client.get("/api/v1/admin/survey-summary").status_code == 401
        api.login("prof")
        assert client.post("/api/v1/survey", json=payload()).status_code == 403
        api.login("alice")
        assert client.get("/api/v1/admin/survey-summary").status_code == 403


def test_survey_rejects_invalid_ratings_unknown_topics_and_extra_sensitive_fields(make_client):
    with make_client() as client:
        api = Api(client)
        api.make_student()
        api.login("alice")
        path = "/api/v1/survey"
        assert client.post(path, json=payload(helpfulness=0)).status_code == 422
        assert client.post(path, json=payload(source_confidence=6)).status_code == 422
        assert client.post(path, json=payload(clarity="excellent")).status_code == 422
        assert client.post(path, json=payload(topic="does_not_exist")).status_code == 404
        assert client.post(path, json=payload(student_id="student-123")).status_code == 422
        assert client.post(path, json=payload(question="My name is Alice")).status_code == 422
        assert client.post(path, json=payload(comment="I live at ...")).status_code == 422
        with Session(api.services.engine) as db:
            assert db.exec(select(SurveyResponse)).all() == []


def test_survey_storage_has_no_identity_or_text_and_aggregates_are_suppressed(make_client):
    with make_client() as client:
        api = Api(client)
        api.make_student()
        api.make_instructor()
        api.login("alice")
        response = client.post("/api/v1/survey", json=payload())
        assert response.status_code == 201 and response.json() == {"saved": True}
        with Session(api.services.engine) as db:
            rows = db.exec(select(SurveyResponse)).all()
            assert len(rows) == 1
            assert rows[0].topic == "asthma"
            columns = {x["name"] for x in inspect(api.services.engine).get_columns("survey_response")}
            assert columns == {"id", "topic", "helpfulness", "material_relevance",
                               "clarity", "source_confidence"}
            assert all(not hasattr(rows[0], f) for f in ("student_id", "question", "session_id", "comment"))
        api.login("prof")
        listing = client.get("/api/v1/admin/survey-summary")
        assert listing.status_code == 200
        assert listing.json()["min_group_size"] == 3
        topics = {t["topic"]: t for t in listing.json()["topics"]}
        assert set(topics) == set(FIVE)
        assert topics["asthma"]["count"] == 1
        assert topics["asthma"]["sufficient_sample"] is False
        assert topics["asthma"]["mean_helpfulness"] is None
        assert topics["asthma"]["mean_material_relevance"] is None
        assert topics["pneumonia"]["count"] == 0


def test_three_submissions_show_only_aggregated_results_persistent_across_login(make_client):
    with make_client() as client:
        api = Api(client)
        api.make_student()
        api.make_instructor()
        api.login("alice")
        for r in (payload(helpfulness=1), payload(helpfulness=3), payload(helpfulness=5)):
            assert client.post("/api/v1/survey", json=r).status_code == 201
        api.login("prof")
        survey = client.get("/api/v1/admin/survey-summary").json()
        topic = next(t for t in survey["topics"] if t["topic"] == "asthma")
        assert topic["count"] == 3
        assert topic["sufficient_sample"] is True
        assert topic["mean_helpfulness"] == 3.0
        assert topic["mean_material_relevance"] == 4.0
        assert topic["mean_clarity"] == 3.0
        assert topic["mean_source_confidence"] == 2.0
        assert "student_id" not in str(survey)
        assert "Alice" not in str(survey)
