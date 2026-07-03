from datetime import UTC, datetime

import pytest

from healthsync.sources.zepp_life import (
    ZeppLifeConfig,
    ZeppLifeSourceError,
    ZeppLifeWeightSource,
)


def make_source(
    responses: list[object],
    *,
    use_profile_fallback: bool = True,
) -> tuple[ZeppLifeWeightSource, list[str], list[dict[str, str]]]:
    urls: list[str] = []
    headers_seen: list[dict[str, str]] = []

    def http_get(url: str, headers: dict[str, str]) -> object:
        urls.append(url)
        headers_seen.append(headers)
        return responses.pop(0)

    source = ZeppLifeWeightSource(
        ZeppLifeConfig(
            host="https://api-mifit.huami.com/",
            user_id="user 123",
            app_token="local-token",
            days=14,
            use_profile_fallback=use_profile_fallback,
        ),
        http_get=http_get,
    )
    return source, urls, headers_seen


def test_zepp_weight_record_maps_to_weight_measurement() -> None:
    source, urls, headers_seen = make_source(
        [
            {
                "weightRecords": [
                    {
                        "date": "2026-06-27 07:15:00",
                        "weight": "72.4",
                        "fat": "18.6",
                        "muscle": "54.4",
                        "privateAccountNote": "not copied",
                    }
                ]
            }
        ]
    )

    measurements = source.fetch_weight_measurements()

    assert len(measurements) == 1
    measurement = measurements[0]
    assert measurement.source == "zepp_life_api"
    assert measurement.measured_at == datetime(2026, 6, 27, 7, 15)
    assert measurement.weight_kg == 72.4
    assert measurement.body_fat_percent == 18.6
    assert measurement.muscle_mass_kg == 54.4
    assert measurement.metadata == {
        "provider": "zepp_life",
        "endpoint": "weightRecords",
        "profile_fallback": False,
        "raw_keys": ["date", "fat", "muscle", "privateAccountNote", "weight"],
    }
    assert urls == [
        "https://api-mifit.huami.com/users/user%20123/members/-1/weightRecords?days=14"
    ]
    assert headers_seen[0]["Apptoken"] == "local-token"


def test_empty_weight_records_returns_empty_when_profile_fallback_disabled() -> None:
    source, urls, _headers_seen = make_source(
        [{"weightRecords": []}],
        use_profile_fallback=False,
    )

    assert source.fetch_weight_measurements() == []
    assert len(urls) == 1


def test_empty_weight_records_uses_profile_latest_weight_fallback() -> None:
    source, urls, _headers_seen = make_source(
        [
            {"weightRecords": []},
            {
                "lastUpdateTime": 1_782_546_300_000,
                "weight": 72.9,
                "bodyFatRate": 18.7,
            },
        ]
    )

    measurements = source.fetch_weight_measurements()

    assert len(measurements) == 1
    measurement = measurements[0]
    assert measurement.weight_kg == 72.9
    assert measurement.body_fat_percent == 18.7
    assert measurement.metadata["endpoint"] == "profile"
    assert measurement.metadata["profile_fallback"] is True
    assert urls == [
        "https://api-mifit.huami.com/users/user%20123/members/-1/weightRecords?days=14",
        "https://api-mifit.huami.com/users/user%20123",
    ]


def test_invalid_response_type_fails_clearly() -> None:
    source, _urls, _headers_seen = make_source(["not-json-object"])

    with pytest.raises(
        ZeppLifeSourceError,
        match="Zepp Life response must be a JSON object or list",
    ):
        source.fetch_weight_measurements()


def test_incomplete_records_fail_when_no_parseable_weight_records_exist() -> None:
    source, _urls, _headers_seen = make_source(
        [{"weightRecords": [{"date": "2026-06-27 07:15:00"}]}]
    )

    with pytest.raises(
        ZeppLifeSourceError,
        match="No parseable Zepp Life weight records found",
    ):
        source.fetch_weight_measurements()


def test_config_from_env_requires_session_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ZEPP_HOST", raising=False)
    monkeypatch.setenv("ZEPP_USER_ID", "123")
    monkeypatch.setenv("ZEPP_APP_TOKEN", "token")

    with pytest.raises(
        ZeppLifeSourceError,
        match="Missing required environment variable: ZEPP_HOST",
    ):
        ZeppLifeConfig.from_env()


def test_config_from_env_rejects_invalid_days(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ZEPP_HOST", "api-mifit.huami.com")
    monkeypatch.setenv("ZEPP_USER_ID", "123")
    monkeypatch.setenv("ZEPP_APP_TOKEN", "token")
    monkeypatch.setenv("ZEPP_DAYS", "soon")

    with pytest.raises(ZeppLifeSourceError, match="ZEPP_DAYS must be an integer"):
        ZeppLifeConfig.from_env()


def test_epoch_timestamps_parse_as_utc_regardless_of_local_timezone() -> None:
    source, _urls, _headers = make_source(
        [
            {
                "weightRecords": [
                    {
                        "timestamp": 1750000000000,
                        "weight": 72.5,
                    }
                ]
            }
        ]
    )

    measurements = source.fetch_weight_measurements()

    assert measurements[0].measured_at == datetime(2025, 6, 15, 15, 6, 40, tzinfo=UTC)
