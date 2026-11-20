"""S14: paraphrased and misspelled questions in course retrieval, the course-wide document-type prior and the
optional semantic step. Fictional course material and a fake encoder only."""
import numpy as np

from app.rag.course_retriever import ASSESSMENT_WEIGHT, IndexedCourseRetriever
from app.rag.query_text import Vocabulary, analyze, expand_question, stem, synonyms

SYLLABUS = """# Fictional Studies 101: syllabus

## Schedule

The course closes on 2030-06-30. Students who miss the cutoff lose their certificate.

## Books

No textbook is required for Fictional Studies.
"""

LECTURE = """# Lecture 2: Quartzzyme kinetics

Quartzzyme kinetics describe how fast a quartzzyme reaction runs. The rate constant of the reaction
depends on temperature, and the glimmerwave method measures it directly.
"""

HOMEWORK = """# Homework 2

Problem 1. Using the glimmerwave method, compute the rate constant of a quartzzyme reaction.
Problem 2. Explain the glimmerwave method and the rate constant of the reaction in one paragraph.
"""


def _material(root, module, name, body):
    path = root / "courses" / "1" / "materials" / str(module) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _course(tmp_path, embedder=None):
    _material(tmp_path, "_course", "syllabus.md", SYLLABUS)
    _material(tmp_path, "_course", "homework_2.md", HOMEWORK)
    _material(tmp_path, 2, "lecture_2.md", LECTURE)
    rag = IndexedCourseRetriever(tmp_path, scan=lambda _: True, embedder=embedder)
    rag.rebuild(1)
    return rag


def _names(chunks):
    return [c.source.rsplit("/", 1)[-1] for c in chunks]


# ------------------------------------------------------------------------------------ text helpers


def test_stem_joins_inflections():
    assert len({stem(w) for w in ("charge", "charges", "charging", "charged")}) == 1
    assert stem("studies") == "study" and stem("running") == "run" and stem("class") == "class"
    assert stem("cpu") == "cpu" and stem("2027") == "2027"


def test_analyze_drops_stop_words_and_adds_bigrams():
    assert analyze("The graphs of the circuits") == ["graph", "circuit", "graph circuit"]


def test_synonyms_add_the_other_words_of_a_group_only():
    extra = synonyms("when does the course end")
    assert {"finish", "deadline", "due"} <= set(extra) and "end" not in extra
    assert synonyms("how do plants grow") == []


def test_vocabulary_corrects_misspellings_and_leaves_known_or_short_words():
    vocab = Vocabulary({"margin": 3, "marine": 1, "cour": 5, "textbook": 2, "noise": 4})
    assert vocab.correct("marjin") == "margin"
    assert vocab.correct("textbok") == "textbook"
    assert vocab.correct("courses") is None  # known
    assert vocab.correct("noi") is None  # too short
    assert vocab.correct("zzzzzz") is None


def test_expand_question_keeps_the_original_words_and_separates_synonyms():
    vocab = Vocabulary({"margin": 3, "noise": 4})
    asked, extra = expand_question("what is a noise marjin", vocab)
    assert asked.startswith("what is a noise marjin") and asked.endswith("margin") and extra == ""
    assert expand_question("plain words", None) == ("plain words", "")
    assert "deadline" in expand_question("when is it due", None)[1]


# --------------------------------------------------------------------------------- lexical retrieval


def test_paraphrase_finds_the_syllabus(tmp_path):
    rag = _course(tmp_path)
    for question in ("When does the course end?", "by what date must I be finished", "whats the deadline"):
        assert _names(rag.retrieve(1, None, question, 1, question_kind="logistics")) == ["syllabus.md"]


def test_misspelled_question_finds_the_lecture(tmp_path):
    rag = _course(tmp_path)
    assert _names(rag.retrieve(1, 2, "how fast is a quartzimes reaktion", 1)) == ["lecture_2.md"]
    assert _names(rag.retrieve(1, None, "wat is a quartzzime kinetix", 1)) == ["lecture_2.md"]


