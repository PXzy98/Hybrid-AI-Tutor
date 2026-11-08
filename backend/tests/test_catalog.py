"""Task Z4: the course catalog holds the demo course; the app reads its content from the database."""
from pathlib import Path

import pytest
from sqlmodel import Session, select

from app.catalog import DEMO_COURSE, CatalogError, create_course, import_topics, load_course_content
from app.core.services import build_services
from app.learner.content import ContentStore, load_yaml_topics
from app.storage.models import CatalogMisconception, CheckItem, Course, Kc, KcPrerequisite, Module

CONTENT = Path(__file__).resolve().parents[2] / "content" / "topics"


def _signature(store: ContentStore):
    return [(t, [k.model_dump() for k in store.kcs(t)],
             sorted(i.model_dump_json() for k in store.kcs(t)
                    for i in store.items(k.id, include_unpublished=True)),
             sorted(m.model_dump_json() for m in store.all_misconceptions() if store.topic_of(m.kc) == t))
            for t in store.topics()]


def test_the_demo_course_is_created_once_from_the_yaml_seed(use_config):
    first = build_services(use_config())
    with Session(first.engine) as db:
        courses = db.exec(select(Course)).all()
        assert [(c.code, c.title, c.course_type, c.visibility_mode) for c in courses] == [
            (DEMO_COURSE["code"], DEMO_COURSE["title"], "medical_science", "A")]
        modules = db.exec(select(Module).order_by(Module.position)).all()
    assert [m.code for m in modules] == [t.topic for t in load_yaml_topics(CONTENT)]
    second = build_services(use_config())  # a restart does not import again
    with Session(second.engine) as db:
        assert len(db.exec(select(Course)).all()) == 1
        assert len(db.exec(select(Kc)).all()) == sum(len(t.kcs) for t in load_yaml_topics(CONTENT))
    assert second.content.course_id == courses[0].id


def test_database_content_equals_the_yaml_seed(use_config):
    services = build_services(use_config())
    assert _signature(services.content) == _signature(ContentStore.from_yaml(CONTENT))


def test_unreviewed_seed_content_is_imported_as_draft_and_not_served(use_config):
    services = build_services(use_config())
    with Session(services.engine) as db:
        assert {i.status for i in db.exec(select(CheckItem)).all()} == {"draft"}
        assert {m.status for m in db.exec(select(CatalogMisconception)).all()} == {"draft"}
    assert services.content.items("HBP.1") == []
    assert services.content.active_item_count("high_blood_pressure") == 0


def test_seed_status_active_publishes_the_demo_content(use_config):
    services = build_services(use_config({"content": {"seed_status": "active"}}))
    assert len(services.content.items("HBP.1")) == 4


def test_prerequisites_and_retired_kcs(use_config):
    services = build_services(use_config())
    with Session(services.engine) as db:
        hbp2 = db.exec(select(Kc).where(Kc.code == "HBP.2")).one()
        edges = db.exec(select(KcPrerequisite).where(KcPrerequisite.kc_id == hbp2.id)).all()
        assert len(edges) == 1
        hbp2.status = "retired"
        db.add(hbp2)
        db.commit()
    store = load_course_content(services.engine, services.content.course_id)
    assert store.kc("HBP.2") is None and store.kc("HBP.1") is not None


def test_import_refuses_a_course_with_content_and_deleting_a_course_removes_its_content(use_config):
    services = build_services(use_config())
    topics = load_yaml_topics(CONTENT)
    with Session(services.engine) as db:
        with pytest.raises(CatalogError):
            import_topics(db, services.content.course_id, topics)
        other = create_course(db, code="ELG 5902", title="Fictional engineering course", course_type="ece")
        import_topics(db, other.id, topics[:1], status="active")
        db.commit()
        assert len(db.exec(select(Kc).where(Kc.course_id == other.id)).all()) == len(topics[0].kcs)
        db.delete(db.get(Course, other.id))
        db.commit()
        for table in (Module, Kc, CheckItem, CatalogMisconception):
            assert db.exec(select(table).where(table.course_id == other.id)).all() == []
