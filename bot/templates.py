from __future__ import annotations

import logging

from bot.config import RepliesConfig, TemplateConfig

logger = logging.getLogger(__name__)


def select_template(
    config: RepliesConfig,
    activity_urn: str,
    post_body_text: str,
) -> tuple[list[str], list[str]]:
    matched = _match_template(config, activity_urn, post_body_text)
    root_sentences = list(config.sentences)
    root_dm_messages = list(config.dm.messages)

    if matched is None:
        return root_sentences, root_dm_messages

    sentences = list(matched.sentences) or root_sentences
    dm_messages = list(matched.dm_messages) or root_dm_messages
    return sentences, dm_messages


def _match_template(
    config: RepliesConfig,
    activity_urn: str,
    post_body_text: str,
) -> TemplateConfig | None:
    bound_name = config.post_bindings.get(activity_urn)
    if bound_name:
        template = config.templates.get(bound_name)
        if template is not None:
            logger.debug(
                "Template '%s' selected via post_bindings for %s",
                bound_name,
                activity_urn,
            )
            return template

    if not post_body_text:
        return None

    haystack = post_body_text.lower()
    for name, template in config.templates.items():
        for keyword in template.keywords:
            if keyword.lower() in haystack:
                logger.debug(
                    "Template '%s' selected via keyword '%s' for %s",
                    name,
                    keyword,
                    activity_urn,
                )
                return template

    return None
