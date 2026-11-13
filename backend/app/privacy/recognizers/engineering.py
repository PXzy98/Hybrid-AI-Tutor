"""Credentials and infrastructure details a student pastes into a question (task Z11).

- `secret_token` (base layer, every course): API keys and access tokens of common services, JSON web tokens,
  private keys, and the value after "password:" / "token=" style assignments. A leaked credential is
  dangerous in any subject. Entity `SECRET`.
- `internal_address` (ECE profile): private and link-local IPv4 host addresses (10/8, 172.16/12, 192.168/16,
  169.254/16), optionally with a port, and MAC addresses. A network written with a prefix length
  ("192.168.0.0/16") is a textbook example and is kept. Entity `INTERNAL_ADDRESS`.
- `repo_url` (ECE profile): repository URLs on code hosts that name an account
  (github.com/<account>/<repo>, gitlab, bitbucket, the university's GitHub). Entity `REPO_URL`.

Fictional examples in the tests and in eval/privacy-filter/ece_cases.jsonl.
"""
import re

from presidio_analyzer import Pattern, PatternRecognizer, RecognizerResult

from app.core.registry import pii_recognizers

# vendor key formats (fixed prefixes, so a hex or base64 string alone is not enough)
GITHUB_TOKEN = r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}\b|\bgithub_pat_[A-Za-z0-9_]{40,}"
JWT = r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"
# up to its END line, or to the end of the text when it was cut off (not to the end of a line)
PRIVATE_KEY = r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----[\s\S]*?(?:-----END (?:[A-Z]+ )?PRIVATE KEY-----|\Z)"
SECRET_PATTERNS = [
    Pattern("openai-style key", r"\bsk-(?:proj-|ant-)?[A-Za-z0-9_-]{20,}", 0.9),
    Pattern("github token", GITHUB_TOKEN, 0.95),
    Pattern("aws access key", r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b", 0.9),
    Pattern("slack token", r"\bxox[abprs]-[A-Za-z0-9-]{10,}", 0.9),
    Pattern("google api key", r"\bAIza[0-9A-Za-z_-]{35}\b", 0.9),
    Pattern("json web token", JWT, 0.9),
    Pattern("private key", PRIVATE_KEY, 0.95),
]
# "password: hunter22", "api_key = 'abc...'", "my token is X1y2z3...": the value only. A closing quote may
# follow the name, as in {"password": "..."} (JSON) and {'api_key': '...'} (Python).
_SECRET_NAMES = (r"pass(?:word|wd|phrase)?|pwd|api[_ -]?key|secret(?:[_ -]?key)?|access[_ -]?token"
                 r"|auth[_ -]?token|token")
ASSIGNED_SECRET_RE = re.compile(
    rf"\b(?:{_SECRET_NAMES})[\"']?\s*(?:is\s*|[:=]\s*)[\"']?([^\s\"',;}}]{{6,}})", re.I)
# words that follow "token" or "password" in course prose, not values
_NOT_VALUES = {"expired", "invalid", "required", "missing", "rotation", "hashing", "hashed", "storage",
               "generation", "validation", "strength", "manager", "managers", "policy", "policies", "reset"}
# placeholders in teaching code, not values (found by scanning open course material). Only explicit ones: the
# name of a key variable right after "=", unquoted (a reference in code, "?token=API_KEY"); a value that says
# it is a placeholder ("YOUR_PASSWORD", "<your-api-key>", "{{ api_key }}", "xxxxxx"). A quoted or spaced
# constant-like value ('password = "LAB_PASS_2026"', "password: LAB_PASS") or a bracketed value with digits
# or symbols is a real credential.
CONSTANT_NAME_RE = re.compile(r"(?:[A-Z]+_)+(?:KEY|TOKEN|SECRET)")
_PLACEHOLDER_WORD = r"(?:your|example|placeholder|changeme|change[_-]me|replace[_-]?me|dummy|redacted)"
PLACEHOLDER_VALUE_RE = re.compile(
    rf"(?i:(?:[a-z]+[_-])*{_PLACEHOLDER_WORD}(?:[_-][a-z]+)*)"  # YOUR_PASSWORD, example-token
    rf"|<\s*(?i:(?:[a-z]+[ _-])*(?:{_PLACEHOLDER_WORD}|api)(?:[ _-][a-z]+)*)\s*>"  # <your-api-key>
    r"|\{\{?\s*[a-z_]+(?:\.[a-z_]+)*\s*\}?\}|[xX]{4,}|\*{4,}|\.{3,}")  # {{ api_key }}, xxxxxx


_O = r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)"  # one octet
PRIVATE_IPV4 = (rf"(?<![\d.])(?:10\.{_O}\.{_O}\.{_O}|172\.(?:1[6-9]|2\d|3[01])\.{_O}\.{_O}"
                rf"|192\.168\.{_O}\.{_O}|169\.254\.{_O}\.{_O})(?::\d{{2,5}})?(?![\d.]|/\d)")
