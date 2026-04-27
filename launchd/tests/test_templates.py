from bot.config import DMConfig, RepliesConfig, TemplateConfig
from bot.templates import select_template


def _make_config(templates=None, post_bindings=None, dm_messages=None):
    return RepliesConfig(
        enabled=True,
        sentences=["root-1", "root-2", "root-3"],
        reply_delay_seconds_min=30,
        reply_delay_seconds_max=120,
        post_lookback_days=30,
        polling_min_interval_seconds=900,
        dm=DMConfig(enabled=True, messages=dm_messages or ["root-dm-1"]),
        templates=templates or {},
        post_bindings=post_bindings or {},
    )


def test_urn_binding_takes_priority_over_keywords():
    config = _make_config(
        templates={
            "bound": TemplateConfig(
                keywords=["never-matches"],
                sentences=["bound-sentence"],
                dm_messages=["bound-dm"],
            ),
            "keyword_only": TemplateConfig(
                keywords=["런칭"],
                sentences=["keyword-sentence"],
                dm_messages=["keyword-dm"],
            ),
        },
        post_bindings={"urn:li:activity:111": "bound"},
    )
    sentences, dms = select_template(config, "urn:li:activity:111", "런칭 소식 공유")
    assert sentences == ["bound-sentence"]
    assert dms == ["bound-dm"]


def test_keyword_match_when_no_binding():
    config = _make_config(
        templates={
            "launch": TemplateConfig(
                keywords=["런칭"],
                sentences=["launch-sentence"],
                dm_messages=["launch-dm"],
            )
        }
    )
    sentences, dms = select_template(config, "urn:li:activity:222", "오늘 런칭했습니다!")
    assert sentences == ["launch-sentence"]
    assert dms == ["launch-dm"]


def test_root_fallback_when_nothing_matches():
    config = _make_config(
        templates={
            "launch": TemplateConfig(
                keywords=["not-present"],
                sentences=["should-not-apply"],
            )
        }
    )
    sentences, dms = select_template(config, "urn:li:activity:333", "일상 이야기")
    assert sentences == ["root-1", "root-2", "root-3"]
    assert dms == ["root-dm-1"]


def test_empty_template_sentences_falls_back_to_root_sentences_only():
    config = _make_config(
        templates={
            "partial": TemplateConfig(
                keywords=["런칭"],
                sentences=[],
                dm_messages=["only-dm-override"],
            )
        }
    )
    sentences, dms = select_template(config, "urn:li:activity:444", "런칭 이야기")
    assert sentences == ["root-1", "root-2", "root-3"]
    assert dms == ["only-dm-override"]


def test_keyword_match_is_case_insensitive():
    config = _make_config(
        templates={
            "launch": TemplateConfig(
                keywords=["launch"],
                sentences=["launch-sentence"],
                dm_messages=["launch-dm"],
            )
        }
    )
    sentences, dms = select_template(config, "urn:li:activity:555", "Product LAUNCH today")
    assert sentences == ["launch-sentence"]
    assert dms == ["launch-dm"]


def test_no_post_body_text_uses_bindings_only():
    config = _make_config(
        templates={
            "bound": TemplateConfig(
                sentences=["bound-sentence"],
            )
        },
        post_bindings={"urn:li:activity:666": "bound"},
    )
    sentences, _ = select_template(config, "urn:li:activity:666", "")
    assert sentences == ["bound-sentence"]
