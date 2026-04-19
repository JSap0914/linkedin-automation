from __future__ import annotations

from copy import deepcopy


_DEFAULTS: dict = {
    "enabled": True,
    "sentences": [
        "{name}님 댓글 감사합니다! 🙏",
        "{name}님 관심 가져주셔서 감사해요 😊",
        "좋은 말씀 감사드립니다!",
    ],
    "reply_delay_seconds_min": 0,
    "reply_delay_seconds_max": 0,
    "post_lookback_days": 30,
    "polling_min_interval_seconds": 60,
    "dm": {
        "enabled": False,
        "only_first_degree_connections": True,
        "auto_accept_pending_invitations": True,
        "messages": [
            "{name}님, 댓글 감사드려요! 시간 되실 때 이야기 나눠요 🙏",
            "{name}님 관심 남겨주셔서 감사해요 😊",
            "좋은 말씀 감사드립니다! 언제든 편하게 연락주세요.",
        ],
        "max_per_day": 30,
        "delay_seconds_min": 0,
        "delay_seconds_max": 0,
    },
    "templates": {},
    "post_bindings": {},
}


def default_config_dict() -> dict:
    return deepcopy(_DEFAULTS)
