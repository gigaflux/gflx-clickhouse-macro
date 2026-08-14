"""Integration tests."""
import datetime
from typing import TypeAlias

import pytest
from clickhouse_connect.driver.client import Client

from gflx.clickhouse.macro.engine import MacroRenderEngine

TableRow: TypeAlias = tuple[int, str, str, int, int, int, str]

d1 = datetime.datetime.now(tz=datetime.timezone.utc).date() - datetime.timedelta(days=10)
d2 = d1 + datetime.timedelta(days=1)
d3 = d1 + datetime.timedelta(days=2)
d_cold = d1 - datetime.timedelta(400)

def test_check_etl(engine_macro: MacroRenderEngine, client: Client, test_env: tuple[str, str]) -> None:
    """Test scd2 etl script."""
    db, table  = test_env
    params: dict[str, str | int | float | bool] = {"db": db, "table": table, "id_struct": "ID UInt64",
                                                   "id": "ID", "sharding_column": "ID"}

    list(engine_macro.explain_macro(template_name="scd2.sql", macro_name="prepare", client=client, macro_params=params))
    list(engine_macro.execute_macro(template_name="scd2.sql", macro_name="prepare", client=client, macro_params=params))

    list(engine_macro.execute_macro(template_name="scd2.sql", macro_name="merge", client=client, macro_params=params))

    list(engine_macro.explain_macro(template_name="scd2.sql", macro_name="clean", client=client, macro_params=params))

