"""Unit tests for resolving the configuration: flag, then environment, then default."""

from __future__ import annotations

from pathlib import Path

import pytest

from benethos_yahoo_finance_mcp import settings
from benethos_yahoo_finance_mcp.settings import (
    CACHE_MAX_ENTRIES,
    DEFAULT_TTLS,
    TOKEN_VAR,
    Settings,
    SettingsError,
    load_settings,
)


def test_a_bare_start_gets_the_dataclass_defaults():
    assert load_settings({}, {}) == Settings()


def test_the_flag_wins_over_the_environment():
    env = {"YF_MCP_TRANSPORT": "sse", "YF_MCP_PORT": "9000", "YF_MCP_HOST": "a"}
    resolved = load_settings({"transport": "streamable-http", "port": 8123}, env)
    assert resolved.transport == "streamable-http"
    assert resolved.port == 8123
    assert resolved.host == "a"


def test_a_port_of_zero_on_the_command_line_is_given_not_missing():
    assert load_settings({"port": 0}, {"YF_MCP_PORT": "9000"}).port == 0


class TestCacheSwitch:
    def test_off_unless_set(self):
        assert load_settings({}, {}).cache_enabled is False

    @pytest.mark.parametrize("raw", ["0", "off", "false", "no", ""])
    def test_falsy_values_keep_it_off(self, raw):
        assert load_settings({}, {"YF_MCP_CACHE": raw}).cache_enabled is False

    def test_a_truthy_value_turns_it_on(self, tmp_path):
        env = {"YF_MCP_CACHE": "1", "YF_MCP_CACHE_DIR": str(tmp_path)}
        assert load_settings({}, env).cache_enabled is True

    def test_no_cache_on_the_command_line_wins(self):
        assert (
            load_settings({"cache": False}, {"YF_MCP_CACHE": "1"}).cache_enabled
            is False
        )


class TestCacheDir:
    def test_the_environment_names_it(self, tmp_path):
        env = {"YF_MCP_CACHE": "1", "YF_MCP_CACHE_DIR": str(tmp_path)}
        assert load_settings({}, env).cache_dir == tmp_path

    def test_the_flag_wins(self, tmp_path):
        flags = {"cache": True, "cache_dir": str(tmp_path / "flag")}
        env = {"YF_MCP_CACHE_DIR": str(tmp_path / "env")}
        assert load_settings(flags, env).cache_dir == tmp_path / "flag"

    def test_not_looked_up_while_the_cache_is_off(self, monkeypatch):
        """Finding the platform default can fail without a home directory.

        A server that does not cache must not trip over that.
        """

        def no_home() -> Path:
            raise RuntimeError("Could not determine home directory.")

        monkeypatch.setattr(settings.Path, "home", staticmethod(no_home))
        monkeypatch.setattr(settings.sys, "platform", "linux")
        assert load_settings({}, {}).cache_dir is None

    def test_windows_without_localappdata_stays_under_home(self, monkeypatch, tmp_path):
        """Not the shared temp directory, where another user could plant a file."""
        monkeypatch.setattr(settings.sys, "platform", "win32")
        monkeypatch.setattr(settings.Path, "home", staticmethod(lambda: tmp_path))
        cache_dir = load_settings({}, {"YF_MCP_CACHE": "1"}).cache_dir
        assert (
            cache_dir == tmp_path / "AppData" / "Local" / "benethos-yahoo-finance-mcp"
        )

    def test_no_home_with_the_cache_on_says_what_to_set(self, monkeypatch):
        def no_home() -> Path:
            raise RuntimeError("Could not determine home directory.")

        monkeypatch.setattr(settings.Path, "home", staticmethod(no_home))
        monkeypatch.setattr(settings.sys, "platform", "linux")
        with pytest.raises(SettingsError, match="YF_MCP_CACHE_DIR"):
            load_settings({}, {"YF_MCP_CACHE": "1"})

    def test_the_platform_default_when_on(self, monkeypatch, tmp_path):
        monkeypatch.setattr(settings.sys, "platform", "linux")
        env = {"YF_MCP_CACHE": "1", "XDG_CACHE_HOME": str(tmp_path)}
        assert (
            load_settings({}, env).cache_dir == tmp_path / "benethos-yahoo-finance-mcp"
        )


class TestTtls:
    def test_defaults_when_nothing_is_set(self):
        assert load_settings({}, {}).cache_ttls == DEFAULT_TTLS

    def test_the_environment_overrides_one(self):
        ttls = load_settings({}, {"YF_MCP_CACHE_TTL_QUOTE": "15"}).cache_ttls
        assert ttls["quote"] == 15.0
        assert ttls["news"] == DEFAULT_TTLS["news"]

    def test_an_invalid_environment_value_is_ignored_and_recorded(self):
        resolved = load_settings({}, {"YF_MCP_CACHE_TTL_NEWS": "not-a-number"})
        assert resolved.cache_ttls["news"] == DEFAULT_TTLS["news"]
        assert resolved.ignored == (("YF_MCP_CACHE_TTL_NEWS", "not-a-number"),)

    def test_the_flag_wins_over_the_environment(self):
        flags = {"cache_ttl": ["quote=5"]}
        ttls = load_settings(flags, {"YF_MCP_CACHE_TTL_QUOTE": "15"}).cache_ttls
        assert ttls["quote"] == 5.0

    @pytest.mark.parametrize("item", ["quote", "bogus=5", "quote=soon"])
    def test_an_unusable_flag_is_an_error(self, item):
        with pytest.raises(SettingsError, match="--cache-ttl"):
            load_settings({"cache_ttl": [item]}, {})


