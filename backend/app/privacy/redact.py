from app.core.schemas import PIIEntity

# Set by the fail-closed placeholder privacy filter (until Step 4). When the question is withheld,
# the answer is withheld from storage too: nothing is known about which PII it might repeat.
WITHHELD_QUESTION = "[question withheld: privacy filter not installed]"


def redact_known(text: str, entities: list[PIIEntity]) -> str:
    """Replace every known PII value in `text` with its placeholder.

    Used before storing answers: a local model sees the original question and may repeat a name.
    Longest values first, so that "Alice Tremblay" is replaced before "Alice".
    """
    for e in sorted(entities, key=lambda e: len(e.text), reverse=True):
        if e.text:
            text = text.replace(e.text, e.placeholder)
    return text
