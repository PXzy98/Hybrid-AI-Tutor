"""Credentials and infrastructure details a student pastes into a question (task Z11).

- `secret_token` (base layer, every course): API keys and access tokens of common services, JSON web tokens,
  private keys, and the value after "password:" / "token=" style assignments. Z22b adds: names with a prefix
  or suffix (`AWS_SECRET_ACCESS_KEY=`, `API_TOKEN="..."`, `aws_secret_access_key='...'`, also as dict
  entries), `Bearer <token>`, the password in URL user info (`scheme://user:PASSWORD@host`) and "the
  password for X is V" in prose. A leaked credential is dangerous in any subject. Entity `SECRET`.
- `internal_address` (ECE profile): private and link-local IPv4 host addresses (10/8, 172.16/12, 192.168/16,
  169.254/16), optionally with a port, and MAC addresses. A network written with a prefix length
  ("192.168.0.0/16") is a textbook example and is kept. Entity `INTERNAL_ADDRESS`.
- `repo_url` (ECE profile): repository URLs on code hosts that name an account
  (github.com/<account>/<repo>, gitlab, bitbucket, the university's GitHub), also SCP-style
  (`git@github.com:<account>/<repo>.git`, Z22b). Entity `REPO_URL`.

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
# Z22b: a credential name with a prefix or suffix joined by "_" or "-" (AWS_SECRET_ACCESS_KEY, API_TOKEN,
# db-password, aws_secret_access_key) followed by "=" or ":" (a dict entry or a Python argument too). These
# names are wider than the plain ones above, so the value must look like a credential (see _credential_like).
PREFIXED_SECRET_RE = re.compile(
    r"(?<![A-Za-z0-9_-])((?:[A-Za-z0-9]+[_-])*(?:pass(?:word|wd|phrase)?|pwd|key|secret|token)(?:[_-][A-Za-z0-9]+)*)"
    r"[\"']?\s*[:=]\s*[\"']?([^\s\"',;)}]{8,})", re.I)
# A prefixed name is a credential name when its last part is one (AWS_SECRET_ACCESS_KEY, API_TOKEN,
# db_password; not token_count, cache_key_prefix), and a name ending in "key" also needs a credential word
# before it (api_key, secret_access_key; not cache_key, primary_key, sort_key).
_CREDENTIAL_LAST = re.compile(r"(?:pass(?:word|wd|phrase)?|pwd|secret|token|key)$", re.I)
_KEY_QUALIFIER = re.compile(
    r"(?:^|[_-])(?:api|secret|access|private|auth|client|signing|master|encryption|app|service|account"
    r"|session|webhook|license|stripe|aws|ssh|gpg|pgp)(?:[_-]|$)", re.I)
_NOT_CREDENTIAL_PREFIX = re.compile(
    r"(?:^|[_-])(?:max|min|num|n|count|total|page|next|prev|sort|cache|primary|foreign|partition|lookup"
    r"|hash|dict|map|row|column|index|unique)[_-]", re.I)
# a dotted code expression (request.path, "student.id"), not a credential
CODE_EXPRESSION_RE = re.compile(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+")
# "Authorization: Bearer <token>", "'Bearer <token>'"
BEARER_RE = re.compile(r"\bBearer\s+([A-Za-z0-9._~+/=-]{16,})", re.I)
# the password in URL user info: mqtt://user:PASSWORD@host
URL_PASSWORD_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9+.-]*://[^\s:/@]+:([^\s@/]+)@")
# "my Wi-Fi password for the library is X", "the passcode to the lab is X"
PROSE_PASSWORD_RE = re.compile(
    r"\bpass(?:word|phrase|code)\s+(?:for|of|to)\s+(?:[\w'-]+\s+){1,4}?is\s+[\"']?([^\s\"',;]{6,})", re.I)
_PLACEHOLDER_WORD = r"(?:your|example|placeholder|changeme|change[_-]me|replace[_-]?me|dummy|redacted)"
PLACEHOLDER_VALUE_RE = re.compile(
    rf"(?i:(?:[a-z]+[_-])*{_PLACEHOLDER_WORD}(?:[_-][a-z]+)*)"  # YOUR_PASSWORD, example-token
    rf"|<\s*(?i:(?:[a-z]+[ _-])*(?:{_PLACEHOLDER_WORD}|api)(?:[ _-][a-z]+)*)\s*>"  # <your-api-key>
    r"|\{\{?\s*[a-z_]+(?:\.[a-z_]+)*\s*\}?\}|[xX]{4,}|\*{4,}|\.{3,}")  # {{ api_key }}, xxxxxx


_O = r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)"  # one octet
# Z22b: a full stop after the address ends the sentence ("... at 172.16.8.203."); only a digit, ".<digit>"
# (a longer dotted number) or "/<digit>" (a network with a prefix length) after it rules it out
PRIVATE_IPV4 = (rf"(?<![\d.])(?:10\.{_O}\.{_O}\.{_O}|172\.(?:1[6-9]|2\d|3[01])\.{_O}\.{_O}"
                rf"|192\.168\.{_O}\.{_O}|169\.254\.{_O}\.{_O})(?::\d{{2,5}})?(?!\d|\.\d|/\d)")
MAC = r"(?<![\w:-])(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}(?![\w:-])"
REPO_URL = (r"(?:https?://)?(?:www\.)?(?:github\.com|gitlab\.com|bitbucket\.org|github\.uottawa\.ca"
            r"|gitlab\.uottawa\.ca)/[A-Za-z0-9](?:[A-Za-z0-9._-]{0,38})(?:/[A-Za-z0-9._-]+)*/?")
# SCP-style remote, any host: git@github.com:account/repo.git (Z22b)
SCP_REPO_URL = r"\bgit@[A-Za-z0-9.-]+\.[A-Za-z]{2,}:[A-Za-z0-9][A-Za-z0-9._-]*(?:/[A-Za-z0-9._-]+)+"


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
        found = {(r.start, r.end) for r in results}
        for start, end in self._z22b_values(text):
            if (start, end) not in found:
                found.add((start, end))
                results.append(self._result(start, end))
        return results

    @staticmethod
    def _z22b_values(text: str):
        """Spans of the Z22b shapes: prefixed names, Bearer tokens, URL passwords, passwords in prose."""
        for m in PREFIXED_SECRET_RE.finditer(text):
            name, value = m.group(1), m.group(2)
            if not re.search(r"[_-]", name):
                continue  # a plain name: ASSIGNED_SECRET_RE above decides
            if not _credential_name(name):
                continue  # token_count, cache_key, primary_key: not credentials
            bare = value.strip("`.,:)]\"'")
            if bare.isdigit() or CODE_EXPRESSION_RE.fullmatch(bare):
                continue  # token_limit=10000000, cache_key=request.path
            if _credential_like(value, reference=text[m.start(2) - 1] == "="):
                yield _trimmed(m, text, 2)
        for regex in (BEARER_RE, URL_PASSWORD_RE, PROSE_PASSWORD_RE):
            for m in regex.finditer(text):
                if _credential_like(m.group(1), reference=False, short_ok=regex is URL_PASSWORD_RE):
                    yield _trimmed(m, text, 1)

    def _result(self, start: int, end: int) -> RecognizerResult:
        explanation = self.build_regex_explanation(self.name, "assigned secret", ASSIGNED_SECRET_RE.pattern,
                                                   0.85, None, ASSIGNED_SECRET_RE.flags)
        return RecognizerResult("SECRET", start, end, 0.85, analysis_explanation=explanation,
                                recognition_metadata={RecognizerResult.RECOGNIZER_NAME_KEY: self.name,
                                                      RecognizerResult.RECOGNIZER_IDENTIFIER_KEY: self.id})


def _credential_name(name: str) -> bool:
    """A prefixed or suffixed name that names a credential (see _CREDENTIAL_LAST)."""
    if not _CREDENTIAL_LAST.search(name) or _NOT_CREDENTIAL_PREFIX.search(name):
        return False
    return not name.lower().endswith("key") or bool(_KEY_QUALIFIER.search(name[:-3]))


def _trimmed(m: re.Match, text: str, group: int) -> tuple[int, int]:
    """The span of the value without punctuation that ends the sentence ("...KEY=abc123." keeps the stop)."""
    end = m.end(group)
    while end > m.start(group) + 1 and text[end - 1] in ".,:)]`":
        end -= 1
    return m.start(group), end


def _credential_like(value: str, *, reference: bool, short_ok: bool = False) -> bool:
    """A value that looks like a credential, not a word, a placeholder or code: at least 8 characters (6 in
    a URL's user info, where the shape says it is a password) with a digit or a symbol, or 20 characters or
    more in mixed case; never a placeholder, a call or an index, or, right after "=", the name of a key
    variable. "user_profile_settings" and "lambda" stay."""
    bare = value.strip("`.,:)]")
    if PLACEHOLDER_VALUE_RE.fullmatch(bare) or (reference and CONSTANT_NAME_RE.fullmatch(bare)):
        return False
    if re.search(r"[(\[]", bare):
        return False  # a call or an index: os.environ["API_KEY"], get_secret()
    if re.search(r"\d|[^\w]", bare):
        return len(bare) >= (6 if short_ok else 8)
    return len(bare) >= 20 and bare != bare.lower() and bare != bare.upper()


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
        patterns = [Pattern("repository url", REPO_URL, 0.8), Pattern("scp-style remote", SCP_REPO_URL, 0.8)]
        super().__init__(supported_entity="REPO_URL", patterns=patterns)
