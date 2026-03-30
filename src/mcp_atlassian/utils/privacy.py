"""PII redaction filter for MCP Atlassian.

Redacts sensitive data from text content before it is returned to the LLM.
Applied to all Jira and Confluence content at the preprocessing layer.
Enabled by default; set ``PRIVACY_FILTER_ENABLED=false`` to opt out.

Pattern categories mirror the OTel gateway-collector-config.yaml redaction
processor used in production infrastructure, extended with IBAN and IPv6.

Covered fields (read path only — write path is intentionally unfiltered):
  Jira   : issue summary, description (string + ADF), comment body (string + ADF),
           linked-issue summary, changelog from_string/to_string, custom field
           string values
  Confluence: page title, page body (Markdown output), comment title + body,
              ancestor page titles, user-search title + excerpt

Known limitations (structural, not fixable with regex):
  - Natural-language PII (full names, addresses) is not detected.
  - Fields not listed above (e.g. project/board/sprint names) are not filtered
    as they are system-managed and rarely contain personal data.
  - This is a best-effort, defence-in-depth measure, not a compliance guarantee.
"""

import logging
import os
import re
from collections.abc import Callable

logger = logging.getLogger("mcp-atlassian")


# ---------------------------------------------------------------------------
# Validation helpers (reduce false positives for numeric patterns)
# ---------------------------------------------------------------------------


def _luhn_valid(digits: str) -> bool:
    """Return True if *digits* passes the Luhn checksum algorithm.

    Used to reject sequences of digits that look like credit card numbers
    but are actually order IDs, page IDs, or other numeric identifiers.
    """
    total = 0
    reverse = digits[::-1]
    for i, ch in enumerate(reverse):
        n = int(ch)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def _iban_valid(candidate: str) -> bool:
    """Return True if *candidate* passes the ISO 13616 MOD-97 check.

    Moves the first 4 characters to the end, converts letters to digits
    (A=10 … Z=35), and verifies the remainder mod 97 equals 1.
    """
    rearranged = candidate[4:] + candidate[:4]
    numeric = "".join(
        str(ord(ch) - ord("A") + 10) if ch.isalpha() else ch
        for ch in rearranged
    )
    try:
        return int(numeric) % 97 == 1
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Compiled patterns + validator callbacks
# ---------------------------------------------------------------------------
# Each entry is (compiled_regex, replacement_label, optional_validator).
# The validator receives the full match string and returns False to skip
# replacement when the match fails a secondary check (e.g. Luhn, MOD-97).
# ---------------------------------------------------------------------------

_PatternEntry = tuple[re.Pattern[str], str, Callable[[str], bool] | None]

_PATTERNS: list[_PatternEntry] = [
    # JWT tokens — characteristic 3-part base64url structure
    (
        re.compile(r"eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+"),
        "[REDACTED_JWT]",
        None,
    ),
    # Email addresses
    (
        re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"),
        "[REDACTED_EMAIL]",
        None,
    ),
    # IPv6 addresses (full and compressed forms per RFC 4291)
    (
        re.compile(
            r"(?:"
            r"(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}"           # full
            r"|(?:[0-9a-fA-F]{1,4}:){1,7}:"                         # trailing ::
            r"|:(?::[0-9a-fA-F]{1,4}){1,7}"                         # leading ::
            r"|(?:[0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}"  # one compressed group
            r"|(?:[0-9a-fA-F]{1,4}:){1,5}(?::[0-9a-fA-F]{1,4}){1,2}"
            r"|(?:[0-9a-fA-F]{1,4}:){1,4}(?::[0-9a-fA-F]{1,4}){1,3}"
            r"|(?:[0-9a-fA-F]{1,4}:){1,3}(?::[0-9a-fA-F]{1,4}){1,4}"
            r"|(?:[0-9a-fA-F]{1,4}:){1,2}(?::[0-9a-fA-F]{1,4}){1,5}"
            r"|[0-9a-fA-F]{1,4}:(?::[0-9a-fA-F]{1,4}){1,6}"
            r"|::(?:[fF]{4}(?::0{1,4})?:)?"                         # IPv4-mapped
            r"(?:25[0-5]|(?:2[0-4]|1?[0-9])?[0-9])"
            r"(?:\.(?:25[0-5]|(?:2[0-4]|1?[0-9])?[0-9])){3}"
            r"|::1"                                                   # loopback
            r"|::"                                                    # unspecified
            r")"
        ),
        "[REDACTED_IPV6]",
        None,
    ),
    # IPv4 addresses — GDPR considers IP addresses as PII
    (
        re.compile(r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b"),
        "[REDACTED_IP]",
        None,
    ),
    # Credit card numbers — 13-19 digits with optional spaces/dashes,
    # validated by Luhn algorithm to avoid false positives on numeric IDs.
    (
        re.compile(r"\b(?:\d{4}[- ]?){3,4}\d{1,4}\b"),
        "[REDACTED_CC]",
        lambda m: _luhn_valid(re.sub(r"[- ]", "", m)),
    ),
    # IBAN — 2-letter country code + 2 check digits + up to 30 alphanumerics,
    # validated by ISO 13616 MOD-97 to avoid matching Jira issue keys etc.
    (
        re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{4,30}\b"),
        "[REDACTED_IBAN]",
        _iban_valid,
    ),
    # Inline key=value secrets (e.g. "password=abc123", "token: xyz",
    # "authorization: Bearer <token>").
    # Catches secrets pasted into ticket descriptions as config snippets or curl
    # commands.
    (
        re.compile(
            r"(?i)"
            r"(password|passwd|pwd|passphrase|secret|api[_\-]?key|token"
            r"|bearer|authorization|private[_\-]?key|client[_\-]?secret"
            r"|access[_\-]?token|refresh[_\-]?token)"
            r"([=:\s]+)"
            r"(?:Bearer\s+)?"           # optional "Bearer " prefix before the token
            r"[^\s,;\"'\]\[]{4,}",     # value: at least 4 non-whitespace chars
        ),
        r"\1\2[REDACTED]",
        None,
    ),
]


def _is_enabled() -> bool:
    """Return False only when PRIVACY_FILTER_ENABLED is explicitly set to a falsy value.

    Defaults to enabled so that PII redaction is active without any configuration.
    Set ``PRIVACY_FILTER_ENABLED=false`` (or ``0`` / ``no``) to opt out.
    """
    val = os.getenv("PRIVACY_FILTER_ENABLED", "true").lower()
    return val not in ("false", "0", "no")


def redact(text: str) -> str:
    """Redact PII from *text* and return the sanitised string.

    No-ops and returns the original string when ``text`` is empty, not a
    string, or ``PRIVACY_FILTER_ENABLED`` is set to a falsy value.

    Args:
        text: Plain-text or Markdown content to sanitise.

    Returns:
        Sanitised copy of *text* with PII replaced by labelled placeholders.
    """
    if not text or not isinstance(text, str):
        return text
    if not _is_enabled():
        return text

    for pattern, replacement, validator in _PATTERNS:
        try:
            if validator is None:
                text = pattern.sub(replacement, text)
            else:
                def _replace(
                    m: re.Match[str],
                    r: str = replacement,
                    v: Callable[[str], bool] = validator,  # type: ignore[assignment]
                ) -> str:
                    return r if v(m.group()) else m.group()

                text = pattern.sub(_replace, text)
        except re.error:
            logger.warning(
                "PII filter: error applying pattern %s — skipped",
                pattern.pattern,
            )

    return text
