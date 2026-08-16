"""Test engine."""
import re
from typing import cast

import pytest
import sqlglot
from clickhouse_connect.driver.client import Client
from jinja2 import TemplateRuntimeError
from sqlglot import exp

from gflx.clickhouse.macro.engine import MacroRenderEngine


@pytest.mark.parametrize(
    ("macro", "params", "expected_value"),
    [
        # Case 1: Empty string column name
        ("create_distributed_table", {"table": "db.TEST", "table_local": "DE_SYSTEM___db.db___TEST_local",
                                      "sharding_column": "ID", "cluster": "cluster"},
         (
            r"CREATE TABLE IF NOT EXISTS db.TEST ON CLUSTER cluster AS DE_SYSTEM___db\.db___TEST_local\r?\n"
            r"ENGINE = Distributed\('cluster', 'DE_SYSTEM___db', 'db___TEST_local', xxh3\(ID\)\)"
          )
         ),
        ("create_distributed_table", {"table": "db.TEST", "table_local": "DE_SYSTEM___db.db___TEST_local",
                                      "sharding_column": "ID1, ID2", "cluster": "cluster"},
         (
            r"CREATE TABLE IF NOT EXISTS db.TEST ON CLUSTER cluster AS DE_SYSTEM___db\.db___TEST_local\r?\n"
            r"ENGINE = Distributed\('cluster', 'DE_SYSTEM___db', 'db___TEST_local', xxh3\(ID1, ID2\)\)"
         )
        ),
        ("create_distributed_table", {"table": "TEST", "table_local": "DE_SYSTEM___db.db___TEST_local",
                                      "sharding_column": "ID", "cluster": "cluster"},
         (
            r"CREATE TABLE IF NOT EXISTS TEST ON CLUSTER cluster AS DE_SYSTEM___db\.db___TEST_local\r?\n"
            r"ENGINE = Distributed\('cluster', 'DE_SYSTEM___db', 'db___TEST_local', xxh3\(ID\)\)"
         )
        ),
        ("create_distributed_table", {"table": "db.TEST", "table_local": "db___TEST_local",
                                      "sharding_column": "ID", "cluster": "cluster"},
         (
            r"CREATE TABLE IF NOT EXISTS db.TEST ON CLUSTER cluster AS db___TEST_local\r?\n"
            r"ENGINE = Distributed\('cluster', 'db', 'db___TEST_local', xxh3\(ID\)\)"
         )
        ),
        ("create_distributed_table", {"table": "TEST", "table_local": "db___TEST_local",
                                      "sharding_column": "ID", "cluster": "cluster"},
         (
            r"CREATE TABLE IF NOT EXISTS TEST ON CLUSTER cluster AS db___TEST_local\r?\n"
            r"ENGINE = Distributed\('cluster', 'default', 'db___TEST_local', xxh3\(ID\)\)"
         )
        ),
        ("sync_replica", {"table": "TEST", "cluster": "cluster"},
        r"SYSTEM SYNC REPLICA ON CLUSTER cluster TEST"),
        ("drop_table", {"table": "TEST", "cluster": "cluster"},
        r"DROP TABLE IF EXISTS TEST ON CLUSTER cluster"),
        ("attach_all_partitions_from", {"table_src": "TEST_SRC", "table_dst": "TEST_DST", "cluster": "cluster"},
        r"ALTER TABLE TEST_DST ON CLUSTER cluster ATTACH PARTITION ALL FROM TEST_SRC")
    ]
)
def test_engine_render_macro_core(engine_macro: MacroRenderEngine,
                                  macro: str,
                                  params: dict[str, str | int | float | bool],
                                  expected_value: str) -> None:
    """Test engine render_macro function."""
    response = engine_macro.render_macro("core.sql", macro, params)
    assert re.match(expected_value, response) is not None

