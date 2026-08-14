
{% macro init(
    db,
    table,
    id_struct,
    id,
    sharding_column,
    db_local="DE_SYSTEM___{db}",
    table_local="{db_local}.{db}___{table}_local",
    buf_table="{db}.{table}_STAGE_BUF",
    buf_table_local="{db_local}.{db}___{table}_STAGE_BUF_local",
    start_at="SNAP_DATE",
    loaded_at="LOAD_DATE",
    is_deleted="DELETED_FLG",
    is_closed="CLOSED_FLG",
    merge_interval="1 year",
    replicated_cluster="isreplicated",
    replicated_cluster_replica="{replicated_cluster}_replica",
    replicated_cluster_shard="{replicated_cluster}_shard",
    dict_cluster="isdicts",
    dict_cluster_replica="{dict_cluster}_replica",
    dict_cluster_shard="{dict_cluster}_shard",
    zk_path="/clickhouse/tables/{db_local}_{shard}/{table}_local",
    stage_tmp_prefix="{db_local}.{db}___{table}_STAGE_TMP",
    max_insert_threads=4,
    min_insert_block_size_bytes=1073741824,
    params=none
) %}
{#
    Return context parameters

    Parameters:
        db (str): database
        db_local (str): database used for store replicated tables
        table (str): target distributed table
        table_local (str): target replicated table
        buf_table (str): A distributed buffer table into which an external system writes data
        buf_table_local (str): Replicated buffer table
        id_struct (str): entity id struct in format column1 type1,column2 type2,...column type without time column
        id (str): entity id columns if format column1,column2,...column
        sharding_column (str): sharding column
        start_at (str): the name of the DateTime column that stores entity version creating time
        loaded_at (str): the name of the DateTime column that stores the entity version loading time
        is_deleted (str): the name of the Bool column that stores entity version deletion flag
        is_closed (str): the name of the Bool column that stores entity version closed flag
        merge_interval (str): merge interval in the target table
        replicated_cluster (str): logical ClickHouse sharded and replicated cluster
        replicated_cluster_replica (str): Replicated cluster replica macro
        replicated_cluster_shard (str): Replicated cluster shard macro
        dict_cluster (str): logical ClickHouse replicated cluster
        dict_cluster_replica (str): Dict cluster replica macro
        dict_cluster_shard (str): Dict cluster shard macro
        zk_path (str): Zookeeper template path used by the ReplicatedMergeTree engine
        stage_tmp_prefix (str): Prefix for created temporary tables
        max_insert_threads (int): Number of insert threads,
        min_insert_block_size_bytes (int): Minimum insert block size,
        params (dict): Parameters passed from other macros

    Returns:
        str: Dictionary with context parameters
#}

{% set params = params or {} %}
{% do params.update({
    "db": params.db or db,
    "table": params.table or table,
    "id_struct": params.id_struct or id_struct,
    "id": params.id or id,
    "sharding_column": params.sharding_column or sharding_column,
    "db_local": params.db_local or db_local,
    "table_local": params.table_local or table_local,
    "buf_table": params.buf_table or buf_table,
    "buf_table_local": params.buf_table_local or buf_table_local,
    "start_at": params.start_at or start_at,
    "loaded_at": params.loaded_at or loaded_at,
    "is_deleted": params.is_deleted or is_deleted,
    "is_closed": params.is_closed or is_closed,
    "merge_interval": params.merge_interval or merge_interval,
    "replicated_cluster": params.replicated_cluster or replicated_cluster,
    "replicated_cluster_replica": params.replicated_cluster_replica or replicated_cluster_replica,
    "replicated_cluster_shard": params.replicated_cluster_shard or replicated_cluster_shard,
    "dict_cluster": params.dict_cluster or dict_cluster,
    "dict_cluster_replica": params.dict_cluster_replica or dict_cluster_replica,
    "dict_cluster_shard": params.dict_cluster_shard or dict_cluster_shard,
    "zk_path": params.zk_path or zk_path,
    "stage_tmp_prefix": params.stage_tmp_prefix or stage_tmp_prefix,
    "max_insert_threads": params.max_insert_threads or max_insert_threads,
    "min_insert_block_size_bytes": params.min_insert_block_size_bytes or min_insert_block_size_bytes
}) %}

{% set required_fields = ['db', 'table', 'id_struct', 'id', 'sharding_column'] %}

{% for field in required_fields %}
  {% if params[field] is none or params[field] is undefined %}
    {{ exceptions.raise_compiler_error("Parameter '" ~ field ~ "' is missing or None") }}
  {% endif %}
{% endfor %}

{% set t_vars = {
    'db_local': params.db_local,
    'table_local': params.table_local,
    'buf_table': params.buf_table,
    'buf_table_local': params.buf_table_local,
    'replicated_cluster_replica': params.replicated_cluster_replica,
    'replicated_cluster_shard': params.replicated_cluster_shard,
    'dict_cluster_replica': params.dict_cluster_replica,
    'dict_cluster_shard': params.dict_cluster_shard,
    'zk_path': params.zk_path,
    'stage_tmp_prefix': params.stage_tmp_prefix
} %}

{% for key in t_vars.keys() %}
    {% do t_vars.update({key: t_vars[key].replace('{', '{{').replace('}', '}}')}) %}
{% endfor %}
{% set ctx = ctx or {} %}
{% do ctx.update({
    "db": params.db,
    "table": params.table,
    "id_struct": params.id_struct,
    "id" : params.id,
    "sharding_column": params.sharding_column,
    "start_at": params.start_at,
    "loaded_at": params.loaded_at,
    "is_deleted": params.is_deleted,
    "is_closed": params.is_closed,
    "merge_interval": params.merge_interval,
    "table_target_full": "{}.{}".format(params.db, params.table),
    "table_target": params.table,
    "replicated_cluster": params.replicated_cluster,
    "dict_cluster": params.dict_cluster,
    "max_insert_threads": params.max_insert_threads,
    "min_insert_block_size_bytes": params.min_insert_block_size_bytes,
    "zk_path": params.zk_path,
    "stage_tmp_prefix": params.stage_tmp_prefix,
}) %}
{% do ctx.update({
    "db_local": render(t_vars.db_local, **ctx),
    "replicated_cluster_replica": "{" ~ render(t_vars.replicated_cluster_replica, **ctx) ~ "}",
    "replicated_cluster_shard": "{" ~ render(t_vars.replicated_cluster_shard, **ctx) ~ "}",
    "dict_cluster_replica": "{" ~ render(t_vars.dict_cluster_replica, **ctx) ~ "}",
    "dict_cluster_shard": "{" ~ render(t_vars.dict_cluster_shard, **ctx) ~ "}"
}) %}
{% do ctx.update({
    "table_target_full_local": render(t_vars.table_local, **ctx),
    "table_stage_buf_full": render(t_vars.buf_table, **ctx),
    "table_stage_buf_full_local": render(t_vars.buf_table_local, **ctx),
    "stage_tmp_prefix_full": render(t_vars.stage_tmp_prefix, **ctx)
}) %}

{% do ctx.update({
    "table_stage_full": ctx.stage_tmp_prefix_full,
    "table_stage_full_local": "{}_local".format(ctx.stage_tmp_prefix_full),
    "table_stage_hash_full": "{}_HASH".format(ctx.stage_tmp_prefix_full),
    "table_stage_hash_full_local": "{}_HASH_local".format(ctx.stage_tmp_prefix_full),
    "table_stage_inc_full": "{}_INC".format(ctx.stage_tmp_prefix_full),
    "table_stage_inc_full_local": "{}_INC_local".format(ctx.stage_tmp_prefix_full),
    "table_stage_time_full": "{}_TIME".format(ctx.stage_tmp_prefix_full),
    "table_stage_time_full_local": "{}_TIME_local".format(ctx.stage_tmp_prefix_full),
}) %}

{% do ctx.update({
    "table_stage_buf": ctx.table_stage_buf_full.split(".")[1],
    "table_stage": ctx.table_stage_full.split(".")[1],
    "table_stage_hash": ctx.table_stage_hash_full.split(".")[1],
    "table_stage_inc": ctx.table_stage_inc_full.split(".")[1],
    "table_stage_time": ctx.table_stage_time_full.split(".")[1]
}) %}

{% do ctx.update({
    "table_stage_zk": render(t_vars.zk_path, db=ctx.db, db_local=ctx.db_local, table=ctx.table_stage, shard=ctx.replicated_cluster_shard),
    "table_stage_hash_zk": render(t_vars.zk_path, db=ctx.db, db_local=ctx.db_local, table=ctx.table_stage_hash, shard=ctx.replicated_cluster_shard),
    "table_stage_inc_zk": render(t_vars.zk_path, db=ctx.db, db_local=ctx.db_local, table=ctx.table_stage_inc, shard=ctx.replicated_cluster_shard),
    "table_stage_time_zk": render(t_vars.zk_path, db=ctx.db, db_local=ctx.db_local, table=ctx.table_stage_time, shard=ctx.dict_cluster_shard)
}) %}

{{ return(ctx) }}
{%- endmacro %}


{% macro prepare(ctx=none) %}
{% if ctx is none %}
    {% do init(params=kwargs) %}
    {% set ctx = get_return() %}
{% endif %}

-- @echo STEP prepare 1/12: Creating stage time table
CREATE TABLE IF NOT EXISTS {{ ctx.table_stage_time_full_local }} ON CLUSTER {{ ctx.dict_cluster }} (
    merge_at DateTime
)
ENGINE = ReplicatedMergeTree('{{ ctx.table_stage_time_zk }}', '{{ ctx.dict_cluster_replica }}')
ORDER BY merge_at
SETTINGS distributed_ddl_output_mode = 'none';

-- @echo STEP prepare 2/12: Calculating merge_at timestamp and propagating to all cluster nodes
INSERT INTO {{ ctx.table_stage_time_full_local }} SELECT toDateTime(today() - INTERVAL {{ ctx.merge_interval }});

-- @echo STEP prepare 3/12: Waiting for replication sync on stage time table
{{ sync_replica(ctx.table_stage_time_full_local, ctx.dict_cluster) }}

-- @echo STEP prepare 4/12: Creating stage table
CREATE TABLE IF NOT EXISTS {{ ctx.table_stage_full_local }} ON CLUSTER {{ ctx.replicated_cluster }} AS {{ ctx.table_target_full_local }}
ENGINE = ReplicatedReplacingMergeTree('{{ ctx.table_stage_zk }}', '{{ ctx.replicated_cluster_replica }}', {{ ctx.loaded_at }}, {{ ctx.is_deleted }})
SETTINGS distributed_ddl_output_mode = 'none';

-- @echo STEP prepare 5/12: Waiting for replication sync on stage table
{{ sync_replica(ctx.table_stage_full_local, ctx.replicated_cluster) }}

-- @echo STEP prepare 6/12: Creating distributed stage table
{{ create_distributed_table(ctx.table_stage_full, ctx.table_stage_full_local, ctx.sharding_column, ctx.replicated_cluster) }}

-- @echo STEP prepare 7/12: Creating stage hash table
CREATE TABLE IF NOT EXISTS {{ ctx.table_stage_hash_full_local }} ON CLUSTER {{ ctx.replicated_cluster }} (
    {{ ctx.id_struct }},
    start_at DateTime,
    loaded_at DateTime,
    is_deleted Bool,
    is_closed Bool,
    attr_hash UInt64, -- xxh3 hash of attributes
    source UInt8 -- 1 - cold, 2 - hot, 3 - buf
)
ENGINE = ReplicatedMergeTree('{{ ctx.table_stage_hash_zk }}', '{{ ctx.replicated_cluster_replica }}')
ORDER BY ({{ ctx.id }}, start_at)
SETTINGS distributed_ddl_output_mode = 'none';

-- @echo STEP prepare 8/12: Waiting for replication sync on stage hash table
{{ sync_replica(ctx.table_stage_hash_full_local, ctx.replicated_cluster) }}

-- @echo STEP prepare 9/12: Creating distributed stage hash table
{{ create_distributed_table(ctx.table_stage_hash_full, ctx.table_stage_hash_full_local, ctx.sharding_column, ctx.replicated_cluster) }}

-- @echo STEP prepare 10/12: Creating stage inc table
CREATE TABLE IF NOT EXISTS {{ ctx.table_stage_inc_full_local }} ON CLUSTER {{ ctx.replicated_cluster }} (
    {{ ctx.id_struct }},
    start_at DateTime,
    source UInt8 -- 2 - hot, 3 - buf
)
ENGINE = ReplicatedMergeTree('{{ ctx.table_stage_inc_zk }}', '{{ ctx.replicated_cluster_replica }}')
ORDER BY ({{ ctx.id }}, start_at)
SETTINGS distributed_ddl_output_mode = 'none';

-- @echo STEP prepare 11/12: Waiting for replication sync on stage inc table
{{ sync_replica(ctx.table_stage_inc_full_local, ctx.replicated_cluster) }}

-- @echo STEP prepare 12/12: Creating distributed stage inc table
{{ create_distributed_table(ctx.table_stage_inc_full, ctx.table_stage_inc_full_local, ctx.sharding_column, ctx.replicated_cluster) }}
{%- endmacro %}



{% macro merge(ctx=none) %}
{% if ctx is none %}
    {% do init(params=kwargs) %}
    {% set ctx = get_return() %}
{% endif %}

-- @echo STEP merge 1/13: Waiting for replication sync on buffer table
{{ sync_replica(ctx.table_stage_buf_full_local, ctx.replicated_cluster) }}

-- @echo STEP merge 2/13: Waiting for replication sync on target table
{{ sync_replica(ctx.table_target_full_local, ctx.replicated_cluster) }}

-- @echo STEP merge 3/13: Inserting hashes from cold data into hash table
INSERT INTO {{ ctx.table_stage_hash_full }}
WITH
( SELECT max(merge_at) FROM {{ ctx.table_stage_time_full_local }} ) AS merge_at
SELECT {{ ctx.id }},
MAX({{ ctx.start_at }}),
argMax({{ ctx.loaded_at }}, {{ ctx.start_at }}),
argMax({{ ctx.is_deleted }}, ({{ ctx.start_at }}, {{ ctx.loaded_at }})),
argMax({{ ctx.is_closed }}, ({{ ctx.start_at }}, {{ ctx.loaded_at }})),
argMax(if({{ ctx.is_deleted }} = 1 OR {{ ctx.is_closed }} = 1, 0, xxh3(tuple(* EXCEPT({{ ctx.id }}, {{ ctx.start_at }}, {{ ctx.loaded_at }}, {{ ctx.is_deleted }}, {{ ctx.is_closed }})))), ({{ ctx.start_at }}, {{ ctx.loaded_at }})),
1
FROM {{ ctx.table_target_full }} FINAL
WHERE {{ ctx.is_deleted }} = 0
AND {{ ctx.start_at }} < merge_at
AND ({{ ctx.id }}) IN (
    SELECT buf.{{ ctx.id }} FROM {{ ctx.table_stage_buf_full }} AS buf WHERE buf.{{ ctx.start_at }} >= merge_at
)
GROUP BY {{ ctx.id }}
SETTINGS
distributed_product_mode = 'local',
distributed_group_by_no_merge = 1,
parallel_distributed_insert_select = 2,
min_insert_block_size_rows = 0,
max_insert_threads = {{ ctx.max_insert_threads }},
min_insert_block_size_bytes = {{ ctx.min_insert_block_size_bytes }},
max_memory_usage = 80000000000;

-- @echo STEP merge 4/13: Inserting hashes from hot data into hash table
INSERT INTO {{ ctx.table_stage_hash_full }}
WITH
( SELECT max(merge_at) FROM {{ ctx.table_stage_time_full_local }} ) AS merge_at
SELECT
{{ ctx.id }},
{{ ctx.start_at }},
{{ ctx.loaded_at }},
{{ ctx.is_deleted }},
{{ ctx.is_closed }},
if({{ ctx.is_deleted }} = 1 OR {{ ctx.is_closed }} = 1, 0, xxh3(tuple(* EXCEPT ({{ ctx.id }}, {{ ctx.start_at }}, {{ ctx.loaded_at }}, {{ ctx.is_deleted }}, {{ ctx.is_closed }})))) AS h,
2
FROM {{ ctx.table_target_full }} FINAL
WHERE {{ ctx.is_deleted }} = 0
AND {{ ctx.start_at }} >= merge_at
AND ({{ ctx.id }}) IN (
    SELECT buf.{{ ctx.id }} FROM {{ ctx.table_stage_buf_full }} AS buf WHERE buf.{{ ctx.start_at }} >= merge_at
)
WINDOW w AS (
    PARTITION BY {{ ctx.id }} ORDER BY {{ ctx.start_at }} ASC, {{ ctx.loaded_at }} DESC, {{ ctx.is_deleted }} DESC, {{ ctx.is_closed }} DESC ROWS BETWEEN 1 PRECEDING AND CURRENT ROW
)
QUALIFY row_number() OVER w = 1 OR ( {{ ctx.start_at }} != lagInFrame({{ ctx.start_at }}, 1) OVER w AND h != lagInFrame(h, 1) OVER w )
SETTINGS
distributed_product_mode = 'local',
distributed_group_by_no_merge = 1,
parallel_distributed_insert_select = 2,
min_insert_block_size_rows = 0,
max_insert_threads = {{ ctx.max_insert_threads }},
min_insert_block_size_bytes = {{ ctx.min_insert_block_size_bytes }},
max_memory_usage = 80000000000;

-- @echo STEP merge 5/13: Inserting hashes from buffer into hash table
INSERT INTO {{ ctx.table_stage_hash_full }}
WITH
( SELECT max(merge_at) FROM {{ ctx.table_stage_time_full_local }} ) AS merge_at
SELECT
{{ ctx.id }},
{{ ctx.start_at }},
{{ ctx.loaded_at }},
{{ ctx.is_deleted }},
{{ ctx.is_closed }},
if({{ ctx.is_deleted }} = 1 OR {{ ctx.is_closed }} = 1, 0, xxh3(tuple(* EXCEPT ({{ ctx.id }}, {{ ctx.start_at }}, {{ ctx.loaded_at }}, {{ ctx.is_deleted }}, {{ ctx.is_closed }})))) AS h,
3
FROM {{ ctx.table_stage_buf_full }}
WHERE {{ ctx.start_at }} >= merge_at
WINDOW w AS (
    PARTITION BY {{ ctx.id }} ORDER BY {{ ctx.start_at }} ASC, {{ ctx.loaded_at }} DESC, {{ ctx.is_deleted }} DESC, {{ ctx.is_closed }} DESC ROWS BETWEEN 1 PRECEDING AND CURRENT ROW
)
QUALIFY row_number() OVER w = 1 OR ( {{ ctx.start_at }} != lagInFrame({{ ctx.start_at }}, 1) OVER w AND h != lagInFrame(h, 1) OVER w )
SETTINGS
distributed_product_mode = 'local',
distributed_group_by_no_merge = 1,
parallel_distributed_insert_select = 2,
min_insert_block_size_rows = 0,
max_insert_threads = {{ ctx.max_insert_threads }},
min_insert_block_size_bytes = {{ ctx.min_insert_block_size_bytes }},
max_memory_usage = 80000000000;

-- @echo STEP merge 6/13: Waiting for replication sync on hash table
{{ sync_replica(ctx.table_stage_hash_full_local, ctx.replicated_cluster) }}

-- @echo STEP merge 7/13: Inserting updates from hash table into inc table
INSERT INTO {{ ctx.table_stage_inc_full }}
SELECT {{ ctx.id }}, start_at, source FROM {{ ctx.table_stage_hash_full }}
WINDOW w AS (
    PARTITION BY {{ ctx.id }} ORDER BY start_at ASC, loaded_at DESC, is_deleted DESC, is_closed DESC, source ASC ROWS BETWEEN 1 PRECEDING AND CURRENT ROW
)
QUALIFY source != 1 AND ( row_number() OVER w = 1 OR ( start_at != lagInFrame(start_at, 1) OVER w AND attr_hash != lagInFrame(attr_hash, 1) OVER w ) )
SETTINGS
distributed_product_mode = 'local',
distributed_group_by_no_merge = 1,
parallel_distributed_insert_select = 2,
min_insert_block_size_rows = 0,
max_insert_threads = {{ ctx.max_insert_threads }},
min_insert_block_size_bytes = {{ ctx.min_insert_block_size_bytes }},
max_memory_usage = 80000000000;

-- @echo STEP merge 8/13: Waiting for replication sync on inc table
{{ sync_replica(ctx.table_stage_inc_full_local, ctx.replicated_cluster) }}

-- @echo STEP merge 9/13: Inserting rows with deleted flag into stage table
INSERT INTO {{ ctx.table_stage_full }} ({{ ctx.id }}, {{ ctx.start_at }}, {{ ctx.loaded_at }}, {{ ctx.is_deleted }})
WITH
( SELECT max(merge_at) FROM {{ ctx.table_stage_time_full_local }} ) AS merge_at
SELECT s.{{ ctx.id }}, s.{{ ctx.start_at }}, s.{{ ctx.loaded_at }}, 1
FROM {{ ctx.table_target_full }} AS s FINAL LEFT JOIN {{ ctx.table_stage_inc_full }} as inc
ON s.{{ ctx.id }} = inc.{{ ctx.id }} AND s.{{ ctx.start_at }} = inc.start_at
WHERE (s.{{ ctx.id }}) IN (
    SELECT i.{{ ctx.id }} FROM {{ ctx.table_stage_inc_full }} AS i
)
AND inc.source != 2 AND s.{{ ctx.start_at }} >= merge_at AND s.{{ ctx.is_deleted }} = 0
SETTINGS
join_use_nulls = 0,
distributed_product_mode = 'local',
distributed_group_by_no_merge = 1,
parallel_distributed_insert_select = 2,
min_insert_block_size_rows = 0,
join_algorithm = 'full_sorting_merge',
max_rows_in_set_to_optimize_join = 0,
max_insert_threads = {{ ctx.max_insert_threads }},
min_insert_block_size_bytes = {{ ctx.min_insert_block_size_bytes }},
max_memory_usage = 80000000000;


-- @echo STEP merge 10/13: Waiting for replication sync on stage table
{{ sync_replica(ctx.table_stage_full_local, ctx.replicated_cluster) }}

-- @echo STEP merge 11/13: Upserting rows into stage table
INSERT INTO {{ ctx.table_stage_full }}
WITH
( SELECT max(merge_at) FROM {{ ctx.table_stage_time_full_local }} ) AS merge_at
SELECT * FROM {{ ctx.table_stage_buf_full }}
WHERE {{ ctx.start_at }} >= merge_at
AND ({{ ctx.id }}, {{ ctx.start_at }}) IN ( SELECT {{ ctx.id }}, start_at FROM {{ ctx.table_stage_inc_full }} WHERE source = 3 )
WINDOW w AS (
    PARTITION BY {{ ctx.id }} ORDER BY {{ ctx.start_at }} ASC, {{ ctx.loaded_at }} DESC, {{ ctx.is_deleted }} DESC, {{ ctx.is_closed }} DESC ROWS BETWEEN 1 PRECEDING AND CURRENT ROW
)
QUALIFY row_number() OVER w = 1 OR {{ ctx.start_at }} != lagInFrame({{ ctx.start_at }}, 1) OVER w
SETTINGS
distributed_product_mode = 'local',
distributed_group_by_no_merge = 1,
parallel_distributed_insert_select = 2,
min_insert_block_size_rows = 0,
max_insert_threads = {{ ctx.max_insert_threads }},
max_threads = {{ ctx.max_insert_threads }},
max_bytes_before_external_sort = 80000000000,
max_bytes_before_external_group_by = 80000000000,
min_insert_block_size_bytes = {{ ctx.min_insert_block_size_bytes }},
max_memory_usage = 100000000000;

-- @echo STEP merge 12/13: Waiting for replication sync on stage table
{{ sync_replica(ctx.table_stage_full_local, ctx.replicated_cluster) }}

-- @echo STEP merge 13/13: Coping partitions from stage table to target
{{ attach_all_partitions_from(ctx.table_stage_full_local, ctx.table_target_full_local, ctx.replicated_cluster) }}
{%- endmacro %}



{% macro clean(ctx=none) %}
{% if ctx is none %}
    {% do init(params=kwargs) %}
    {% set ctx = get_return() %}
{% endif %}

-- @echo STEP clean 1/7: Dropping stage time table
{{ drop_table(ctx.table_stage_time_full_local, ctx.dict_cluster) }}

-- @echo STEP clean 2/7: Dropping stage distributed inc table
{{ drop_table(ctx.table_stage_inc_full, ctx.replicated_cluster) }}

-- @echo STEP clean 3/7: Dropping stage inc table
{{ drop_table(ctx.table_stage_inc_full_local, ctx.replicated_cluster) }}

-- @echo STEP clean 4/7: Dropping stage distributed hash table
{{ drop_table(ctx.table_stage_hash_full, ctx.replicated_cluster) }}

-- @echo STEP clean 5/7: Dropping stage hash table
{{ drop_table(ctx.table_stage_hash_full_local, ctx.replicated_cluster) }}

-- @echo STEP clean 6/7: Dropping stage distributed table
{{ drop_table(ctx.table_stage_full, ctx.replicated_cluster) }}

-- @echo STEP clean 7/7: Dropping stage table
{{ drop_table(ctx.table_stage_full_local, ctx.replicated_cluster) }}
{%- endmacro %}

{% macro rollback(ctx=none) %}
{% if ctx is none %}
    {% do init(params=kwargs) %}
    {% set ctx = get_return() %}
{% endif %}
{{ clean(ctx=ctx) }}
{%- endmacro %}

{% macro main(ctx=none) %}
{% if ctx is none %}
    {% do init(params=kwargs) %}
    {% set ctx = get_return() %}
{% endif %}
{{ clean(ctx=ctx) }}
{{ prepare(ctx=ctx) }}
{{ merge(ctx=ctx) }}
{{ clean(ctx=ctx) }}
{%- endmacro %}
