"""Tests for gflx.clickhouse.macro.__main__."""
import logging
import sys
from argparse import ArgumentParser
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from _pytest.capture import CaptureFixture

from gflx.clickhouse.macro.__main__ import get_parser, main, parse_args, parse_url


@pytest.fixture
def mock_render() -> Generator[MagicMock, None, None]:
    """Mock the render_macro method of MacroRenderEngine class."""
    # Path to the CLASS, then the METHOD
    target_path = "gflx.clickhouse.macro.__main__.MacroRenderEngine.render_macro"

    with patch(target_path) as mocked:
        # Define what the mock returns when called
        mocked.return_value = "SELECT 1"
        yield mocked

@pytest.fixture
def mock_execute() -> Generator[MagicMock, None, None]:
    """Mock the render_macro method of MacroRenderEngine class."""
    # Path to the CLASS, then the METHOD
    target_path = "gflx.clickhouse.macro.__main__.MacroRenderEngine.execute_macro"

    with patch(target_path) as mocked:
        # Define what the mock returns when called
        mocked.return_value = "SELECT 1"
        yield mocked

@pytest.mark.parametrize(
    ("url", "status"),
    [
        ("clickhouse://default:@localhost:8443/default?verify=False&secure=True", True),
        ("clickhouse1://default/default?verify=False&secure=True", False),
        ("clickhouse1://default:@localhost:8443/default?verify=False&secure=True", False),
        ("clickhouse1://default:@localhost/default?verify=False&secure=True", False)
    ]
)
def test_main_parse_url(url: str, status: bool) -> None:
    """Test parse_url method."""
    if status:
        assert parse_url(url)
    else:
        with pytest.raises(ValueError, match="Invalid clickhouse url"):
            parse_url(url)

def test_main_get_parser() -> None:
    """Test get_parser method."""
    result = get_parser()
    assert isinstance(result, ArgumentParser)


@pytest.mark.parametrize(
    ("params", "status"),
    [
        ({"db": "TEST", "table": "TEST", "id_struct": "ID UInt64", "id": "ID", "sharding_column": "ID"}, True),
        (
            {
                "db": "TEST",
                "table": "TEST",
                "id_struct": "ID UInt64",
                "id": "ID",
                "sharding_column": "ID",
                "db_local": "DE_SYSTEM___{db}",
            },
            True,
        ),
        ({"db": "TEST"}, False),
        ({"db": "TEST", "table": "TEST"}, False),
        ({"db": "TEST", "table": "TEST", "id_struct": "ID UInt64"}, False),
        ({"db": "TEST", "table": "TEST", "id_struct": "ID UInt64", "id": "ID"}, False)
    ],
)
def test_main_parse_args(capsys: CaptureFixture[str],
                         params: dict[str, str | int | float | bool], status: bool) -> None:
    """Test parse_args method."""
    # 1. Simulate command-line arguments via sys.argv
        # Run the parse_args function
    if status:
        with patch.object(sys, "argv", ["__main__.py"] + [f"--{k.replace('_', '-')}={v}" for k, v in params.items()]):
            result = parse_args()
            expected = (params.get("execute", False), {k: v for k, v in params.items() if k not in ("execute", "url")})
            assert (result[0], {k: v for k, v in result[2].items() if k in params}) == expected
    else:
        with (patch.object(sys, "argv", ["__main__.py"] + [f"--{k.replace('_', '-')}={v}" for k, v in params.items()]),
              pytest.raises(SystemExit) as exit_info):
                parse_args()
        captured = capsys.readouterr()
        assert "the following arguments are required" in captured.err
        assert exit_info.value.code == 2


@pytest.mark.parametrize(
    "params",
    [
        {"db": "TEST", "table": "TEST", "id_struct": "ID UInt64", "id": "ID", "sharding_column": "ID"},
        {"db": "TEST", "table": "TEST", "id_struct": "ID UInt64", "id": "ID", "sharding_column": "ID",
         "db_local": "DE_SYSTEM___{db}"},
    ],
)
def test_main_main_render(capsys: CaptureFixture[str],
                          params: dict[str, str | int | float | bool]) -> None:
    """Test successful CLI execution."""
    # 1. Simulate command-line arguments via sys.argv
    with patch.object(sys, "argv", ["__main__.py"] + [f"--{k.replace('_', '-')}={v}" for k, v in params.items()]):
        main()
    captured = capsys.readouterr()
    assert captured.err == ""
    assert len(captured.out) > 0

@pytest.mark.parametrize(
    "params",
    [
        {"db": "TEST", "table": "TEST", "id_struct": "ID UInt64", "id": "ID", "sharding_column": "ID"},
        {"db": "TEST", "table": "TEST", "id_struct": "ID UInt64", "id": "ID", "sharding_column": "ID",
         "db_local": "DE_SYSTEM___{db}"},
    ],
)
def test_main_main_execute(caplog: pytest.LogCaptureFixture,
                           params: dict[str, str | int | float | bool]) -> None:
    """Test successful CLI execution."""
    # 1. Simulate command-line arguments via sys.argv

    with patch.object(sys, "argv", ["__main__.py", "--execute"] +
                                   [f"--{k.replace('_', '-')}={v}"
                                    for k, v in params.items()]):
        test_logger = logging.getLogger("clickhouse_etl")
        logging.getLogger("sqlglot").setLevel(logging.ERROR)
        main(logger=test_logger)
    errors = [r.message for r in caplog.records if r.levelno >= logging.ERROR]
    assert len(errors) == 0