@pytest.mark.parametrize(
    "params",
    [
        {"db": "TEST", "table": "TEST", "id_struct": "ID UInt64", "id": "ID", "sharding_column": "ID"},
        {
            "db": "TEST",
            "table": "TEST",
            "id_struct": "ID UInt64",
            "id": "ID",
            "sharding_column": "ID",
            "replicated_cluster": "replicated",
            "dict_cluster": "all_repplicated",
        },
        {
            "db": "TEST",
            "table": "TEST",
            "id_struct": "ID UInt64",
            "id": "ID",
            "sharding_column": "ID",
            "replicated_cluster": "replicated",
            "replicated_cluster_replica": "{replicated_cluster}_replica_new",
            "replicated_cluster_shard": "{replicated_cluster}_shard_new",
            "dict_cluster": "all_repplicated",
            "dict_cluster_replica": "{dict_cluster}_replica_new",
            "dict_cluster_shard": "{dict_cluster}_shard_new",
        },
        {
            "db": "TEST",
            "table": "TEST",
            "id_struct": "ID UInt64",
            "id": "ID",
            "sharding_column": "ID",
            "db_local": "{db}",
            "table_local": "{db_local}.{table}_local",
            "buf_table": "{db_local}.{table}_STAGE_BUF",
            "buf_table_local": "{db_local}.{table}_STAGE_BUF_local",
            "stage_tmp_prefix": "{db_local}.{table}_STAGE_TMP",
        }
    ],
)
def test_engine_render_macro_init(engine_macro: MacroRenderEngine, params: dict[str, str | int | float | bool]) -> None:
    """Test engine render_macro function."""
    engine_macro.render_macro("scd2.sql", "init", params)
    response = engine_macro._dbt_get_return()
    assert isinstance(response, dict)

    default_params: dict[str, str | int | float | bool] = {
        "db_local": "DE_SYSTEM___{db}",
        "table_local": "{db_local}.{db}___{table}_local",
        "buf_table": "{db}.{table}_STAGE_BUF",
        "buf_table_local": "{db_local}.{db}___{table}_STAGE_BUF_local",
        "start_at": "SNAP_DATE",
        "loaded_at": "LOAD_DATE",
        "is_deleted": "DELETED_FLG",
        "is_closed": "CLOSED_FLG",
        "merge_interval": "1 year",
        "replicated_cluster": "isreplicated",
        "replicated_cluster_replica": "{replicated_cluster}_replica",
        "replicated_cluster_shard": "{replicated_cluster}_shard",
        "dict_cluster": "isdicts",
        "dict_cluster_replica": "{dict_cluster}_replica",
        "dict_cluster_shard": "{dict_cluster}_shard",
        "zk_path": "/clickhouse/tables/{db_local}_{shard}/{table}_local",
        "stage_tmp_prefix": "{db_local}.{db}___{table}_STAGE_TMP",
        "max_insert_threads": 4,
        "min_insert_block_size_bytes": 1073741824
    }

    args = default_params
    args.update(params)
    ctx: dict[str, str | int | bool | float] = {}

    t_vars = {
        'db_local': args["db_local"],
        'table_local': args["table_local"],
        'buf_table': args["buf_table"],
        'buf_table_local': args["buf_table_local"],
        'replicated_cluster_replica': args["replicated_cluster_replica"],
        'replicated_cluster_shard': args["replicated_cluster_shard"],
        'dict_cluster_replica': args["dict_cluster_replica"],
        'dict_cluster_shard': args["dict_cluster_shard"],
        'zk_path': args["zk_path"],
        'stage_tmp_prefix': args["stage_tmp_prefix"]
    }
    ctx.update({
        "db": args["db"],
        "table": args["table"],
        "id_struct": args["id_struct"],
        "id" : args["id"],
        "sharding_column": args["sharding_column"],
        "start_at": args["start_at"],
        "loaded_at": args["loaded_at"],
        "is_deleted": args["is_deleted"],
        "is_closed": args["is_closed"],
        "merge_interval": args["merge_interval"],
        "table_target_full": "{}.{}".format(args["db"], args["table"]),
        "table_target": args["table"],
        "replicated_cluster": args["replicated_cluster"],
        "dict_cluster": args["dict_cluster"],
        "max_insert_threads": args["max_insert_threads"],
        "min_insert_block_size_bytes": args["min_insert_block_size_bytes"],
        "zk_path": args["zk_path"],
        "stage_tmp_prefix": args["stage_tmp_prefix"]
    })

    ctx.update({
        "db_local": str(t_vars["db_local"]).format(**ctx),
        "replicated_cluster_replica": "{" + str(t_vars["replicated_cluster_replica"]).format(**ctx) + "}",
        "replicated_cluster_shard": "{" + str(t_vars["replicated_cluster_shard"]).format(**ctx) + "}",
        "dict_cluster_replica":  "{" + str(t_vars["dict_cluster_replica"]).format(**ctx) + "}",
        "dict_cluster_shard": "{" + str(t_vars["dict_cluster_shard"]).format(**ctx) + "}"
    })

    ctx.update({
        "table_target_full_local": str(t_vars["table_local"]).format(**ctx),
        "table_stage_buf_full": str(t_vars["buf_table"]).format(**ctx),
        "table_stage_buf_full_local": str(t_vars["buf_table_local"]).format(**ctx),
        "stage_tmp_prefix_full": str(t_vars["stage_tmp_prefix"]).format(**ctx),
    })

    ctx.update({
        "table_stage_full": ctx["stage_tmp_prefix_full"],
        "table_stage_full_local": "{}_local".format(ctx["stage_tmp_prefix_full"]),
        "table_stage_hash_full": "{}_HASH".format(ctx["stage_tmp_prefix_full"]),
        "table_stage_hash_full_local": "{}_HASH_local".format(ctx["stage_tmp_prefix_full"]),
        "table_stage_inc_full": "{}_INC".format(ctx["stage_tmp_prefix_full"]),
        "table_stage_inc_full_local": "{}_INC_local".format(ctx["stage_tmp_prefix_full"]),
        "table_stage_time_full": "{}_TIME".format(ctx["stage_tmp_prefix_full"]),
        "table_stage_time_full_local": "{}_TIME_local".format(ctx["stage_tmp_prefix_full"])
    })

    ctx.update({
        "table_stage_buf": str(ctx["table_stage_buf_full"]).split(".")[1],
        "table_stage": str(ctx["table_stage_full"]).split(".")[1],
        "table_stage_hash": str(ctx["table_stage_hash_full"]).split(".")[1],
        "table_stage_inc": str(ctx["table_stage_inc_full"]).split(".")[1],
        "table_stage_time": str(ctx["table_stage_time_full"]).split(".")[1]
    })
    ctx.update(
        {
            "table_stage_zk": str(t_vars["zk_path"]).format(
                db=ctx["db"], db_local=ctx["db_local"], table=ctx["table_stage"], shard=ctx["replicated_cluster_shard"]
            ),
            "table_stage_hash_zk": str(t_vars["zk_path"]).format(
                db=ctx["db"],
                db_local=ctx["db_local"],
                table=ctx["table_stage_hash"],
                shard=ctx["replicated_cluster_shard"],
            ),
            "table_stage_inc_zk": str(t_vars["zk_path"]).format(
                db=ctx["db"],
                db_local=ctx["db_local"],
                table=ctx["table_stage_inc"],
                shard=ctx["replicated_cluster_shard"],
            ),
            "table_stage_time_zk": str(t_vars["zk_path"]).format(
                db=ctx["db"], db_local=ctx["db_local"], table=ctx["table_stage_time"], shard=ctx["dict_cluster_shard"]
            ),
        }
    )
    assert response == ctx

