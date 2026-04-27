from bot.auth import _extract_internal_person_urn_from_me_response, _looks_internal_person_urn


def test_extract_internal_person_urn_prefers_internal_profile_identifier():
    data = {
        "data": {
            "plainId": 1548400641,
            "*miniProfile": "urn:li:fs_miniProfile:ACoAAFxKuAEB2uYSY5bKNUovRFAO8QRcvS4wXzg",
        },
        "included": [
            {
                "$type": "com.linkedin.voyager.identity.shared.MiniProfile",
                "dashEntityUrn": "urn:li:fsd_profile:ACoAAFxKuAEB2uYSY5bKNUovRFAO8QRcvS4wXzg",
                "entityUrn": "urn:li:fs_miniProfile:ACoAAFxKuAEB2uYSY5bKNUovRFAO8QRcvS4wXzg",
                "objectUrn": "urn:li:member:1548400641",
                "publicIdentifier": "jisang-han-229681372",
            }
        ],
    }

    assert _extract_internal_person_urn_from_me_response(data) == "urn:li:person:ACoAAFxKuAEB2uYSY5bKNUovRFAO8QRcvS4wXzg"


def test_internal_person_urn_rejects_vanity_slug_style_identifier():
    assert not _looks_internal_person_urn("urn:li:person:jisang-han-229681372")
