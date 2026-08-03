"""Main entry point for macro rendering."""
import argparse
import logging
import logging.config
import sys
import uuid
from argparse import ArgumentParser
from pathlib import Path
from urllib.parse import urlparse

import clickhouse_connect
import yaml
from rich_argparse import RawDescriptionRichHelpFormatter

from gflx.clickhouse.macro.engine import MacroRenderEngine

description_text = """
Render a ClickHouse ETL script with deduplication and SCD2 history tracking

1) Target replicated table.
CREATE TABLE IF NOT EXISTS {{ db-local ]}.{{ table }}_local ON CLUSTER {{ replicated-cluster }} (
{{ id-struct }},
{{ start-at }} Date|DateTime,
{{ loaded-at }} Date|DateTime,
{{ is-deleted }} Bool|UInt8,
{{ is-closed }} Bool|UInt8,
attrs
)
ENGINE = ReplicatedReplacingMergeTree('zk-path', '{replicated-cluster-replica}', {{ loaded-at }}, {{ is-deleted }})
PARTITION BY toStartOfYear({{ start_at }})
ORDER BY ({{ id-struct }}, {{ start-at }});

2) Target distributed table
CREATE TABLE IF NOT EXISTS {{ db }}.{{ table }} ON CLUSTER {{ replicated-cluster }} AS {{ db-local }}.{{ table }}_local
ENGINE = Distributed('{{ replicated-cluster }}', '{{ db-local }}', '{{ table }}_local', xxh3({{ sharding-column }});

3) Stage replicated table
CREATE TABLE IF NOT EXISTS {{ db-local ]}.{{ buf-table }}_local ON CLUSTER {{ replicated-cluster }} (
{{ id-struct }},
{{ start-at }} Date|DateTime,
{{ loaded-at }} Date|DateTime,
{{ is-deleted }} Bool|UInt8,
{{ is-closed }} Bool|UInt8,
attrs
)
ENGINE = ReplicatedMergeTree('zk-path', '{replicated-cluster-replica}')
PARTITION BY ()
ORDER BY ({{ id-struct }}, {{ start-at }});

4) Stage distributed table
CREATE TABLE IF NOT EXISTS {{ db }}.{{ buf-table }} ON CLUSTER {{ replicated-cluster }} AS {{ db-local }}.{{ buf-table }}_local
ENGINE = Distributed('{{ replicated-cluster }}', '{{ db-local }}', '{{ buf-table }}_local', xxh3({{ sharding-column }});
"""  # noqa: E501

#formatted_description = Text.from_markup(description_text, justify="left")

def _url_default_conn(session_id: str = "") -> str:
    base = "clickhouse://default:@localhost:8443/default?verify=False&secure=True&"
    session_settings = {
        "session_id": f"session_{session_id}" if session_id else f"session_{uuid.uuid4().hex[:8]}",
        "max_threads": 8,
        "max_memory_usage": 4294967296,
        "mutations_sync": 1,
        "max_execution_time": 60,
    }
    return base + "&".join([f"{k}={v}" for k, v in session_settings.items()])


def parse_url(url: str) -> bool:
    """Parse clickhouse url.

    Args:
    url (str): Url connection

    Returns:
    bool: Valid or not.

    Raises:
    TypeError: If url is invalid
    ValueError: If url is invalid

    """
    parsed = urlparse(url)
    if parsed.scheme != "clickhouse":
        raise ValueError(f"Invalid clickhouse url: {url}")
    if not parsed.netloc or parsed.netloc == "@":
        raise ValueError(f"Invalid clickhouse url: {url}")
    if not parsed.port:
        raise ValueError(f"Invalid clickhouse url: {url}")
    return True


