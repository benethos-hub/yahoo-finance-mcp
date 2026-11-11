"""The prompts: what a client lists, what it renders, and what the text names.

A recipe names tools and fields in backticks. Nothing at runtime notices when
one of them is renamed, the model would simply be sent to a tool that is not
there, so every name is held here to what the server registers and returns.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import re

import pytest

from benethos_yahoo_finance_mcp import yahoo
from benethos_yahoo_finance_mcp.server import build_server

SERVER = build_server()
PROMPTS = asyncio.run(SERVER.list_prompts())
TOOLS = {t.name: t for t in asyncio.run(SERVER.list_tools())}

# A field a recipe names, and where the server provides it: a parameter in a
# tool's input schema, or a key the yahoo function of that name builds.
PARAMETERS = {"methodology": ("get_earnings", "get_estimates")}
RESULT_KEYS = {
    "quoteType": yahoo.get_quote,
    "truncated": yahoo.get_history,
    "not_found": yahoo.get_quotes,
}


def _render(name: str, arguments: dict[str, str]) -> str:
    result = asyncio.run(SERVER.get_prompt(name, arguments))
    [message] = result.messages
    assert message.role == "user"
    return message.content.text


def _placeholders(name: str) -> str:
    """The text with every argument given, as the bundle manifest shows it."""
    prompt = next(p for p in PROMPTS if p.name == name)
    return _render(name, {a.name: f"${{arguments.{a.name}}}" for a in prompt.arguments})


def test_the_client_lists_six_prompts_in_this_order():
    assert [p.name for p in PROMPTS] == [
        "snapshot",
        "compare",
        "earnings_preview",
        "etf_profile",
        "dividend_calendar",
        "find_symbol",
    ]


def test_each_has_a_title_and_a_one_line_description():
    titles = [p.title for p in PROMPTS]
    assert all(titles) and len(set(titles)) == len(titles)
    for prompt in PROMPTS:
        assert prompt.description and "\n" not in prompt.description


def test_each_argument_is_described_and_only_the_first_is_required():
    for prompt in PROMPTS:
        assert all(a.description for a in prompt.arguments), prompt.name
        assert [a.required for a in prompt.arguments] == [True] + [False] * (
            len(prompt.arguments) - 1
        ), prompt.name


@pytest.mark.parametrize("prompt", PROMPTS, ids=lambda p: p.name)
def test_every_name_in_backticks_is_a_tool_or_a_field_it_has(prompt):
    named = set(re.findall(r"`([^`]+)`", _placeholders(prompt.name)))
    unknown = named - set(TOOLS) - set(PARAMETERS) - set(RESULT_KEYS)
    assert not unknown


@pytest.mark.parametrize("field", sorted(PARAMETERS))
def test_a_parameter_a_recipe_names_is_in_those_tools_schemas(field):
    for tool in PARAMETERS[field]:
        assert field in TOOLS[tool].input_schema["properties"], tool


@pytest.mark.parametrize("field", sorted(RESULT_KEYS))
def test_a_result_key_a_recipe_names_is_built_where_it_says(field):
    source = inspect.getsource(inspect.getmodule(RESULT_KEYS[field]))
    assert f'"{field}"' in source


@pytest.mark.parametrize(
    "name", ["snapshot", "compare", "earnings_preview", "etf_profile"]
)
def test_every_data_recipe_ends_with_the_rules(name):
    text = _placeholders(name)
    assert text.endswith("give no buy, sell or hold recommendation.")
    assert "never converted" in text and "GBp" in text


def test_the_arguments_land_in_the_text():
    text = _render("compare", {"symbols": "SAP.DE, MSFT", "period": "3mo"})
    assert "Compare SAP.DE, MSFT over 3mo." in text
    assert "period 3mo" in text


def test_an_optional_argument_left_out_takes_its_default():
    assert "over 1y." in _render("compare", {"symbols": "SAP.DE, MSFT"})
    assert "home exchange" in _render("find_symbol", {"query": "Siemens"})
    assert "listing on Xetra" in _render(
        "find_symbol", {"query": "Siemens", "exchange": "Xetra"}
    )


def test_a_missing_required_argument_is_refused():
    with pytest.raises(ValueError, match="symbol"):
        asyncio.run(SERVER.get_prompt("snapshot", {}))


def test_the_dividend_calendar_ends_with_its_own_rules():
    """It converts on purpose, so the rule that nothing is converted is not its."""
    text = _placeholders("dividend_calendar")
    assert text.endswith("Give no buy, sell or hold recommendation and no tax advice.")
    assert "never converted" not in text
    assert "Pass them to no tool." in text


def test_the_dividend_calendar_defaults_to_this_year_in_euros():
    text = _render("dividend_calendar", {"positions": "SAP.DE:50"})
    assert text.startswith(
        "Build a dividend calendar for the current year in EUR from these "
        "positions: SAP.DE:50."
    )


def test_share_counts_reach_no_log_line(caplog):
    """SPECS §7a promises it, and the SDK logs at debug level too."""
    caplog.set_level(logging.DEBUG)
    _render("dividend_calendar", {"positions": "SAP.DE:4711", "year": "2027"})
    assert "4711" not in caplog.text
