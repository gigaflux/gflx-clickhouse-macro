
{% macro create_distributed_table(
    table,
    table_local,
    sharding_column,
    cluster
) %}
{#
    Generate a script to create a distributed table

    Parameters:
        table (str): distributed table
        table_local (str): local table
        sharding_column (str): sharding column
        cluster (str): cluster name

    Returns:
        str: create table script
#}
{% if '.' in table_local %}
    {% set local_db = table_local.split('.')[0] %}
    {% set local_tbl = table_local.split('.')[1] %}
{% else %}
    {% set local_db = table.split('.')[0] if '.' in table else "default" %}
    {% set local_tbl = table_local %}
{% endif %}
CREATE TABLE IF NOT EXISTS {{ table }} ON CLUSTER {{ cluster }} AS {{ table_local }}
ENGINE = Distributed('{{ cluster }}', '{{ local_db }}', '{{ local_tbl }}', xxh3({{ sharding_column | trim }}))
SETTINGS distributed_ddl_output_mode = 'none';
{%- endmacro %}

{% macro sync_replica(
    table,
    cluster,
    mode="LIGHTWEIGHT"
) %}
{#
    Generate a script to wait sync replicas

    Parameters:
        table (str): replicated table
        cluster (str): cluster name

    Returns:
        str: sync replicas script
#}
SYSTEM SYNC REPLICA ON CLUSTER {{ cluster }} {{ table }} {{ mode }};
{%- endmacro %}

{% macro drop_table(
    table,
    cluster
) %}
{#
    Generate a script to drop table

    Parameters:
        table (str): table
        cluster (str): cluster name

    Returns:
        str: drop table script
#}
DROP TABLE IF EXISTS {{ table }} ON CLUSTER {{ cluster }} SYNC
SETTINGS distributed_ddl_output_mode = 'none';
{%- endmacro %}


{% macro attach_all_partitions_from(
    table_src,
    table_dst,
    cluster
) %}
{#
    Generate a script to attach all partitions

    Parameters:
        table_src (str): source table
        table_dst (str): destination table
        cluster (str): cluster name

    Returns:
        str: script to attach all partitions
#}
ALTER TABLE {{ table_dst }} ON CLUSTER {{ cluster }} ATTACH PARTITION ALL FROM {{ table_src }}
SETTINGS distributed_ddl_output_mode = 'none';
{%- endmacro %}
