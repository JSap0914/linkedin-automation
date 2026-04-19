import re
from typing import Tuple

COMMENT_RE = re.compile(r"^urn:li:comment:\((?:urn:li:)?activity:(\d+),(\d+)\)$")
ACTIVITY_RE = re.compile(r"^urn:li:activity:(\d+)$")
PERSON_RE = re.compile(r"^urn:li:person:([A-Za-z0-9_\-]+)$")
FSD_PROFILE_RE = re.compile(r"^urn:li:fsd_profile:([A-Za-z0-9_\-]+)$")
_INTERNAL_ID_RE = re.compile(r"^[A-Z][A-Za-z0-9_-]{10,}$")


def parse_comment_urn(urn: str) -> Tuple[str, str]:
    """Returns (activity_id, comment_id). Raises ValueError on invalid format."""
    m = COMMENT_RE.match(urn)
    if not m:
        raise ValueError(f"Invalid URN format: {urn}")
    return m.group(1), m.group(2)


def parse_activity_urn(urn: str) -> str:
    """Returns activity_id numeric string. Raises ValueError on invalid format."""
    m = ACTIVITY_RE.match(urn)
    if not m:
        raise ValueError(f"Invalid URN format: {urn}")
    return m.group(1)


def parse_person_urn(urn: str) -> str:
    """Returns person_id string. Raises ValueError on invalid format."""
    m = PERSON_RE.match(urn)
    if not m:
        raise ValueError(f"Invalid URN format: {urn}")
    return m.group(1)


def person_to_fsd_profile_urn(urn: str) -> str:
    """Convert ``urn:li:person:<ID>`` to ``urn:li:fsd_profile:<ID>`` idempotently.

    Accepts either ``urn:li:person:*`` or ``urn:li:fsd_profile:*`` inputs.
    Rejects vanity slugs (enforces internal-style opaque IDs of length >= 10)
    because the messaging endpoint requires a real internal profile id.
    """
    if not isinstance(urn, str) or not urn:
        raise ValueError(f"Invalid URN format: {urn!r}")

    fsd_match = FSD_PROFILE_RE.match(urn)
    person_match = PERSON_RE.match(urn)

    if fsd_match:
        profile_id = fsd_match.group(1)
    elif person_match:
        profile_id = person_match.group(1)
    else:
        raise ValueError(f"Invalid URN format: {urn}")

    if not _INTERNAL_ID_RE.match(profile_id):
        raise ValueError(f"Profile URN does not look like an internal id: {urn}")

    return f"urn:li:fsd_profile:{profile_id}"
