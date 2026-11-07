"""Chinese self-introductions ("我是李明轩", "我叫王芳").

spaCy's English model does not find Chinese names.
"""
import re

from presidio_analyzer import EntityRecognizer, RecognizerResult

from app.core.registry import pii_recognizers

CJK = "一-鿿"  # CJK Unified Ideographs
INTRO_RE = re.compile(r"(?:我是|我叫|我的名字是|我名叫)\s*([" + CJK + r"]{2,4})(?=[，,。.\s（(]|$)")


@pii_recognizers.register("zh_person")
class ChinesePersonRecognizer(EntityRecognizer):
    def __init__(self) -> None:
        super().__init__(supported_entities=["PERSON"], name="ChinesePersonRecognizer")

    def load(self) -> None:
        pass

    def analyze(self, text: str, entities: list[str], nlp_artifacts=None) -> list[RecognizerResult]:
        return [RecognizerResult("PERSON", m.start(1), m.end(1), 0.8) for m in INTRO_RE.finditer(text)]