@pytest.mark.parametrize(
("macro", "params"),
[
        ("prepare", {"db": "TEST", "table": "TEST", "id_struct": "ID UInt64", "id": "ID", "sharding_column": "ID"}),
        ("merge", {"db": "TEST", "table": "TEST", "id_struct": "ID UInt64", "id": "ID", "sharding_column": "ID"}),
        ("clean", {"db": "TEST", "table": "TEST", "id_struct": "ID UInt64", "id": "ID", "sharding_column": "ID"}),
        ("rollback", {"db": "TEST", "table": "TEST", "id_struct": "ID UInt64", "id": "ID", "sharding_column": "ID"}),
        ("main", {"db": "TEST", "table": "TEST", "id_struct": "ID UInt64", "id": "ID", "sharding_column": "ID"})
    ]
)
def test_engine_render_macro_scd2(engine_macro: MacroRenderEngine,
                             macro: str,
                             params: dict[str, str | int | float | bool]) -> None:
    """Test engine render_macro function."""
    response = engine_macro.render_macro("scd2.sql", macro, params)
    assert isinstance(response, str)

@pytest.mark.parametrize(
    ("macro", "params", "value"),
    [
        ("init", {}, r"Parameter '.+' is missing or None"),
        ("init", {"db": "TEST"}, r"Parameter '.+' is missing or None"),
        ("init", {"db": "TEST", "table": "TEST"}, r"Parameter '.+' is missing or None"),
        ("init", {"db": "TEST", "table": "TEST", "id_struct": "ID UInt64"},
         r"Parameter '.+' is missing or None"),
        ("init", {"db": "TEST", "table": "TEST", "id_struct": "ID UInt64", "id": "ID"},
         r"Parameter '.+' is missing or None"),
        ("prepare", {}, r"Parameter '.+' is missing or None"),
        ("prepare", {"db": "TEST"}, r"Parameter '.+' is missing or None"),
        ("prepare", {"db": "TEST", "table": "TEST"}, r"Parameter '.+' is missing or None"),
        ("prepare", {"db": "TEST", "table": "TEST", "id_struct": "ID UInt64"},
         r"Parameter '.+' is missing or None"),
        ("prepare", {"db": "TEST", "table": "TEST", "id_struct": "ID UInt64", "id": "ID"},
         r"Parameter '.+' is missing or None"),
        ("merge", {}, r"Parameter '.+' is missing or None"),
        ("merge", {"db": "TEST"}, r"Parameter '.+' is missing or None"),
        ("merge", {"db": "TEST", "table": "TEST"}, r"Parameter '.+' is missing or None"),
        ("merge", {"db": "TEST", "table": "TEST", "id_struct": "ID UInt64"},
         r"Parameter '.+' is missing or None"),
        ("merge", {"db": "TEST", "table": "TEST", "id_struct": "ID UInt64", "id": "ID"},
         r"Parameter '.+' is missing or None"),
        ("clean", {}, r"Parameter '.+' is missing or None"),
        ("clean", {"db": "TEST"}, r"Parameter '.+' is missing or None"),
        ("clean", {"db": "TEST", "table": "TEST"}, r"Parameter '.+' is missing or None"),
        ("clean", {"db": "TEST", "table": "TEST", "id_struct": "ID UInt64"},
         r"Parameter '.+' is missing or None"),
        ("clean", {"db": "TEST", "table": "TEST", "id_struct": "ID UInt64", "id": "ID"},
         r"Parameter '.+' is missing or None"),
        ("rollback", {}, r"Parameter '.+' is missing or None"),
        ("rollback", {"db": "TEST"}, r"Parameter '.+' is missing or None"),
        ("rollback", {"db": "TEST", "table": "TEST"}, r"Parameter '.+' is missing or None"),
        ("rollback", {"db": "TEST", "table": "TEST", "id_struct": "ID UInt64"},
         r"Parameter '.+' is missing or None"),
        ("rollback", {"db": "TEST", "table": "TEST", "id_struct": "ID UInt64", "id": "ID"},
         r"Parameter '.+' is missing or None"),
        ("main", {}, r"Parameter '.+' is missing or None"),
        ("main", {"db": "TEST"}, r"Parameter '.+' is missing or None"),
        ("main", {"db": "TEST", "table": "TEST"}, r"Parameter '.+' is missing or None"),
        ("main", {"db": "TEST", "table": "TEST", "id_struct": "ID UInt64"},
         r"Parameter '.+' is missing or None"),
        ("main", {"db": "TEST", "table": "TEST", "id_struct": "ID UInt64", "id": "ID"},
         r"Parameter '.+' is missing or None"),
    ],
)
def test_engine_render_exception_macro_scd2(engine_macro: MacroRenderEngine,
                                       macro: str,
                                       params: dict[str, str | int | float | bool],
                                       value: str) -> None:
    """Test parameter is missing or None."""
    with pytest.raises(TemplateRuntimeError) as ex:
        engine_macro.render_macro(template_name="scd2.sql", macro_name=macro, macro_params=params)
    assert re.match(value,str(ex.value)) is not None

