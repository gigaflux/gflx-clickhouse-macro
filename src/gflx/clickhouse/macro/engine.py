"""Core module containing the rendering engine for ClickHouse Jinja2 macros."""
import json
import re
import threading
import typing
from collections.abc import Generator, Sequence
from importlib.resources import files
from typing import cast

import sqlglot
from clickhouse_connect.driver.client import Client
from clickhouse_connect.driver.exceptions import DatabaseError, OperationalError, ProgrammingError
from clickhouse_connect.driver.summary import QuerySummary
from jinja2 import Environment, FunctionLoader, TemplateRuntimeError, pass_context, runtime, select_autoescape
from jinja2.runtime import Context


class MacroReturnException(Exception):
    """dbt return."""

    def __init__(self, value: object) -> None:
        self.value = value

class TemplateExceptions:
    """User defined exception."""

    def raise_compiler_error(self, message: str) -> None:
        """Raise the compiler error."""
        raise TemplateRuntimeError(message)

class MacroRenderEngine:
    """Engine for loading YAML table configurations and rendering ClickHouse SQL macros via Jinja2.

    This class encapsulates resource loading from implicit Python namespace packages
    and injects Pydantic-validated functions directly into the Jinja2 environment context.
    """

    def __init__(self) -> None:
        """Initialize the rendering engine and configures the Jinja2 environment."""
        # Dynamically locate the package root directory in site-packages
        self._pkg = files("gflx.clickhouse.macro")

        self._thread_local = threading.local()
        # Initialize the Jinja2 environment with an isolated resource loader
        self._env = Environment(
            loader=FunctionLoader(self._load_template_source),
            trim_blocks=True,
            lstrip_blocks=True,
            extensions=["jinja2.ext.do"],  # support {% do %}
            autoescape=select_autoescape([]),
        )

        self._env.globals["return"] = self._dbt_return  # ty:ignore[invalid-assignment]
        self._env.globals["get_return"] = self._dbt_get_return  # ty:ignore[invalid-assignment]
        self._env.globals["render"] = self._dbt_render  # ty:ignore[invalid-assignment]
        self._env.globals["exceptions"] = TemplateExceptions()  # ty:ignore[invalid-assignment]

    def _dbt_return(self, value: object) -> None:
        self._thread_local.last_return_value = value
        # raise MacroReturnException(value)

    def _dbt_get_return(self) -> object:
        return getattr(self._thread_local, "last_return_value", None)
        #return self.last_return_value

    @pass_context
    def _dbt_render(self, context: Context, value: str, **kwargs: str | int | float | bool) -> str:
        return self._render_string_global(context, value, **kwargs)

    @pass_context
    def _render_string_global(self, context: Context,
                              value: str,
                              **kwargs: str | int | float | bool) -> str:
        """Jinja2 global function to dynamically render a string template using the current context.

        Args:
            context: (Context) The Jinja2 execution context (injected automatically).
            value: (str) The template string or object to be rendered.
            **kwargs: Arbitrary keyword arguments passed explicitly (e.g., db, table).

        Returns:
            str: The rendered string.

        """
        #if not isinstance(value, str):
        #    return cast(str, value)

        combined_context: dict[str, object] = {}
        #raw_context: dict[str, object] = context.get_all()
        #for val in raw_context.values():
        #    if isinstance(val, dict):
        #        combined_context.update({str(k): v for k, v in val.items()})
        #combined_context.update({k: v for k, v in raw_context.items() if isinstance(v, str | int | bool | float) })
        combined_context.update(kwargs)
        return str(context.environment.from_string(value).render(combined_context))


    def _load_template_source(self, template_name: str) -> str | None:
        """Lazy loader callback used by Jinja2 to fetch template files from package resources.

        Args:
            template_name (str): The filename of the template (e.g., 'scd2.sql').

        Returns:
            Optional[str]: The raw string content of the template file, or None if not found.

        """
        try:
            return self._pkg.joinpath(f"macros/{template_name}").read_text(
                encoding="utf-8"
            )
        except FileNotFoundError:
            return None

    def render_macro(self,
                     template_name: str,
                     macro_name: str,
                     macro_params: dict[str, str | int | float | bool] | None = None) -> str:
        """Directly invokes and renders an isolated Jinja2 macro defined inside a template file.

        Args:
            template_name (str): The name of the template file containing the macro definition.
            macro_name (str): The exact name of the target macro to extract and execute.
            macro_params (dict[str, str | int | float | bool] | None): A dictionary of parameters forwarded
                to the macro signature. Defaults to None, which resolves to an empty dictionary.

        Returns:
            str: The rendered string fragment produced by the executed Jinja2 macro.

        Raises:
            TemplateNotFound: If the requested `template_name` file cannot be found by the environment loader.
            TemplateSyntaxError: If the template file contains invalid Jinja2 syntax and cannot be compiled.
            AttributeError: If the requested `macro_name` does not exist inside the target template.
            UndefinedError: If the macro execution fails because it attempts to access a missing strict variable
                or if a passed `macro_params` object structure is incompatible with the template logic.

        """
        if "drop_table" not in self._env.globals:
            try:
                core_template = self._env.get_template("core.sql")
                for attr_name in dir(core_template.module):
                    if not attr_name.startswith("_"):
                        attr_value = getattr(core_template.module, attr_name)
                        if isinstance(attr_value, runtime.Macro):
                            self._env.globals.update({attr_name: attr_value})
            except Exception as e:
                raise AttributeError("Could not load core.sql template") from e

        template = self._env.get_template(template_name)
        macro_func: runtime.Macro | None = getattr(template.module, macro_name, None)
        if macro_func is None:
            macro_func = typing.cast(runtime.Macro | None, self._env.globals.get(macro_name))

        if macro_func is None:
            raise AttributeError(
                f"Macro '{macro_name}' was not found inside template '{template_name}'."
            )
        try:
            return str(macro_func(**(macro_params or {})))
        except MacroReturnException as e:
            if isinstance(e.value, dict):
                return json.dumps(e.value, ensure_ascii=False)
            return cast(str, e.value)

    def parse_macro(self,
                     template_name: str,
                     macro_name: str,
                     macro_params: dict[str, str | int | float | bool] | None = None) \
        -> Generator[tuple[str, dict[str, str]], None, None]:
        """Render a Jinja2 macro and parses it into individual SQL statements.

        Extracts standalone ClickHouse `SETTINGS` blocks before parsing via `sqlglot`
        to prevent syntax failures. Yields a tuple of the cleaned SQL query text
        and its isolated settings mapping.

        Args:
            template_name (str): The name of the template file containing the target macro definition.
            macro_name (str): The exact name of the target macro to extract, render, and parse.
            macro_params (dict[str, str | int | float | bool] | None): A dictionary of parameters
                forwarded to the macro signature. Defaults to None.

        Yields:
            Generator[tuple[str, dict[str, str]], None, None]: A generator yielding a tuple where the first element
                is the clean SQL statement string (without masks) and the second element
                is a dictionary of extracted ClickHouse settings.

        Raises:
            TemplateNotFound: If the `template_name` file cannot be located.
            TemplateSyntaxError: If the template file contains invalid Jinja2.
            AttributeError: If the `macro_name` does not exist in the template.
            UndefinedError: If the macro attempts to access a missing strict variable during execution.
            ParseError: If `sqlglot` fails to compile the masked script into
                abstract syntax tree statements due to SQL syntax errors.
            UnsupportedError: If the internal AST contains expressions or nodes
                that cannot be generated into valid ClickHouse SQL text.
            GenerateError: If the generator fails to transform the specific AST
                statement back into a string format.

        """
        script = self.render_macro(template_name, macro_name, macro_params)
        # Regex to capture the entire SETTINGS block until a semicolon
        settings_regex = re.compile(r"(\bSETTINGS\s+[^;]+)", re.IGNORECASE | re.DOTALL)
        # Regex to identify injected placeholders during post-processing
        mask_regex = re.compile(r"/\* CH_SETTINGS_MASK_(\d+) \*/")
        # Regex to extract key-value pairs from the isolated SETTINGS block
        kv_regex = re.compile(r"([\w_]+)\s*=\s*([^,\s]+)")

        # Temporary storage for raw SETTINGS strings indexed by an incrementing ID
        settings_storage: dict[int, str] = {}
        counter = 0

        def mask_match(m: re.Match[str]) -> str:
            """Store the raw SETTINGS block and return a unique comment mask."""
            nonlocal counter
            settings_text = m.group(1)
            settings_storage[counter] = settings_text
            mask = f"/* CH_SETTINGS_MASK_{counter} */"
            # mask = f"'CH_SETTINGS_MASK_{counter}'"
            counter += 1
            return mask

        # Replace all raw SETTINGS blocks with temporary comment masks
        masked_content = settings_regex.sub(mask_match, script)
        # Parse the masked script into abstract syntax tree statements
        statements = sqlglot.parse(masked_content, dialect="clickhouse")

        for stmt in statements:
            if not stmt:
                continue
            # FIX: sqlglot nodes generate SQL via .sql() method on the expression instance
            stmt_sql = stmt.sql(dialect="clickhouse")
            local_settings: dict[str, str] = {}
            # Find all mask placeholders present inside the current statement
            masks_found = mask_regex.findall(stmt_sql)

            for mask_idx_str in masks_found:
                mask_idx = int(mask_idx_str)
                raw_settings_block = settings_storage[mask_idx]

                # Parse and clean key-value pairs from the stored raw block
                for k, v in kv_regex.findall(raw_settings_block):
                    # local_settings[k.strip()] = v.strip().strip("'\"`")
                    local_settings[k.strip()] = v.strip()

            # Strip masks and trailing commas left after mask removal
            clean_stmt_sql = mask_regex.sub("", stmt_sql).strip()
            clean_stmt_sql = re.sub(r"\s*,\s*$", "", clean_stmt_sql)
            yield clean_stmt_sql, local_settings

    def explain_macro(self,
                       template_name: str,
                       macro_name: str,
                       client: Client,
                       macro_params: dict[str, str | int | float | bool] | None = None) \
        -> Generator[tuple[str, str], None, None]:
        """Explain a macro.

        Args:
            template_name (str): The name of the template file containing the target macro definition.
            macro_name (str): The exact name of the target macro to explain.
            client: (clickhouse_connect.driver.client.Client): ClickHouse client
            macro_params (dict[str, str | int | float | bool] | None): A dictionary of parameters
                forwarded to the macro signature. Defaults to None.

        Yields:
            Generator[tuple[str, str], None, None]: A generator yielding source statement, result of EXPLAIN AST.

        Raises:
            TemplateNotFound: If the `template_name` file cannot be located.
            TemplateSyntaxError: If the template file contains invalid Jinja2.
            AttributeError: If the `macro_name` does not exist in the template.
            UndefinedError: If the macro attempts to access a missing strict variable during execution.
            ParseError: If `sqlglot` fails to compile the masked script into
                abstract syntax tree statements due to SQL syntax errors.
            UnsupportedError: If the internal AST contains expressions or nodes
                that cannot be generated into valid ClickHouse SQL text.
            GenerateError: If the generator fails to transform the specific AST
                statement back into a string format.
            ProgrammingError: If the SQL statement contains syntax errors, invalid settings, or formatting issues
                that prevent AST compilation.
            DatabaseError: If the statement references databases, tables, or columns that do not exist on the
                ClickHouse server.
            OperationalError: If the user lacks necessary access permissions or if a network timeout occurs
                during the request execution.
            InterfaceError: If a low-level HTTP communication failure occurs
                while receiving the response from the database server.

        """
        for stmt, settings in list(self.parse_macro(template_name, macro_name, macro_params)):
            settings_str = ",\n".join([f"{k} = {v}" for k, v in settings.items()])
            stmt_final = f"{stmt} SETTINGS {settings_str}" if settings_str else stmt
            ast_result = client.command(f"EXPLAIN AST {stmt_final}")
            if isinstance(ast_result, Sequence):
                yield stmt_final, "\n".join(str(item) for item in ast_result)
            elif isinstance(ast_result, str | int):
                yield stmt_final, str(ast_result)
            elif isinstance(ast_result, QuerySummary):
                yield stmt_final, json.dumps(ast_result.summary, indent=4)

    def execute_macro(self,
                      template_name: str,
                      macro_name: str,
                      client: Client,
                      macro_params: dict[str, str | int | float | bool] | None = None,
                      rollback_macro_name: str | None = None,
                      rollback_macro_params: dict[str, str | int | float | bool] | None = None) \
        -> Generator[tuple[str, str, int], None, None]:
        """Execute a macro.

        Args:
            template_name (str): The name of the template file containing the target macro definition.
            macro_name (str): The exact name of the target macro to execute.
            client: (clickhouse_connect.driver.client.Client): ClickHouse client
            macro_params (dict[str, str | int | float | bool] | None): A dictionary of parameters
                forwarded to the macro signature. Defaults to None.
            rollback_macro_name (str): The exact name of the rollback target macro.
            rollback_macro_params (dict[str, str | int | float | bool] | None): A dictionary of parameters
                forwarded to the rollback macro signature. Defaults to None.

        Yields:
            Generator[tuple[str, str, int], None, None]: A generator yielding source statement, result, start|end flag.

        Raises:
            TemplateNotFound: If the `template_name` file cannot be located.
            TemplateSyntaxError: If the template file contains invalid Jinja2.
            AttributeError: If the `macro_name` does not exist in the template.
            UndefinedError: If the macro attempts to access a missing strict variable during execution.
            ParseError: If `sqlglot` fails to compile the masked script into
                abstract syntax tree statements due to SQL syntax errors.
            UnsupportedError: If the internal AST contains expressions or nodes
                that cannot be generated into valid ClickHouse SQL text.
            GenerateError: If the generator fails to transform the specific AST
                statement back into a string format.
            ProgrammingError: If the SQL statement contains syntax errors, invalid settings, or formatting issues
                that prevent AST compilation.
            DatabaseError: If the statement references databases, tables, or columns that do not exist on the
                ClickHouse server.
            OperationalError: If the user lacks necessary access permissions or if a network timeout occurs
                during the request execution.
            InterfaceError: If a low-level HTTP communication failure occurs
                while receiving the response from the database server.

        """
        stmts = list(self.explain_macro(template_name, macro_name, client, macro_params))
        rollback_stmts = None
        if rollback_macro_name:
            rollback_stmts = list(self.explain_macro(template_name, rollback_macro_name, client, rollback_macro_params))

        for stmt, _ in stmts:
            #pattern = r"--[\s]+@echo[\s]+.*"
            #echo_comments = "\n".join(re.findall(pattern, stmt))
            #if echo_comments:
            #    yield echo_comments, ""
            yield stmt, "", 0
            try:
                result = client.command(stmt)
            except (ProgrammingError, DatabaseError, OperationalError) as e:
                if rollback_stmts and rollback_macro_name:
                    self.execute_macro(template_name, rollback_macro_name, client, rollback_macro_params)
                raise e
            if isinstance(result, Sequence):
                yield stmt, "\n".join(str(item) for item in result), 1
            elif isinstance(result, str | int):
                yield stmt, str(result), 1
            elif isinstance(result, QuerySummary):
                yield stmt, json.dumps(result.summary, indent=4), 1



