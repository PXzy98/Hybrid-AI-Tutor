"""X1: web passages are labelled as web sources in the answer prompt, local and cloud."""
from app.core.schemas import AskRequest, Chunk, CloudRequest, PIIResult, RequestContext
from app.llm.cloud_guard import build_cloud_request
from app.prompts import passage_text, render_cloud, render_local
from app.prompts.render import WEB_SOURCE_PREFIX, base_system, material_block

COURSE = Chunk(text="Lists are mutable.", source="course/py/lists.pdf", topic="py", score=1)
WEB = Chunk(text="Python 3.14 is the latest release.", source="https://www.python.org/downloads/",
            topic="web", score=1,
            metadata={"web": True, "title": "Download Python", "url": "https://www.python.org/downloads/"})


def _ctx(passages):
    request = AskRequest(student_id="s", topic="py", question="Which version?")
    return RequestContext(request_id="r", request=request, passages=passages)


def test_web_passage_is_labelled_with_title_and_domain():
    assert passage_text(WEB).startswith("Web source: Download Python (www.python.org)\n")
    assert passage_text(COURSE) == COURSE.text


def test_material_block_separates_web_from_course_and_keeps_numbering():
    block = material_block([passage_text(COURSE), passage_text(WEB)])
    assert block.startswith("Course material:\n[1] Lists are mutable.")
    assert "[2] Web source: Download Python (www.python.org)" in block
    assert block.index("Web sources") > block.index("[1]")
    assert "not course material" in block
    only_web = material_block([passage_text(WEB)])
    assert only_web.startswith("Course material: none was found") and "[1] Web source:" in only_web


def test_prompt_without_web_passages_is_unchanged():
    assert material_block(["a", "b"]) == "Course material:\n[1] a\n\n[2] b"
    user = render_local(_ctx([COURSE]))[-1]["content"]
    assert "Web source" not in user and "[1] Lists are mutable." in user


def test_local_and_cloud_prompts_label_web_passages_and_instruct():
    ctx = _ctx([COURSE, WEB])
    local = render_local(ctx)
    assert "[2] Web source: Download Python (www.python.org)" in local[-1]["content"]
    ctx.pii = PIIResult.model_construct(sanitized_text="Which version?", cloud_safe=True)
    req = build_cloud_request(ctx)
    assert isinstance(req, CloudRequest)
    assert req.passages[1].startswith(WEB_SOURCE_PREFIX)
    cloud = render_cloud(req)
    assert "[2] Web source: Download Python (www.python.org)" in cloud[-1]["content"]
    for messages in (local, cloud):
        assert "never call them course material" in messages[0]["content"]
    assert "never call them course material" in base_system()
