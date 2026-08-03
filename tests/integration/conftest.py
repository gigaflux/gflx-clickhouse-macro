"""conftest for integration tests."""
import itertools
import uuid
from collections.abc import Generator, Iterator

import pytest
from clickhouse_connect import get_client
from clickhouse_connect.driver.client import Client

from gflx.clickhouse.macro.engine import MacroRenderEngine


@pytest.fixture
def engine_macro() -> MacroRenderEngine:
    """Return render engine."""
    return MacroRenderEngine()

@pytest.fixture(scope="session")
def client() -> Generator[Client, None, None]:
    """Return connection to CliCkhouse."""
    test_session_id = f"pytest_session_{uuid.uuid4().hex[:8]}"

    session_settings = {
        "session_id": test_session_id,
        "max_threads": 8,
        "max_memory_usage": 4294967296,
        "mutations_sync": 1,
        "max_execution_time": 60
    }

    client = get_client(
        host="localhost",
        port=8443,
        username="default",
        password="",
        database="default",
        secure=True,
        verify=False,
        settings=session_settings
    )

    yield client
    client.close()

@pytest.fixture(scope="session")
def global_counter() -> Iterator[int]:
    """Counter."""
    return itertools.count(start=1)

@pytest.fixture
def test_env(global_counter: Iterator[int], client: Client) -> Generator[tuple[str, str], None, None]:
    """Create a test table."""
    counter = next(global_counter)
    db = f"TESTSCD2_{counter}"
    db_local = f"DE_SYSTEM___{db}"
    isreplicated_cluster="isreplicated"
    isreplicated_shard = "{" + f"{isreplicated_cluster}" + "_shard}"
    isreplicated_replica="{" + f"{isreplicated_cluster}" + "_replica}"
    table = f"TEST{counter}"
    table_local = f"{db}___{table}_local"
    stage_table = f"{table}_STAGE_BUF"
    stage_table_local = f"{db}___{stage_table}_local"
    zk_path = f"/clickhouse/tables/{db_local}_{isreplicated_shard}/{table_local}"
    zk_stage_path = f"/clickhouse/tables/{db_local}_{isreplicated_shard}/{stage_table_local}"
    create_tables_script = [
    f"""
CREATE TABLE IF NOT EXISTS {db_local}.{table_local} ON CLUSTER {isreplicated_cluster} (
ID UInt64,
SNAP_DATE Date,
LOAD_DATE Date,
DELETED_FLG Bool,
CLOSED_FLG Bool,
ATTR1 Int64,
ATTR2 String )
ENGINE = ReplicatedReplacingMergeTree('{zk_path}', '{isreplicated_replica}', LOAD_DATE, DELETED_FLG)
ORDER BY (ID, SNAP_DATE)
PARTITION BY toStartOfYear(SNAP_DATE)
""",
    f"""
CREATE TABLE IF NOT EXISTS {db}.{table} ON CLUSTER {isreplicated_cluster} AS {db_local}.{table_local}
ENGINE = Distributed('{isreplicated_cluster}', '{db_local}', '{table_local}', xxh3(ID))
""",
    f"""
CREATE TABLE IF NOT EXISTS {db_local}.{stage_table_local} ON CLUSTER {isreplicated_cluster} (
ID UInt64,
SNAP_DATE Date,
LOAD_DATE Date,
DELETED_FLG Bool,
CLOSED_FLG Bool,
ATTR1 Int64,
ATTR2 String )
ENGINE = ReplicatedMergeTree('{zk_stage_path}', '{isreplicated_replica}')
ORDER BY (ID, SNAP_DATE)
""",
    f"""
CREATE TABLE IF NOT EXISTS {db}.{stage_table} ON CLUSTER {isreplicated_cluster} AS {db_local}.{stage_table_local}
ENGINE = Distributed('{isreplicated_cluster}', '{db_local}', '{stage_table_local}', xxh3(ID))
"""
    ]

    drop_tables_script = [
        f"DROP TABLE IF EXISTS {db_local}.{stage_table_local} ON CLUSTER {isreplicated_cluster} SYNC",
        f"DROP TABLE IF EXISTS {db}.{stage_table} ON CLUSTER {isreplicated_cluster} SYNC",
        f"DROP TABLE IF EXISTS {db_local}.{table_local} ON CLUSTER {isreplicated_cluster} SYNC",
        f"DROP TABLE IF EXISTS {db}.{table} ON CLUSTER {isreplicated_cluster} SYNC"
    ]

    create_database_script = [
        f"CREATE DATABASE IF NOT EXISTS {db} ON CLUSTER {isreplicated_cluster}",
        f"CREATE DATABASE IF NOT EXISTS {db_local} ON CLUSTER {isreplicated_cluster}",
    ]
    drop_database_script = [
        f"DROP DATABASE IF EXISTS {db} ON CLUSTER {isreplicated_cluster} SYNC",
        f"DROP DATABASE IF EXISTS {db_local} ON CLUSTER {isreplicated_cluster} SYNC"
    ]

    for s in drop_tables_script:
        client.command(s)

    for s in drop_database_script:
        client.command(s)

    for s in create_database_script:
        client.command(s)

    for s in create_tables_script:
        client.command(s)

    yield db, table

    for s in drop_tables_script:
        client.command(s)

    for s in drop_database_script:
        client.command(s)
