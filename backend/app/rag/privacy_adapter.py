"""Conservative, fail-closed Z11 ScanResult adapter for S4 RAG indexing."""
from collections.abc import Callable

from app.core.schemas import PrivacyProfile
from app.privacy.profiles import ScanResult, scan_document


def privacy_scan_callback(
    profile: PrivacyProfile,
    *, scanner: Callable[[str, PrivacyProfile], ScanResult] = scan_document,
) -> Callable[[str], bool]:
    """Accept a document only if it was fully scanned and nothing found is student data.

    `ScanResult.blocking` lists the found types that are student data (student IDs, grades, ID and health-card
    numbers, dates of birth, credentials, personal health details). Names, e-mail addresses and phone numbers
    do not block: course material names its instructors and cites authors (Z11)."""
    def accepted(text: str) -> bool:
        try:
            result = scanner(text, profile)
        except Exception:
            return False
        return (isinstance(result, ScanResult) and result.scanned is True
                and not result.blocking)

    return accepted
