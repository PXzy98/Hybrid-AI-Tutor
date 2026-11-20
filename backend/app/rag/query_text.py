"""Text handling for course retrieval (S14): a light stemmer, logistics synonyms and typo correction.

No dependency beyond the standard library and scikit-learn's stop-word list. Questions are matched against
the course material by words, so a paraphrase ("when does the course end?") or a misspelling ("wat is a
noise marjin") has to be brought closer to the words of the material first. Corrections and synonyms are
only ever *added* to the question, the student's own words stay.
"""
import re
from difflib import SequenceMatcher

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

_TOKEN = re.compile(r"(?u)\b\w\w+\b")

# Words of course logistics that students phrase in many ways. A question that contains one word of a group
# also searches for the others. Kept short and generic: they widen the search, they never remove words.
SYNONYM_GROUPS: tuple[frozenset[str], ...] = tuple(frozenset(g.split()) for g in (
    "end ends ending finish finished complete completion expire expires deadline deadlines due cutoff",
    "book books textbook textbooks reading readings reference",
    "grade grades grading graded score scores scoring mark marks weight weighted percent percentage",
    "prerequisite prerequisites prereq prereqs background experience requirement requirements",
    "submit submitted submission submissions hand turn deliver upload",
    "team group partner partners collaborate collaboration together classmate classmates",
    "cheat sheet sheets notes bring allowed permitted",
    "certificate certificates certification credential",
    "miss missed skip skipped late",
    "recitation recitations section sections tutorial tutorials",
))


def stem(word: str) -> str:
    """A small suffix stripper (plurals, -ing, -ed, -ly, final -e): charge, charging, charged agree."""
    w = word
    if len(w) <= 3 or w.isdigit():
        return w
    if w.endswith("ies") and len(w) > 4:
        w = w[:-3] + "y"
    elif w.endswith("sses"):
        w = w[:-2]
    elif w.endswith("s") and not w.endswith(("ss", "us", "is")):
        w = w[:-1]
    for suffix in ("ing", "ed", "ly"):
        if w.endswith(suffix) and len(w) - len(suffix) >= 3:
            w = w[:-len(suffix)]
            if len(w) > 3 and w[-1] == w[-2] and w[-1] not in "lsz":
                w = w[:-1]  # running -> runn -> run
            break
    if w.endswith("e") and len(w) > 4:
        w = w[:-1]
    return w


def words(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def analyze(text: str) -> list[str]:
    """Stemmed unigrams and bigrams without stop words (the word channel of the index and of the queries)."""
    stems = [stem(w) for w in words(text) if w not in ENGLISH_STOP_WORDS]
    return stems + [f"{a} {b}" for a, b in zip(stems, stems[1:], strict=False)]


def synonyms(question: str) -> list[str]:
    """The other words of every synonym group the question touches."""
    asked = set(words(question))
    extra: list[str] = []
    for group in SYNONYM_GROUPS:
        if asked & group:
            extra += sorted(group - asked)
    return extra


class Vocabulary:
    """The unigram stems of an index with their document frequency, for typo correction."""

    def __init__(self, counts: dict[str, int]) -> None:
        self.df = {w: n for w, n in counts.items() if " " not in w}
        self._by_length: dict[int, list[str]] = {}
        for w in self.df:
            self._by_length.setdefault(len(w), []).append(w)

    def correct(self, word: str, cutoff: float = 0.8) -> str | None:
        """The most similar stem of the index for a word the index does not know, or None.

        Words shorter than four letters are left alone (too many neighbours). A candidate must have the same
        first letter or the same last two letters; ties go to the more frequent word."""
        stemmed = stem(word)
        if len(stemmed) < 4 or stemmed in self.df:
            return None
        best: tuple[float, int, str] | None = None
        matcher = SequenceMatcher(autojunk=False)
        matcher.set_seq2(stemmed)
        for length in range(len(stemmed) - 2, len(stemmed) + 3):
            for cand in self._by_length.get(length, ()):
                if cand[0] != stemmed[0] and cand[-2:] != stemmed[-2:]:
                    continue
                matcher.set_seq1(cand)
                if matcher.real_quick_ratio() < cutoff or matcher.quick_ratio() < cutoff:
                    continue
                ratio = matcher.ratio()
                if ratio >= cutoff and (best is None or (ratio, self.df[cand]) > best[:2]):
                    best = (ratio, self.df[cand], cand)
        return best[2] if best else None


def expand_question(question: str, vocabulary: Vocabulary | None) -> tuple[str, str]:
    """(the question plus corrected spellings of words the index does not know, logistics synonyms).

    The two parts are scored separately: synonyms count less than the student's own words."""
    fixed = []
    if vocabulary is not None:
        for w in dict.fromkeys(words(question)):
            if w not in ENGLISH_STOP_WORDS and (right := vocabulary.correct(w)):
                fixed.append(right)
    return " ".join([question, *fixed]), " ".join(synonyms(question))