@pytest.mark.parametrize(
    ("macro", "params"),
    [
        ("prepare", {"db": "TEST", "table": "TEST", "id_struct": "ID UInt64", "id": "ID", "sharding_column": "ID"}),
        ("merge", {"db": "TEST", "table": "TEST", "id_struct": "ID UInt64", "id": "ID", "sharding_column": "ID"}),
        ("clean", {"db": "TEST", "table": "TEST", "id_struct": "ID UInt64", "id": "ID", "sharding_column": "ID"}),
        ("rollback", {"db": "TEST", "table": "TEST", "id_struct": "ID UInt64", "id": "ID", "sharding_column": "ID"}),
        ("main", {"db": "TEST", "table": "TEST", "id_struct": "ID UInt64", "id": "ID", "sharding_column": "ID"}),
     ]
)
def test_engine_parse_macro_scd2(engine_macro: MacroRenderEngine,
                            macro: str,
                            params: dict[str, str | int | float | bool]) -> None:
    """Test engine parse_script function."""
    for stmt, _ in engine_macro.parse_macro(template_name="scd2.sql", macro_name=macro, macro_params=params):
        if not sqlglot.tokenize(stmt):
            continue
        parsed = sqlglot.parse_one(stmt, read="clickhouse")
        sql_text = parsed.sql(dialect="clickhouse")
        drop_class = cast(type[exp.Expression], exp.Drop)
        for drop_node in parsed.find_all(drop_class):
            drop_expr = drop_node.this
            if drop_node.args.get("kind") == "DATABASE":
                pytest.fail(f"Dangerous operation: {sql_text}")
            if drop_node.args.get("kind") == "TABLE":
                table_name = drop_expr.name
                if not re.match(r".*_TMP.*", table_name):
                    pytest.fail(f"Dangerous operation: {sql_text}")