@pytest.mark.xdist_group(name="serial_db")
@pytest.mark.parametrize(
    ("test_id", "insert_data", "data", "data_new"),  # Исправлено: теперь это tuple из строк
    [
        (0, [], [], []),
        (
            1,
            [],
            [(1, d1, d1, False, False, 0, "")],
            [(1, d1, d1, False, False, 0, "")],
        ),
        (
            2,
            [(1, d1, d1, False, False, 0, "")],
            [],
            [(1, d1, d1, False, False, 0, "")],
        ),
        (3, [(1, d1, d1, True, False, 0, "")], [], []),
        (
            4,
            [(1, d1, d1, True, False, 0, "")],
            [(1, d1, d1, False, False, 0, "")],
            [],
        ),
        (
            5,
            [(1, d1, d1, False, False, 0, "")],
            [(1, d1, d1, False, False, 0, "")],
            [(1, d1, d1, False, False, 0, "")],
        ),
        (
            6,
            [
                (1, d1, d1, False, False, 0, ""),
                (1, d1, d1, False, False, 0, ""),
            ],
            [],
            [(1, d1, d1, False, False, 0, "")],
        ),
        (
            7,
            [
                (1, d1, d1, False, False, 0, ""),
                (1, d1, d1, True, False, 0, ""),
            ],
            [],
            [],
        ),
        (8, [(1, d1, d1, False, True, 0, "")], [], [(1, d1, d1, False, True, 0, "")]),
        (
            9,
            [
                (1, d1, d1, False, False, 0, ""),
                (1, d1, d1, False, True, 0, ""),
            ],
            [],
            [(1, d1, d1, False, True, 0, "")],
        ),
        (
            10,
            [
                (1, d1, d1, False, False, 0, ""),
                (1, d1, d2, False, False, 0, ""),
            ],
            [],
            [(1, d1, d2, False, False, 0, "")],
        ),
        (
            11,
            [(1, d1, d2, False, False, 0, "")],
            [(1, d1, d1, False, False, 0, "")],
            [(1, d1, d2, False, False, 0, "")],
        ),
        (
            12,
            [(1, d2, d2, False, False, 1, "")],
            [(1, d1, d1, False, False, 0, "")],
            [
                (1, d1, d1, False, False, 0, ""),
                (1, d2, d2, False, False, 1, ""),
            ],
        ),
        (
            13,
            [(1, d2, d2, False, False, 0, "")],
            [(1, d1, d1, False, False, 0, "")],
            [
                (1, d1, d1, False, False, 0, ""),
            ],
        ),
        (
            14,
            [(1, d1, d2, False, False, 0, "")],
            [(1, d2, d1, False, False, 0, "")],
            [
                (1, d1, d2, False, False, 0, ""),
            ],
        ),
        (
            15,
            [(1, d2, d3, False, False, 1, "")],
            [
                (1, d1, d1, False, False, 0, ""),
                (1, d3, d2, False, False, 2, ""),
            ],
            [(1, d1, d1, False, False, 0, ""), (1, d2, d3, False, False, 1, ""), (1, d3, d2, False, False, 2, "")],
        ),
        (
            16,
            [(2, d1, d1, False, False, 0, "")],
            [(1, d1, d1, False, False, 0, "")],
            [(1, d1, d1, False, False, 0, ""), (2, d1, d1, False, False, 0, "")],
        ),
        (
            17,
            [(1, d_cold, d1, False, False, 0, "")],
            [],
            [],
        ),
        (
            18,
            [(1, d1, d1, False, False, 0, "")],
            [(1, d_cold, d_cold, False, False, 0, "")],
            [
                (1, d_cold, d_cold, False, False, 0, "")
            ],
        ),
        (
            19,
            [(1, d1, d1, False, False, 1, "")],
            [(1, d_cold, d_cold, False, False, 0, "")],
            [
                (1, d_cold, d_cold, False, False, 0, ""),
                (1, d1, d1, False, False, 1, "")
            ],
        ),
        (
            20,
            [
                (1, d1, d1, False, False, 1, "a"),
                (2, d1, d1, False, False, 2, "b"),
                (3, d1, d1, False, False, 3, "c"),
                (4, d1, d1, False, False, 4, "d")
            ],
            [
                (1, d1, d1, False, False, 1, "a"),
                (2, d1, d1, False, False, 2, "b"),
                (3, d1, d1, False, False, 3, "c"),
                (4, d1, d1, False, False, 4, "d")
            ],
            [
                (1, d1, d1, False, False, 1, "a"),
                (2, d1, d1, False, False, 2, "b"),
                (3, d1, d1, False, False, 3, "c"),
                (4, d1, d1, False, False, 4, "d")
            ],
        )
    ],
)
def test_etl1(engine_macro: MacroRenderEngine,
                client: Client,
                test_env: tuple[str, str],
                test_id: int,  # noqa: ARG001
                insert_data: list[TableRow],
                data: list[TableRow],
                data_new: list[TableRow]
                ) -> None:
    """Test scd2 etl script."""
    db, table = test_env
    column_names = ["ID", "SNAP_DATE", "LOAD_DATE", "DELETED_FLG", "CLOSED_FLG", "ATTR1", "ATTR2"]
    params: dict[str, str | int | float | bool] = {"db": db, "table": table, "id_struct": "ID UInt64",
                                                           "id": "ID","sharding_column": "ID"}
    if data:
        client.insert(table=f"{db}.{table}", data=data, column_names=column_names)
    if insert_data:
        client.insert(table=f"{db}.{table}_STAGE_BUF", data=insert_data, column_names=column_names)

    list(engine_macro.execute_macro(template_name="scd2.sql", macro_name="prepare", client=client,
                               macro_params=params))
    list(engine_macro.execute_macro(template_name="scd2.sql", macro_name="merge", client=client,
                               macro_params=params))
    result = client.query(f"SELECT * FROM {db}.{table} FINAL ORDER BY ID, SNAP_DATE").result_rows

    list(engine_macro.execute_macro(template_name="scd2.sql", macro_name="clean", client=client,
                               macro_params=params))
    assert result == data_new

def test_etl2(engine_macro: MacroRenderEngine,
                client: Client,
                test_env: tuple[str, str]) -> None:
    """Test scd2 etl script."""
    db, table = test_env
    column_names = ["ID", "SNAP_DATE", "LOAD_DATE", "DELETED_FLG", "CLOSED_FLG", "ATTR1", "ATTR2"]
    params_main: dict[str, str | int | float | bool] = {"db": db, "table": table, "id_struct": "ID UInt64",
                                                        "id": "ID", "sharding_column": "ID"}
    d_start = datetime.datetime.now(tz=datetime.timezone.utc).date() - datetime.timedelta(days=200)
    data = [
        (i, d_start + datetime.timedelta(days=j), d_start + datetime.timedelta(days=j), False, False, 0, "")
        for i in range(1000) for j in range(100)
    ]
    client.insert(table=f"{db}.{table}_STAGE_BUF", data=data, column_names=column_names)
    list(engine_macro.execute_macro(template_name="scd2.sql", macro_name="main", client=client,
                                    macro_params=params_main))
    rows: int = client.query(f"SELECT COUNT(*) FROM {db}.{table} FINAL").result_rows[0][0]
    assert rows == 1000