MAC = r"(?<![\w:-])(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}(?![\w:-])"
REPO_URL = (r"(?:https?://)?(?:www\.)?(?:github\.com|gitlab\.com|bitbucket\.org|github\.uottawa\.ca"
            r"|gitlab\.uottawa\.ca)/[A-Za-z0-9](?:[A-Za-z0-9._-]{0,38})(?:/[A-Za-z0-9._-]+)*/?")


@pii_recognizers.register("secret_token")
class SecretTokenRecognizer(PatternRecognizer):
    """API keys, tokens, JSON web tokens, private keys, and assigned passwords or tokens (entity SECRET)."""

    def __init__(self) -> None:
        super().__init__(supported_entity="SECRET", patterns=SECRET_PATTERNS)

    def analyze(self, text, entities, nlp_artifacts=None, regex_flags=None):
        results = list(super().analyze(text, entities, nlp_artifacts, regex_flags) or [])
        for m in ASSIGNED_SECRET_RE.finditer(text):
            value = m.group(1)
            plain_word = value.isalpha() and len(value) < 12
            if value.lower() in _NOT_VALUES or plain_word:
                continue  # "the token expired", "password is required"
            bare = value.strip("`.,:)]")
            reference = m.start(1) > 0 and text[m.start(1) - 1] == "="
            if PLACEHOLDER_VALUE_RE.fullmatch(bare) or (reference and CONSTANT_NAME_RE.fullmatch(bare)):
                continue  # 'password = "YOUR_PASSWORD"', "token=API_KEY"
            results.append(self._result(m.start(1), m.end(1)))
        return results

    def _result(self, start: int, end: int) -> RecognizerResult:
        explanation = self.build_regex_explanation(self.name, "assigned secret", ASSIGNED_SECRET_RE.pattern,
                                                   0.85, None, ASSIGNED_SECRET_RE.flags)
        return RecognizerResult("SECRET", start, end, 0.85, analysis_explanation=explanation,
                                recognition_metadata={RecognizerResult.RECOGNIZER_NAME_KEY: self.name,
                                                      RecognizerResult.RECOGNIZER_IDENTIFIER_KEY: self.id})


@pii_recognizers.register("internal_address")
class InternalAddressRecognizer(PatternRecognizer):
    """Private IPv4 host addresses (with an optional port) and MAC addresses (entity INTERNAL_ADDRESS)."""

    def __init__(self) -> None:
        patterns = [Pattern("private ipv4", PRIVATE_IPV4, 0.7), Pattern("mac address", MAC, 0.7)]
        super().__init__(supported_entity="INTERNAL_ADDRESS", patterns=patterns)


@pii_recognizers.register("repo_url")
class RepoUrlRecognizer(PatternRecognizer):
    """Repository URLs that name an account on a code host (entity REPO_URL)."""

    def __init__(self) -> None:
        super().__init__(supported_entity="REPO_URL", patterns=[Pattern("repository url", REPO_URL, 0.8)])