@pytest.mark.parametrize(
    ("macro", "params"),
[
        ("drop_table", {"db": "db", "table": "table", "cluster": "cluster"}),
        ("attach_all_partitions_from", {"table_src": "TEST_SRC", "table_dst": "TEST_DST", "cluster": "cluster"}),
        ("sync_replica", {"table": "TEST", "cluster": "cluster"}),
        ("prepare", {"db": "db", "table": "table", "id_struct": "ID UInt64", "id": "ID", "sharding_column": "ID"}),
        ("merge",  {"db": "db", "table": "table", "id_struct": "ID UInt64", "id": "ID", "sharding_column": "ID"}),
        ("clean",  {"db": "db", "table": "table", "id_struct": "ID UInt64", "id": "ID", "sharding_column": "ID"}),
        ("rollback", {"db": "db", "table": "table", "id_struct": "ID UInt64", "id": "ID", "sharding_column": "ID"}),
        ("main", {"db": "db", "table": "table", "id_struct": "ID UInt64", "id": "ID", "sharding_column": "ID"})
    ],
)
def test_engine_explain_macro_scd2(engine_macro: MacroRenderEngine,
                              client: Client,
                              macro: str,
                              params: dict[str, str | int | float | bool]) -> None:
    """Test engine explain_script function."""
    engine_macro.explain_macro("scd2.sql", macro, client, params)

@pytest.mark.parametrize(
    ("macro", "params"),
    [
        ("drop_table", {"db": "db", "table": "table", "cluster": "cluster"}),
        ("attach_all_partitions_from", {"table_src": "TEST_SRC", "table_dst": "TEST_DST", "cluster": "cluster"}),
        ("sync_replica", {"table": "TEST", "cluster": "cluster"}),
        ("prepare", {"db": "db", "table": "table", "id_struct": "ID UInt64", "id": "ID", "sharding_column": "ID"}),
        ("merge",  {"db": "db", "table": "table", "id_struct": "ID UInt64", "id": "ID", "sharding_column": "ID"}),
        ("clean",  {"db": "db", "table": "table", "id_struct": "ID UInt64", "id": "ID", "sharding_column": "ID"}),
        ("rollback", {"db": "db", "table": "table", "id_struct": "ID UInt64", "id": "ID", "sharding_column": "ID"}),
        ("main", {"db": "db", "table": "table", "id_struct": "ID UInt64", "id": "ID", "sharding_column": "ID"})
    ],
)
def test_engine_execute_macro_scd2(engine_macro: MacroRenderEngine,
                              client: Client,
                              macro: str,
                              params: dict[str, str | int | float | bool]) -> None:
    """Test engine execute_script function."""
    engine_macro.execute_macro("scd2.sql", macro, client, params)
