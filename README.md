# gflx-clickhouse-macro

ClickHouse macros library. Enhance your ClickHouse SQL workflows using Jinja2 templates, SQL parser tools, and advanced code generation capabilities.

- **Homepage**: [github.com/gigaflux/gflx-clickhouse-macro](https://github.com/gigaflux/gflx-clickhouse-macro)
- **Documentation**: [github.com/gigaflux/gflx-clickhouse-macro#readme](https://github.com/gigaflux/gflx-clickhouse-macro#readme)
- **Issue Tracker**: [github.com/gigaflux/gflx-clickhouse-macro/issues](https://github.com/gigaflux/gflx-clickhouse-macro/issues)

---

## Features

- **Jinja2 Templating**: Dynamic ClickHouse SQL generation using a powerful text template engine.
- **SQL Syntax Parsing**: Integrated with `sqlglot` for robust ClickHouse SQL dialect validation and transformation.
- **ClickHouse Native Integration**: Built on top of `clickhouse-connect` for seamless connectivity and communication.
- **CLI Utility**: Comes with a built-in command-line tool `gflx-macro` for quick macro expansions.
- **Type Safe**: Full static typing support using modern Python type hints.

## Requirements

- **Python**: `>= 3.10` and `< 3.13`

## Installation

You can install the package directly from PyPI using your favorite package manager:

```bash
pip install gflx-clickhouse-macro
```

Or via UV / Poetry / Hatch:

```bash
uv add gflx-clickhouse-macro
```

## Quick Start

## CLI Usage

The library provides a global CLI script `gflx-macro` to process your templates.

### Global Options & Template Reference

```bash
gflx-macro --help
```

```sql+jinja
1) Target replicated table.
CREATE TABLE IF NOT EXISTS {{ db-local }}.{{ table }}_local ON CLUSTER {{ replicated-cluster }} (
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
ENGINE = Distributed('{{ replicated-cluster }}', '{{ db-local }}', '{{ table }}_local', xxh3({{ sharding-column }}));

3) Stage replicated table
CREATE TABLE IF NOT EXISTS {{ db-local }}.{{ buf-table }}_local ON CLUSTER {{ replicated-cluster }} (
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
ENGINE = Distributed('{{ replicated-cluster }}', '{{ db-local }}', '{{ buf-table }}_local', xxh3({{ sharding-column }}));
```

### Required Options

| Flag | Description |
| :--- | :--- |
| `--db` | Target ClickHouse database name. |
| `--table` | Target distributed table. |
| `--id-struct` | Entity ID structure (e.g., `'col1 type1, col2 type2, ...'`). |
| `--id` | Entity ID columns (e.g., `'col1, col2, ...'`). |
| `--sharding-column` | Sharding column. The sharding key should be `xxh3(column)`. |

### Optional Options

| Flag | Default & Description                                                                                            |
| :--- |:-----------------------------------------------------------------------------------------------------------------|
| `-h`, `--help` | Show this help message and exit.                                                                                 |
| `--db-local` | **Default:** `"DE_SYSTEM___{db}"`<br>Database used to store replicated tables.                                   |
| `--table-local` | **Default:** `"{db_local}.{db}___{table}_local"`<br>Target replicated table.                                     |
| `--buf-table` | **Default:** `"{db}.{table}_STAGE_BUF"`<br>A distributed buffer table into which an external system writes data. |
| `--buf-table-local` | **Default:** `"{db_local}.{db}___{table}_STAGE_BUF_local"`<br>Replicated buffer table.                           |
| `--start-at` | **Default:** `"SNAP_DATE"`<br>Date/DateTime column for creation time.                                            |
| `--loaded-at` | **Default:** `"LOAD_DATE"`<br>Date/DateTime column for loading time.                                             |
| `--is-deleted` | **Default:** `"DELETED_FLG"`<br>Bool column for deletion flag.                                                   |
| `--is-closed` | **Default:** `"CLOSED_FLG"`<br>Bool column for closed flag.                                                      |
| `--merge-interval` | **Default:** `"1 year"`<br>Merge interval for target table.                                                      |
| `--replicated-cluster` | **Default:** `"isreplicated"`<br>Logical sharded and replicated cluster ID.                                      |
| `--replicated-cluster-replica` | **Default:** `"{replicated_cluster}_replica"`<br>Replicated cluster replica identifier macro.                    |
| `--replicated-cluster-shard` | **Default:** `"{replicated_cluster}_shard"`<br>Replicated cluster shard identifier macro.                        |
| `--dict-cluster` | **Default:** `"isdicts"`<br>Logical replicated dict cluster ID.                                                  |
| `--dict-cluster-replica` | **Default:** `"{dict_cluster}_replica"`<br>Dict cluster replica macro.                                           |
| `--dict-cluster-shard` | **Default:** `"{dict_cluster}_shard"`<br>Dict cluster shard macro.                                               |
| `--zk-path` | **Default:** `"/clickhouse/tables/{db_local}_{shard}/{table}_local"`<br>ZooKeeper replication path template.     |
| `--stage-tmp-prefix` | **Default:** `"{db_local}.{db}___{table}_STAGE_TMP"`<br>Prefix for created temporary tables.                     |
| `--max_insert_threads` | **Default:** `4`<br>Number of insert threads.                                                                    |
| `--min_insert_block_size_bytes` | **Default:** `1073741824` (1 GB)<br>Minimum insert block size in bytes.                                          |
| `--execute` | **Default:** `false` (Dry run)<br>Execute the generated script instead of just rendering it.                     |
| `--url` | **Default:** clickhouse://default:@localhost:8443/default?verify=False&secure=True<br>Database connection URL.                                              |

### Python API Usage

Here is a quick example of how to import and use the library in your code:

```python
from gflx.clickhouse.macro.engine import MacroRenderEngine  # Adjust according to your actual internal API

# Initialize your macro processor or connect to ClickHouse
# (Add specific library initialization code examples here)
```

## Development

To set up a local development environment, clone the repository and install the development dependency group.

### Installation

```bash
git clone https://github.com/gigaflux/gflx-clickhouse-macro
cd gflx-clickhouse-macro
```

### Testing & Quality Control

The project uses `pytest` for test suites, `ruff` for linting, and `mdformat` for Markdown checking.

```bash
# Run tests with coverage report
make test-unit [test-integration]

# Lint your code using Ruff
make lint

# Check code formatting
make format

# scan vulnerabilities
make scan
```

### Build and Release

To build the source distribution and wheels:

```bash
make build
```

## License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for more details.

## Authors & Maintainers

Maintained by the **GigaFlux team** (<dev@gigaflux.dev>).
