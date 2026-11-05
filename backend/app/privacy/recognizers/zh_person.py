"""Chinese self-introductions ("\u6211\u662f\u674e\u660e\u8f69", "\u6211\u53eb\u738b\u82b3").

spaCy's English model does not find Chinese names.
"""
import re

from presidio_analyzer import EntityRecognizer, RecognizerResult

from app.core.registry import pii_recognizers

CJK = "\u4e00-\u9fff"  # CJK Unified Ideographs
INTRO_RE = re.compile(
    r"(?:\u6211\u662f|\u6211\u53eb|\u6211\u7684\u540d\u5b57\u662f|\u6211\u540d\u53eb)"
    + r"\s*([" + CJK + r"]{2,4})"
    + r"(?=[\uff0c,\u3002.\s\uff08(]|$)"
)


@pii_recognizers.register("zh_person")
class ChinesePersonRecognizer(EntityRecognizer):
    def __init__(self) -> None:
        super().__init__(supported_entities=["PERSON"], name="ChinesePersonRecognizer")

    def load(self) -> None:
        pass

    def analyze(self, text: str, entities: list[str], nlp_artifacts=None) -> list[RecognizerResult]:
        return [RecognizerResult("PERSON", m.start(1), m.end(1), 0.8) for m in INTRO_RE.finditer(text)]