def test_course_wide_concept_questions_weight_homework_down(tmp_path):
    rag = _course(tmp_path)
    question = "glimmerwave method rate constant quartzzyme reaction"
    wide = {c.source.rsplit("/", 1)[-1]: c.score for c in rag.retrieve(1, None, question, 3)}
    logistics = {c.source.rsplit("/", 1)[-1]: c.score
                 for c in rag.retrieve(1, None, question, 3, question_kind="logistics")}
    assert ASSESSMENT_WEIGHT < 1
    assert abs(wide["homework_2.md"] - logistics["homework_2.md"] / 1.5 * ASSESSMENT_WEIGHT) < 1e-5
    assert abs(wide["lecture_2.md"] - logistics["lecture_2.md"]) < 1e-5  # module material is untouched


# ------------------------------------------------------------------------------------ semantic step

_TOPICS = {  # a fake encoder: words of one meaning share a dimension
    0: {"close", "closes", "end", "ends", "finish", "cutoff", "deadline"},
    1: {"book", "books", "textbook", "buy"},
    2: {"quartzzyme", "kinetics", "reaction", "rate"},
}


def _fake_embedder(texts):
    out = np.zeros((len(texts), 4), dtype=np.float32)
    for row, text in enumerate(texts):
        low = text.lower()
        for dim, words in _TOPICS.items():
            out[row, dim] = sum(w in low for w in words)
        out[row, 3] = 0.01
    norms = np.linalg.norm(out, axis=1, keepdims=True)
    return out / norms


def test_semantic_step_finds_a_passage_without_a_shared_word(tmp_path):
    lexical = _course(tmp_path)
    assert lexical.retrieve(1, None, "what must I buy?", 1, question_kind="logistics") == []
    semantic = _course(tmp_path / "s", embedder=_fake_embedder)
    assert (tmp_path / "s" / "courses" / "1" / "index" / "v1" / "embeddings.npy").is_file()
    found = semantic.retrieve(1, None, "what must I buy?", 1, question_kind="logistics")
    assert _names(found) == ["syllabus.md"] and "textbook" in found[0].text


def test_index_without_embeddings_and_a_failing_encoder_fall_back_to_lexical(tmp_path):
    _course(tmp_path)  # built without an embedder: no embeddings.npy
    rag = IndexedCourseRetriever(tmp_path, embedder=_fake_embedder)
    assert rag._snapshot(1).dense is None
    assert _names(rag.retrieve(1, None, "when does the course end", 1, question_kind="logistics")) == [
        "syllabus.md"]

    def broken(_texts):
        raise OSError("model files missing")

    other = tmp_path / "b"
    built = _course(other, embedder=broken)  # rebuild still publishes, without embeddings
    assert not (other / "courses" / "1" / "index" / "v1" / "embeddings.npy").exists()
    assert _names(built.retrieve(1, None, "quartzzyme kinetics", 1)) == ["lecture_2.md"]


def test_stem_is_its_own_stem_so_a_correction_matches_the_index(tmp_path):
    for word in ("impulse", "response", "course", "charges", "studies", "running"):
        assert stem(stem(word)) == stem(word)
    _material(tmp_path, 3, "lecture_3.md", "# Lecture 3\n\nThe impulse of a force changes the momentum.\n")
    rag = IndexedCourseRetriever(tmp_path, scan=lambda _: True)
    rag.rebuild(1)
    assert _names(rag.retrieve(1, None, "what is an impulze", 1)) == ["lecture_3.md"]


def test_embeddings_of_another_encoder_are_not_used(tmp_path):
    def encoder_a(texts):
        return _fake_embedder(texts)

    def encoder_b(texts):
        return _fake_embedder(texts)

    encoder_a.identity, encoder_b.identity = "encoder-a", "encoder-b"
    _course(tmp_path, embedder=encoder_a)
    assert IndexedCourseRetriever(tmp_path, embedder=encoder_a)._snapshot(1).dense is not None
    other = IndexedCourseRetriever(tmp_path, embedder=encoder_b)  # same dimension, another space
    assert other._snapshot(1).dense is None
    assert other.retrieve(1, None, "what must I buy?", 1, question_kind="logistics") == []
