from contextlib import contextmanager
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _load_module(module_name: str, relative_path: str):
    module_path = Path(__file__).resolve().parents[1] / relative_path
    spec = spec_from_file_location(module_name, module_path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


urn = _load_module("bot_urn", "bot/urn.py")


@contextmanager
def raises(expected_exception: type[BaseException], match: str):
    try:
        yield
    except expected_exception as exc:
        assert match in str(exc)
    else:
        raise AssertionError(f"Expected {expected_exception.__name__}")


def test_parse_comment_urn_valid() -> None:
    assert urn.parse_comment_urn("urn:li:comment:(activity:7356579210234150912,7356603887497150465)") == (
        "7356579210234150912",
        "7356603887497150465",
    )


def test_parse_comment_urn_valid_full_activity_urn() -> None:
    assert urn.parse_comment_urn(
        "urn:li:comment:(urn:li:activity:7356579210234150912,7356603887497150465)"
    ) == ("7356579210234150912", "7356603887497150465")


def test_parse_activity_urn_valid() -> None:
    assert urn.parse_activity_urn("urn:li:activity:7356579210234150912") == "7356579210234150912"


def test_parse_person_urn_valid() -> None:
    assert urn.parse_person_urn("urn:li:person:ABC123xyz") == "ABC123xyz"


def test_parse_comment_urn_invalid_raises() -> None:
    with raises(ValueError, "Invalid URN format"):
        urn.parse_comment_urn("urn:li:comment:bad-format")


def test_parse_activity_urn_invalid_raises() -> None:
    with raises(ValueError, "Invalid URN format"):
        urn.parse_activity_urn("urn:li:activity:abc")


def test_parse_person_urn_invalid_raises() -> None:
    with raises(ValueError, "Invalid URN format"):
        urn.parse_person_urn("urn:li:person:bad space")


def test_person_to_fsd_profile_urn_from_person_form() -> None:
    assert urn.person_to_fsd_profile_urn(
        "urn:li:person:ACoAAFxKuAEB2uYSY5bKNUovRFAO8QRcvS4wXzg"
    ) == "urn:li:fsd_profile:ACoAAFxKuAEB2uYSY5bKNUovRFAO8QRcvS4wXzg"


def test_person_to_fsd_profile_urn_idempotent_on_fsd_form() -> None:
    assert urn.person_to_fsd_profile_urn(
        "urn:li:fsd_profile:ACoAAFxKuAEB2uYSY5bKNUovRFAO8QRcvS4wXzg"
    ) == "urn:li:fsd_profile:ACoAAFxKuAEB2uYSY5bKNUovRFAO8QRcvS4wXzg"


def test_person_to_fsd_profile_urn_rejects_vanity_slug() -> None:
    with raises(ValueError, "does not look like an internal id"):
        urn.person_to_fsd_profile_urn("urn:li:person:jisang-han-229681372")


def test_person_to_fsd_profile_urn_rejects_invalid_shape() -> None:
    with raises(ValueError, "Invalid URN format"):
        urn.person_to_fsd_profile_urn("not-a-urn")