def get_parser() -> ArgumentParser:
    """CLI entry point to render the ClickHouse full ETL macro."""
    parser = argparse.ArgumentParser(
        description=description_text,
        formatter_class=RawDescriptionRichHelpFormatter,
        prog="gflx-macro"
    )
    # Required parameters (Positionals or mandatory options)
    parser.add_argument(
        "--db",
        type=str,
        required=True,
        help="Target ClickHouse database name."
    )
    parser.add_argument(
        "--table",
        required=True,
        type=str,
        help="Target distributed table"
    )
    parser.add_argument(
        "--id-struct",
        required=True,
        type=str,
        help="Entity ID structure (e.g., 'col1 type1, col2 type2,...').",
    )
    parser.add_argument(
        "--id",
        required=True,
        type=str,
        help="Entity ID columns (e.g., 'col1, col2, ...')."
    )
    parser.add_argument(
        "--sharding-column",
        type=str,
        required=True,
        help="Sharding column. The sharding key should be xxh3(column)"
    )
    parser.add_argument(
        "--db-local",
        type=str,
        default="DE_SYSTEM___{db}",
        required=False,
        help="Database used for store replicated tables",
    )
    parser.add_argument(
        "--table-local",
        type=str,
        default="{db_local}.{db}___{table}_local",
        required=False,
        help="Target replicated table"
    )
    parser.add_argument(
        "--buf-table",
        type=str,
        default="{db}.{table}_STAGE_BUF",
        required=False,
        help="A distributed buffer table into which an external system writes data"
    )
    parser.add_argument(
        "--buf-table-local",
        type=str,
        default="{db_local}.{db}___{table}_STAGE_BUF_local",
        required=False,
        help="Replicated buffer table"
    )
    # Optional parameters with default values matching the macro
    parser.add_argument(
        "--start-at",
        type=str,
        default="SNAP_DATE",
        help="Date/DateTime column for creation time."
    )
    parser.add_argument(
        "--loaded-at",
        type=str,
        default="LOAD_DATE",
        help="Date/DateTime column for loading time."
    )
    parser.add_argument(
        "--is-deleted",
        type=str,
        default="DELETED_FLG",
        help="Bool column for deletion flag."
    )
    parser.add_argument(
        "--is-closed",
        type=str,
        default="CLOSED_FLG",
        help="Bool column for closed flag."
    )
    parser.add_argument(
        "--merge-interval",
        type=str,
        default="1 year",
        help="Merge interval for target table."
    )
    parser.add_argument(
        "--replicated-cluster",
        type=str,
        default="isreplicated",
        help="Logical sharded and replicated cluster ID."
    )
    parser.add_argument(
        "--replicated-cluster-replica",
        type=str,
        default="{replicated_cluster}_replica",
        help="Replicated cluster replica identifier macro."
    )
    parser.add_argument(
        "--replicated-cluster-shard",
        type=str,
        default="{replicated_cluster}_shard",
        help="Replicated cluster shard identifier macro."
    )
    parser.add_argument(
        "--dict-cluster",
        type=str,
        default="isdicts",
        help="Logical replicated dict cluster ID."
    )
    parser.add_argument(
        "--dict-cluster-replica",
        type=str,
        default="{dict_cluster}_replica",
        help="Dict cluster replica macro."
    )
    parser.add_argument(
        "--dict-cluster-shard",
        type=str,
        default="{dict_cluster}_shard",
        help="Dict cluster shard macro."
    )
    parser.add_argument(
        "--zk-path",
        type=str,
        default="/clickhouse/tables/{db_local}_{shard}/{table}_local",
        help="ZooKeeper replication path template."
    )
    parser.add_argument(
        "--stage-tmp-prefix",
        type=str,
        default="{db_local}.{db}___{table}_STAGE_TMP",
        help="Prefix for created temporary tables.",
    )
    parser.add_argument(
        "--max_insert_threads",
        required=False,
        type=int,
        default=4,
        help="Number of insert threads"
    )
    parser.add_argument(
        "--min_insert_block_size_bytes",
        required=False,
        type=int,
        default=1073741824,
        help="Minimum insert block size"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute script.",
    )
    parser.add_argument(
        "--url",
        required=False,
        type=str,
        default=_url_default_conn(),
        help="Database connection URL"
    )
    return parser


def parse_args() -> tuple[bool, str, dict[str, str | int | float | bool]]:
    """Parse arguments from sys.argv."""
    args = get_parser().parse_args()

    # Convert parsed arguments into a dictionary for Jinja kwargs
    # We replace hyphens with underscores to match macro parameter names
    macro_params = {k.replace("-", "_"): v for k, v in vars(args).items()
                    if k not in ("execute", "url")}

    return args.execute or False, args.url or "", macro_params


def main(logger: logging.Logger | None = None, log_config: str | dict[str, object] = "logger.yml") -> None:
    """Render or execute macro."""
    if logger is None:
        if isinstance(log_config, str):
            config_path = Path(__file__).parent / "logger.yml"
            with open(config_path, encoding="utf-8") as f:
                config = yaml.safe_load(f)
                logging.config.dictConfig(config)
                logger = logging.getLogger("clickhouse_etl")
        elif isinstance(log_config, dict):
            logging.config.dictConfig(log_config)
            logger = logging.getLogger("clickhouse_etl")

    if logger is None:
        raise ValueError("No logger provided")

    execute, url, macro_params = parse_args()
    if execute:
        if not url or not url.strip():
            raise ValueError("Missing url parameter")
        parse_url(url)
        gen = MacroRenderEngine().execute_macro(
            template_name="scd2.sql",
            macro_name="main",
            client=clickhouse_connect.get_client(dsn=url),
            macro_params=macro_params,
            rollback_macro_name="rollback",
            rollback_macro_params=macro_params
        )
        for stmt, result, op in list(gen):
            if op == 0:
                logger.info(stmt)
            else:
                logger.info(result)
    else:
        sql_stmt = []
        for stmt, settings in list(MacroRenderEngine().parse_macro(
            template_name="scd2.sql",
            macro_name="main",
            macro_params=macro_params)):
            settings_str = ",\n".join([f"{k} = {v}" for k, v in settings.items()])
            stmt_final = f"{stmt} SETTINGS {settings_str}" if settings_str else stmt
            sql_stmt.append(stmt_final)
        # Print the final generated SQL script to stdout
        sys.stdout.write(";\n".join(sql_stmt))


if __name__ == "__main__":
    main()
