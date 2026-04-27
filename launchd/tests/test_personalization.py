from bot.personalization import render_template


def test_name_placeholder_with_normal_name():
    assert render_template("{name}님 감사합니다", "Jisang Han") == "Jisang Han님 감사합니다"


def test_name_placeholder_with_empty_name_drops_orphan_honorific():
    assert render_template("{name}님 감사합니다", "") == "감사합니다"
    assert render_template("{name}님 감사합니다", None) == "감사합니다"


def test_name_placeholder_with_whitespace_name():
    assert render_template("{name}님 감사합니다", "   ") == "감사합니다"


def test_template_without_placeholder_unchanged():
    assert render_template("댓글 감사합니다! 🙏", "Jisang") == "댓글 감사합니다! 🙏"


def test_template_with_unrelated_brace_token_unchanged():
    assert render_template("안녕하세요 {friend}", "Jisang") == "안녕하세요 {friend}"


def test_template_with_multiple_name_occurrences_all_replaced():
    assert render_template("{name}님 / {name}님", "Han") == "Han님 / Han님"


def test_template_with_mixed_tokens_only_replaces_name():
    assert render_template("{name}님, {other} 참고해주세요", "Han") == "Han님, {other} 참고해주세요"


def test_multi_word_name_gets_whitespace_collapsed():
    assert render_template("{name}님", " Jisang   Han ") == "Jisang Han님"


def test_undefined_lastname_is_stripped():
    assert render_template("{name}님 감사합니다", "JSup undefined") == "JSup님 감사합니다"


def test_null_lastname_is_stripped():
    assert render_template("{name}님 감사합니다", "John null") == "John님 감사합니다"


def test_all_garbage_tokens_name_falls_back_to_empty():
    assert render_template("{name}님 감사합니다", "undefined null") == "감사합니다"


def test_case_insensitive_garbage_token_match():
    assert render_template("{name}님 감사합니다", "Jane UNDEFINED") == "Jane님 감사합니다"
