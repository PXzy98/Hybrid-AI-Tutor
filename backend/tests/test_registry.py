import pytest

from app.core.registry import Registry
from app.rag import load_retriever
from app.routing import load_router


def test_register_get_and_names():
    reg: Registry[type] = Registry("thing")

    @reg.register("b")
    class B: ...

    @reg.register("a")
    class A: ...

    assert reg.get("a") is A and "b" in reg and reg.names() == ["a", "b"]


def test_duplicate_name_is_an_error():
    reg: Registry[type] = Registry("thing")
    reg.register("x")(int)
    with pytest.raises(ValueError, match="already registered"):
        reg.register("x")(str)


def test_unknown_name_lists_known_ones():
    reg: Registry[type] = Registry("router")
    reg.register("stub")(int)
    with pytest.raises(KeyError, match="registered: stub"):
        reg.get("nope")


def test_loaders_use_config_names(use_config):
    use_config({"routing": {"stub_score": 0.7}})
    assert load_router("stub").score == 0.7
    assert load_retriever("stub").retrieve("q", "asthma") == []


def test_fixture_retriever_filters_then_falls_back():
    r = load_retriever("fixture")
    out = r.retrieve("How does salt affect blood pressure?", "high_blood_pressure", k=3, kc_ids=["HBP.5"])
    assert out[0].kc_ids == ["HBP.5"]  # filter match first
    assert len(out) == 3  # topped up with other chunks of the topic
    assert r.retrieve("anything", "migraine") == []  # no fixture chunks for this topic
