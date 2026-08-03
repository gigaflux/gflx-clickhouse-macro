"""test engine."""
from unittest.mock import MagicMock

import pytest
from clickhouse_connect.driver.client import Client
from pytest_mock import MockerFixture

from gflx.clickhouse.macro.engine import MacroRenderEngine


@pytest.fixture
def engine_macro() -> MacroRenderEngine:
    """Return render engine."""
    return MacroRenderEngine()

@pytest.fixture(scope="session")
def client() ->  Client | MagicMock:
    """Return a mocked ClickHouse client for unit tests. No real connection is made."""
    # Create a MagicMock with the spec of the real Client class
    mock_client = MagicMock(spec=Client)

    # Define custom behavior for the 'command' method
    def mock_command(cmd: str) -> str:
        return cmd

    # Bind the side effects to mock
    mock_client.command.side_effect = mock_command

    return mock_client

@pytest.fixture(scope="session", autouse=True)
def mock_get_client(session_mocker: MockerFixture, client: Client | MagicMock) -> Client | MagicMock:
    """Mock get_client for unit tests."""
    session_mocker.patch("clickhouse_connect.get_client", return_value=client)
    return client

