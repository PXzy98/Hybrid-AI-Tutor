"""Long-lived services shared by pipeline steps and API routes, built once at startup."""
from dataclasses import dataclass

from sqlalchemy import Engine

from app.auth.service import AccountService
from app.core.config import Settings, get_settings
from app.core.schemas import EffectiveSettings
from app.learner.content import ContentStore
from app.learner.facade import LearnerModel
from app.llm.base import LLMClient
from app.llm.cloud_guard import CloudClient
from app.llm.endpoints import check_keys_readable
from app.llm.factory import build_llm_clients
from app.llm.gateway import Gateway
from app.platform.components import ComponentManager, Components
from app.platform.courses import CourseService
from app.platform.settings import SettingsService, configure, migrate_v1_history
from app.rag import Retriever, load_retriever
from app.routing import RouteScorer, load_router
from app.sessions import SessionStore, load_session_store
from app.storage.db import init_db, make_engine


@dataclass
class Services:
    """Deploy-time objects plus the current component set (settings, learner model, local model clients,
    pipeline runner), which `app.platform.components` switches live when the system settings change."""

    engine: Engine
    router: RouteScorer
    retriever: Retriever
    sessions: SessionStore
    accounts: AccountService
    cloud_llm: CloudClient
    content: ContentStore
    settings_service: SettingsService
    components: Components | None = None
    component_manager: ComponentManager | None = None
    gateway: Gateway | None = None  # the model gateway (task Z6)
    courses: CourseService | None = None  # courses, members, invitation codes (task Z9)
    usage: object | None = None  # the usage meter (task Z10; app.platform.usage)
    course_retriever: object | None = None  # per-course index (S4; app.rag.course_retriever), read-only here
    course_scopes: object | None = None  # content, learner model and retriever per course (API v2 ask)

    # the current component set; one reference, swapped as a whole
    @property
    def settings(self) -> Settings:
        return self.components.settings

    @settings.setter
    def settings(self, settings: Settings) -> None:  # evaluation harnesses swap the settings of the set
        self.components.settings = settings

    @property
    def learner(self) -> LearnerModel:
        return self.components.learner

    @property
    def local_llm(self) -> LLMClient:
        return self.components.local_llm

    @local_llm.setter
    def local_llm(self, client: LLMClient) -> None:  # tests and evaluation harnesses use fakes
        self.components.local_llm = client

    @property
    def understand_llm(self) -> LLMClient:
        return self.components.understand_llm

    @understand_llm.setter
    def understand_llm(self, client: LLMClient) -> None:
        self.components.understand_llm = client

    def effective(self, course_id: int | None = None) -> EffectiveSettings:
        """The request's settings snapshot (the demo course until requests carry a course)."""
        return self.settings_service.effective(course_id or self.content.course_id)


def load_demo_content(engine, settings: Settings) -> ContentStore:
    """The demo course from the catalog, created from the YAML seed on first start (task Z4)."""
    from app.catalog import ensure_demo_course, load_course_content
    from app.learner.content import load_yaml_topics

    status = "active" if settings.content.seed_status == "active" else None
    course_id = ensure_demo_course(engine, load_yaml_topics(settings.content_dir()), status)
    adopt_rows_without_course(engine, course_id)
    return load_course_content(engine, course_id)


def adopt_rows_without_course(engine, course_id: int) -> None:
    """Rows written before learner data had a course belong to the demo course (the one API v1 served).

    The migration assigns them when the course exists; a database upgraded from before the course catalog
    gets its demo course only at this start, after the migrations, so they are assigned here.
    """
    from sqlalchemy import text

    from app.storage.models import ROWS_OF_A_COURSE

    with engine.begin() as conn:
        for table in ROWS_OF_A_COURSE:
            conn.execute(text(f'UPDATE "{table}" SET course_id = :course WHERE course_id IS NULL'),
                         {"course": course_id})


def build_services(settings: Settings | None = None) -> Services:
    settings = settings or get_settings()
    password = settings.pgpassword.get_secret_value() if settings.pgpassword else None
    engine = make_engine(settings.database_url, pooled=settings.database_pooled, password=password)
    init_db(engine)
    _, cloud_llm, _ = build_llm_clients(settings)
    content = load_demo_content(engine, settings)  # validated here
    settings_service = SettingsService(engine, settings)
    configure(settings_service)
    migrate_v1_history(settings_service, content.course_id)
    services = Services(
        engine=engine,
        router=load_router(settings.routing.impl),
        retriever=load_retriever(settings.rag.impl),
        sessions=load_session_store(settings.sessions.store, engine),
        accounts=AccountService(engine, settings),
        cloud_llm=cloud_llm,
        content=content,
        settings_service=settings_service,
    )
    secret = settings.settings_encryption_key.get_secret_value() if settings.settings_encryption_key else None
    check_keys_readable(engine, secret)  # stored API keys need SETTINGS_ENCRYPTION_KEY (design 6.3)
    services.gateway = Gateway(services)
    services.accounts.default_course_id = content.course_id  # API v1 = the demo course
    services.sessions.course_id = content.course_id  # its conversations belong to that course
    from app.platform import usage

    services.usage = usage.DbUsageMeter(engine, settings.limits.usage, settings_service.effective)
    usage.configure(services.usage)  # check_usage / record_usage (task Z10)
    services.courses = CourseService(engine, services.accounts, settings.limits.accounts,
                                     lambda: settings_service.system_values()[0].get("enabled_course_types"),
                                     encryption_key=secret)  # invitation codes can be shown again
    from app.rag.course_retriever import IndexedCourseRetriever

    # retrieval from the published course indexes (index/current.json); no scanner here, so this object can
    # never publish an index (rebuilds belong to the worker job with scan_document, S4/Z11)
    services.course_retriever = IndexedCourseRetriever(settings.data_path())
    from app.platform.course_scope import CourseScopes

    services.course_scopes = CourseScopes(services)
    services.component_manager = ComponentManager(services, settings)
    services.components = services.component_manager.initial()
    return services
