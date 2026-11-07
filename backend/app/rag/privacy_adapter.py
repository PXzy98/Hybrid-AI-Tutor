"""Conservative, fail-closed Z11 ScanResult adapter for S4 RAG indexing."""
from collections.abc import Callable

from app.core.schemas import PrivacyProfile
from app.privacy.profiles import ScanResult, scan_document


def privacy_scan_callback(
    profile: PrivacyProfile,
    *, scanner: Callable[[str, PrivacyProfile], ScanResult] = scan_document,
) -> Callable[[str], bool]:
    """Accept a document only if fully scanned with zero sensitive findings."""
    def accepted(text: str) -> bool:
        try:
            result = scanner(text, profile)
        except Exception:
            return False
        return (isinstance(result, ScanResult) and result.scanned is True
                and not result.findings)

    return accepted
