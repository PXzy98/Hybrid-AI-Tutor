"""Application settings: config.yaml (structure) + .env / environment (secrets, machine-specific URLs).

Precedence, highest first: init kwargs > environment variables > .env > config.yaml > defaults.
The config file is `APP_CONFIG` if set, otherwise `config.yaml` in the repository root.
"""
import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG = REPO_ROOT / "config.yaml"


def config_path() -> Path:
    return Path(os.environ.get("APP_CONFIG") or DEFAULT_CONFIG)


class Section(BaseModel):
    """Base for config sections: unknown keys are errors, so typos fail at startup."""

    model_config = ConfigDict(extra="forbid")


class VerifyConfig(Section):
    checkers: list[str] = ["grounding", "medical_safety", "pii_leak", "profile_leak"]


class RoutingConfig(Section):
    impl: str = "stub"
    threshold: float = Field(0.6, ge=0, le=1)
    force_local_if_not_cloud_safe: bool = True
    stub_score: float = Field(0.0, ge=0, le=1)


class RagConfig(Section):
    impl: str = "stub"
    k: int = Field(4, ge=1)


class PrivacyConfig(Section):
    spacy_model: str = "en_core_web_lg"
    score_threshold: float = Field(0.5, ge=0, le=1)
    entities: list[str] = ["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "STUDENT_ID", "GRADE", "HEALTH_DETAIL"]
    local_only_types: list[str] = ["HEALTH_DETAIL"]
    allow_list: list[str] = []  # course staff names etc. that must never be redacted
    log_raw_text: Literal[False] = False  # privacy invariant 1: cannot be switched on


class SessionsConfig(Section):
    store: str = "sqlite"
    history_turns: int = Field(6, ge=0)


class LevelsConfig(Section):
    basic_below: float = 0.40
    advanced_above: float = 0.70
    hysteresis: float = Field(0.05, ge=0, le=0.2)

    @model_validator(mode="after")
    def _ordered(self):
        if not 0 < self.basic_below < self.advanced_above < 1:
            raise ValueError("levels: need 0 < basic_below < advanced_above < 1")
        return self


class RecommenderConfig(Section):
    ready: float = 0.70
    mastered: float = 0.90


class BktDefaults(Section):
    p_init: float = Field(0.20, gt=0, lt=1)
    learn: float = Field(0.10, ge=0, lt=1)
    slip: float = Field(0.10, ge=0, lt=0.5)
    guess: float = Field(0.25, ge=0, lt=0.5)


class BktOverride(Section):
    """Per-level BKT parameters; unset fields fall back to bkt_defaults."""

    learn: float | None = Field(None, ge=0, lt=1)
    slip: float | None = Field(None, ge=0, lt=0.5)
    guess: float | None = Field(None, ge=0, lt=0.5)


class WeakLikelihood(Section):
    given_mastered: float = Field(0.30, gt=0, lt=1)
    given_not_mastered: float = Field(0.60, gt=0, lt=1)


class RuleConfig(Section):
    last_n: int = Field(5, ge=1)
    weak_penalty: float = Field(0.05, ge=0, le=0.5)


class LearnerConfig(Section):
    knowledge: str = "bkt"
    preference: str = "simple"
    weak_evidence: bool = False
    levels: LevelsConfig = LevelsConfig()
    recommender: RecommenderConfig = RecommenderConfig()
    bkt_defaults: BktDefaults = BktDefaults()
    bkt_by_level: dict[Literal["basic", "intermediate", "advanced"], BktOverride] = {}  # item level -> params
    weak_likelihood: WeakLikelihood = WeakLikelihood()
    rule: RuleConfig = RuleConfig()
    class_summary_min_group: int = Field(5, ge=1)
    instructor_individual_view: bool = False


class AuthConfig(Section):
    session_ttl_hours: float = Field(12, gt=0, le=24 * 30)
    cookie_name: str = "tutor_session"
    cookie_secure: bool = False
    min_password_length: int = Field(10, ge=8)
    max_failed_logins: int = Field(5, ge=1)
    lockout_minutes: float = Field(15, gt=0)


class LocalLLMConfig(Section):
    model: str = "qwen3.5:9b"
    think: Literal[False] = False  # thinking stays off (boundary test: loops, 5-7x latency)
    temperature: float = 0.2
    num_ctx: int = 8192
    timeout_s: float = 60
    max_tokens: int = Field(1024, ge=64)


class UnderstandLLMConfig(Section):
    model: str = "qwen3.5:9b"
    think: Literal[False] = False
    format: Literal["json"] = "json"
    timeout_s: float = 5


class CloudLLMConfig(Section):
    timeout_s: float = 30
    max_tokens: int = 800
    fallback_to_local: bool = True
    history_turns: int = Field(0, ge=0)


class LLMConfig(Section):
    local: LocalLLMConfig = LocalLLMConfig()
    understand: UnderstandLLMConfig = UnderstandLLMConfig()
    cloud: CloudLLMConfig = CloudLLMConfig()


class ContentConfig(Section):
    dir: str = "content/topics"
    serve_unreviewed: bool = False


class CourseConfig(Section):
    topics: list[str]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # SECTION__FIELD overrides one config.yaml value, e.g. PRIVACY__SPACY_MODEL=en_core_web_sm or
        # CONTENT__SERVE_UNREVIEWED=true (used by the Docker image and the demo)
        env_nested_delimiter="__",
    )

    # --- from config.yaml
    pipeline: list[str] = []
    post_response: list[str] = []
    verify: VerifyConfig = VerifyConfig()
    routing: RoutingConfig = RoutingConfig()
    rag: RagConfig = RagConfig()
    privacy: PrivacyConfig = PrivacyConfig()
    sessions: SessionsConfig = SessionsConfig()
    learner: LearnerConfig = LearnerConfig()
    auth: AuthConfig = AuthConfig()
    llm: LLMConfig = LLMConfig()
    content: ContentConfig = ContentConfig()
    courses: dict[str, CourseConfig] = {}

    # --- from the environment / .env
    ollama_url: str = "http://192.168.2.25:11434"
    cloud_base_url: str = "https://api.openai.com/v1"
    cloud_api_key: SecretStr | None = None
    cloud_model: str | None = None
    instructor_username: str | None = None
    instructor_initial_password: SecretStr | None = None
    database_url: str = f"sqlite:///{(REPO_ROOT / 'data' / 'app.db').as_posix()}"

    @field_validator("cloud_api_key", "cloud_model", "instructor_username", "instructor_initial_password",
                     mode="before")
    @classmethod
    def _empty_is_none(cls, v):
        return None if isinstance(v, str) and not v.strip() else v

    @field_validator("database_url", mode="before")
    @classmethod
    def _empty_db_is_default(cls, v):
        if isinstance(v, str) and not v.strip():
            return f"sqlite:///{(REPO_ROOT / 'data' / 'app.db').as_posix()}"
        return v

    @property
    def cloud_enabled(self) -> bool:
        return self.cloud_api_key is not None and bool(self.cloud_model)

    def topics(self, course_id: str = "default") -> list[str]:
        course = self.courses.get(course_id)
        return list(course.topics) if course else []

    def content_dir(self) -> Path:
        p = Path(self.content.dir)
        return p if p.is_absolute() else REPO_ROOT / p

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        yaml_settings = YamlConfigSettingsSource(
            settings_cls, yaml_file=config_path(), yaml_file_encoding="utf-8"
        )
        return init_settings, env_settings, dotenv_settings, yaml_settings, file_secret_settings


@lru_cache
def get_settings() -> Settings:
    path = config_path()
    if not path.exists():
        raise FileNotFoundError(f"config file not found: {path} (set APP_CONFIG or create config.yaml)")
    return Settings()
