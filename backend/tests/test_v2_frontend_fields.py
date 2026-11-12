"""Fields the v2 frontend needs (api-v2.md 3.3): local_only on courses, the visibility state of each student
in the member list, and the course types. Fictional data."""
from tests.conftest import csrf_client
from tests.test_ask_v2 import V2, World, _login
from tests.test_learner_v2 import set_mode


def test_courses_say_whether_they_are_local_only(make_client):
    with make_client() as client:
        world = World(client)
        alice = _login(world.app, "alice")
        course = next(c for c in alice.get(f"{V2}/courses").json() if c["id"] == world.course)
        assert course["local_only"] is False
        current = world.prof.get(f"{world.url}/settings").json()
        world.prof.put(f"{world.url}/settings", json={"values": {"local_only": True},
                                                      "version": current["version"]})
        assert alice.get(world.url).json()["local_only"] is True


def test_members_show_who_is_visible_without_an_audited_view(make_client):
    with make_client() as client:
        world = World(client)
        world.consent("alice")
        members = {m["username"]: m for m in world.prof.get(f"{world.url}/members").json()}
        assert members["alice"]["visible_to_instructor"] is False
        assert members["prof"]["visible_to_instructor"] is None
        set_mode(world, "B")
        _login(world.app, "alice").post(f"{world.url}/me/visibility", json={"action": "acknowledge"})
        members = {m["username"]: m for m in world.prof.get(f"{world.url}/members").json()}
        assert members["alice"]["visible_to_instructor"] is True


def test_course_types_need_a_login(make_client):
    with make_client() as client:
        world = World(client)
        types = world.prof.get(f"{V2}/course-types").json()
        assert {"general", "ece", "life_science", "medical_science"} <= set(types)
        assert csrf_client(world.app).get(f"{V2}/course-types").status_code == 401