class TestCacheMaxEntries:
    def test_the_default(self):
        assert load_settings({}, {}).cache_max_entries == CACHE_MAX_ENTRIES == 10_000

    def test_from_the_environment(self):
        env = {"YF_MCP_CACHE_MAX_ENTRIES": "500"}
        assert load_settings({}, env).cache_max_entries == 500

    def test_the_flag_wins_over_the_environment(self):
        env = {"YF_MCP_CACHE_MAX_ENTRIES": "500"}
        assert load_settings({"cache_max_entries": 50}, env).cache_max_entries == 50

    @pytest.mark.parametrize("raw", ["many", "0", "-5", "1.5"])
    def test_an_unusable_environment_value_is_ignored_and_recorded(self, raw):
        resolved = load_settings({}, {"YF_MCP_CACHE_MAX_ENTRIES": raw})
        assert resolved.cache_max_entries == CACHE_MAX_ENTRIES
        assert resolved.ignored == (("YF_MCP_CACHE_MAX_ENTRIES", raw),)

    @pytest.mark.parametrize("value", [0, -1])
    def test_a_flag_below_one_is_an_error(self, value):
        with pytest.raises(SettingsError, match="--cache-max-entries"):
            load_settings({"cache_max_entries": value}, {})


def test_the_token_stays_out_of_repr():
    resolved = load_settings({}, {TOKEN_VAR: "s3cr3t-token"})
    assert resolved.bearer_token == "s3cr3t-token"
    assert "s3cr3t" not in repr(resolved)


class TestTtlBounds:
    """float() takes nan, inf and negatives: nan broke every write, inf never
    expired."""

    @pytest.mark.parametrize("raw", ["nan", "inf", "-inf", "-1"])
    def test_the_environment_value_is_ignored(self, raw):
        resolved = load_settings({}, {"YF_MCP_CACHE_TTL_QUOTE": raw})
        assert resolved.cache_ttls["quote"] == DEFAULT_TTLS["quote"]
        assert resolved.ignored == (("YF_MCP_CACHE_TTL_QUOTE", raw),)

    @pytest.mark.parametrize("raw", ["nan", "inf", "-5"])
    def test_the_flag_is_an_error(self, raw):
        with pytest.raises(SettingsError, match="finite"):
            load_settings({"cache_ttl": [f"quote={raw}"]}, {})

    def test_zero_still_turns_a_category_off(self):
        assert load_settings({"cache_ttl": ["quote=0"]}, {}).cache_ttls["quote"] == 0


class TestOrigins:
    def test_a_final_slash_is_dropped(self):
        env = {"YF_MCP_ALLOWED_ORIGINS": "http://localhost:8000/, https://a.example"}
        assert load_settings({}, env).allowed_origins == (
            "http://localhost:8000",
            "https://a.example",
        )

    def test_a_port_wildcard_is_kept(self):
        env = {"YF_MCP_ALLOWED_ORIGINS": "http://localhost:*"}
        assert load_settings({}, env).allowed_origins == ("http://localhost:*",)

    @pytest.mark.parametrize("origin", ["localhost:8000", "http://", "http://a/x"])
    def test_an_origin_without_scheme_or_host_stops_the_start(self, origin):
        """Ignoring it would leave the guard on with no hosts: 421 for everyone."""
        with pytest.raises(SettingsError, match="scheme://host"):
            load_settings({}, {"YF_MCP_ALLOWED_ORIGINS": origin})


def test_unusable_environment_values_fall_back_and_are_recorded():
    env = {
        "YF_MCP_TRANSPORT": "carrier-pigeon",
        "YF_MCP_PORT": "eighty",
        "YF_MCP_LOG_LEVEL": "loud",
    }
    resolved = load_settings({}, env)
    assert (resolved.transport, resolved.port, resolved.log_level) == (
        "stdio",
        8000,
        "INFO",
    )
    assert {variable for variable, _ in resolved.ignored} == set(env)


def test_log_level_and_transport_are_case_insensitive():
    env = {"YF_MCP_LOG_LEVEL": "debug", "YF_MCP_TRANSPORT": " SSE "}
    resolved = load_settings({}, env)
    assert (resolved.log_level, resolved.transport) == ("DEBUG", "sse")


class TestHttpPath:
    def test_defaults_per_transport(self):
        assert Settings(transport="streamable-http").http_path == "/mcp"
        assert Settings(transport="sse").http_path == "/sse"

    def test_an_explicit_path_wins(self):
        assert Settings(transport="sse", path="/events").http_path == "/events"


class TestToken:
    def test_unset_is_none(self):
        assert load_settings({}, {}).bearer_token is None

    def test_blank_counts_as_unset(self):
        """`YF_MCP_BEARER_TOKEN=` reads as "off" to everyone who writes it."""
        assert load_settings({}, {TOKEN_VAR: "   "}).bearer_token is None

    def test_value_is_stripped(self):
        assert load_settings({}, {TOKEN_VAR: "  s3cret\n"}).bearer_token == "s3cret"
