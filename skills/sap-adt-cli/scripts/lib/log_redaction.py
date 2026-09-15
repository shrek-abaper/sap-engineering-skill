"""Redaction of secrets in log output.

The filter is installed unconditionally (also for ``--verbose``):
HTTP ``Authorization`` headers, Bearer tokens, ``password=`` style
fields and the literal password plus its Base64 encodings are all
replaced with ``***`` before records reach a handler.
"""
import base64
import logging
import re
from typing import List, Optional

_BASIC_RE = re.compile(r"(?i)(basic\s+)[A-Za-z0-9+/=_\-]{4,}")
_BEARER_RE = re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]{4,}")
# The negative lookahead keeps "Authorization: Basic/Bearer ***" redacted
# by the header patterns instead of being consumed a second time.
_KEYWORD_RE = re.compile(
    r"(?i)\b(authorization|password|passwd|secret|token)(\s*[:=]\s*)"
    r"(?!basic|bearer)(?:'|\")?[^\s,'\";}\]]+"
)


def _secret_variants(secret: str, username: Optional[str] = None) -> List[str]:
    variants = {secret}
    for raw in (secret.encode(),):
        token = base64.b64encode(raw).decode()
        variants.add(token)
        variants.add(token.rstrip("="))
    if username:
        for pair in (f"{username}:{secret}", f"{username.lower()}:{secret}"):
            token = base64.b64encode(pair.encode()).decode()
            variants.add(token)
            variants.add(token.rstrip("="))
    # Longest first so composite tokens are scrubbed first.
    return sorted((v for v in variants if v), key=len, reverse=True)


def redact(text, secret: Optional[str] = None, username: Optional[str] = None) -> str:
    if text is None:
        return text
    out = str(text)
    out = _BASIC_RE.sub(r"\1***", out)
    out = _BEARER_RE.sub(r"\1***", out)
    out = _KEYWORD_RE.sub(r"\1\2***", out)
    if secret:
        for variant in _secret_variants(secret, username):
            if variant and variant in out:
                out = out.replace(variant, "***")
    return out


class RedactingFilter(logging.Filter):
    def __init__(self, secret: Optional[str] = None, username: Optional[str] = None):
        super().__init__()
        self.secret = secret
        self.username = username

    def set_secret(self, secret: Optional[str], username: Optional[str] = None) -> None:
        self.secret = secret
        self.username = username

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:  # never let logging itself crash a command
            message = str(record.msg)
        record.msg = redact(message, self.secret, self.username)
        record.args = ()
        return True


# One process-wide filter so the HTTP client can feed it the live password.
filter_instance = RedactingFilter()


def configure_logging(verbose: bool = False) -> RedactingFilter:
    """Install redaction on the root logger; verbose only changes the level."""
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s", force=True)
    root = logging.getLogger()
    for handler in root.handlers:
        handler.addFilter(filter_instance)
    root.addFilter(filter_instance)
    root.setLevel(level)
    return filter_instance


def set_secret(secret: Optional[str], username: Optional[str] = None) -> None:
    filter_instance.set_secret(secret, username)
