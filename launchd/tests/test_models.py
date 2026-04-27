from contextlib import contextmanager
from datetime import datetime
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _load_module(module_name: str, relative_path: str):
    module_path = Path(__file__).resolve().parents[1] / relative_path
    spec = spec_from_file_location(module_name, module_path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


models = _load_module("bot_models", "bot/models.py")
Author = models.Author
Comment = models.Comment


@contextmanager
def raises(expected_exception: type[BaseException]):
    try:
        yield
    except expected_exception:
        return
    raise AssertionError(f"Expected {expected_exception.__name__}")


def test_valid_author() -> None:
    author = Author(urn="urn:li:person:ABC123xyz", name="Ada")

    assert author.urn == "urn:li:person:ABC123xyz"
    assert author.is_self is False


def test_invalid_author_urn() -> None:
    with raises(Exception):
        Author(urn="urn:li:activity:123", name="Ada")


def test_comment_is_top_level() -> None:
    author = Author(urn="urn:li:person:ABC123xyz", name="Ada")
    top_level_comment = Comment(
        comment_urn="urn:li:comment:(activity:7356579210234150912,7356603887497150465)",
        comment_id="7356603887497150465",
        activity_urn="urn:li:activity:7356579210234150912",
        activity_id="7356579210234150912",
        parent_comment_urn=None,
        author=author,
        text="Thanks!",
        created_at=datetime(2026, 4, 19, 12, 0, 0),
    )
    nested_comment = Comment(
        comment_urn="urn:li:comment:(activity:7356579210234150912,7356603887497150466)",
        comment_id="7356603887497150466",
        activity_urn="urn:li:activity:7356579210234150912",
        activity_id="7356579210234150912",
        parent_comment_urn="urn:li:comment:(activity:7356579210234150912,7356603887497150465)",
        author=author,
        text="Reply",
        created_at=datetime(2026, 4, 19, 12, 1, 0),
    )

    assert top_level_comment.is_top_level is True
    assert nested_comment.is_top_level is False


def test_frozen_model_raises() -> None:
    author = Author(urn="urn:li:person:ABC123xyz", name="Ada")

    with raises(Exception):
        author.name = "Grace"
