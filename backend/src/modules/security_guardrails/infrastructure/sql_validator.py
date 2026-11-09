"""AST-level SQL security validator and query rewriter using sqlglot."""

from __future__ import annotations

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

from src.modules.security_guardrails.domain.exceptions import SQLSecurityViolationError
from src.modules.security_guardrails.domain.interfaces import ISQLValidator, SQLValidationResult


class SQLSecurityValidator(ISQLValidator):
    """Enforces strict defense-in-depth SQL AST rules before execution."""

    # Explicitly forbidden AST nodes regardless of read/write status
    FORBIDDEN_AST_NODES: tuple[type[exp.Expression], ...] = (
        exp.Drop,
        exp.TruncateTable,
        exp.Alter,
        exp.Grant,
        exp.Revoke,
        exp.Copy,
        exp.Command,
        exp.Create,
        exp.Pragma,
    )

    # Mutation nodes forbidden under read-only mode
    MUTATION_AST_NODES: tuple[type[exp.Expression], ...] = (
        exp.Insert,
        exp.Update,
        exp.Delete,
        exp.Merge,
    )

    def validate_and_rewrite(
        self,
        sql: str,
        *,
        dialect: str = "postgres",
        read_only: bool = True,
        allowed_tables: set[str] | None = None,
        max_limit: int = 100,
    ) -> SQLValidationResult:
        """Parse, validate, and sanitize a SQL query against AST security rules."""
        raw_sql = sql.strip()
        if not raw_sql:
            raise SQLSecurityViolationError("Empty SQL query provided.")

        # Check for multiple statements separated by semicolons (prevent batch injection)
        try:
            parsed_expressions = sqlglot.parse(raw_sql, read=dialect)
        except ParseError as exc:
            raise SQLSecurityViolationError(
                f"SQL syntax error during AST parsing: {exc}",
                details={"raw_sql": raw_sql},
            ) from exc

        if not parsed_expressions:
            raise SQLSecurityViolationError("No valid SQL statements found.")

        # Filter out empty comments or whitespace nodes
        valid_expressions = [expr for expr in parsed_expressions if expr is not None]

        if len(valid_expressions) > 1:
            raise SQLSecurityViolationError(
                "Multi-statement execution rejected. Only single SQL queries are permitted.",
                details={"statement_count": str(len(valid_expressions))},
            )

        root_expr = valid_expressions[0]

        # 1. Reject forbidden DDL / DCL / Administrative AST types
        for forbidden in self.FORBIDDEN_AST_NODES:
            if isinstance(root_expr, forbidden) or root_expr.find(forbidden):
                raise SQLSecurityViolationError(
                    f"Forbidden SQL operation detected: {forbidden.__name__}",
                    details={"forbidden_type": forbidden.__name__},
                )

        # 2. Check for mutations
        has_mutations = False
        for mutation in self.MUTATION_AST_NODES:
            if isinstance(root_expr, mutation) or root_expr.find(mutation):
                has_mutations = True
                break

        if read_only and has_mutations:
            raise SQLSecurityViolationError(
                "Data mutation rejected. Only read-only queries (SELECT) are permitted in this mode.",
                details={"query_type": type(root_expr).__name__},
            )

        # 3. Extract and validate accessed tables
        tables_accessed: list[str] = []
        for table_expr in root_expr.find_all(exp.Table):
            table_name = table_expr.name
            if table_name:
                normalized = table_name.lower().strip('"')
                tables_accessed.append(normalized)

        # Deduplicate while preserving order
        unique_tables = list(dict.fromkeys(tables_accessed))

        if allowed_tables is not None:
            normalized_allowed = {t.lower().strip('"') for t in allowed_tables}
            unauthorized = [t for t in unique_tables if t not in normalized_allowed]
            if unauthorized:
                raise SQLSecurityViolationError(
                    f"Access to unauthorized table(s): {', '.join(unauthorized)}",
                    details={"unauthorized_tables": ", ".join(unauthorized)},
                )

        # 4. Enforce max LIMIT on SELECT queries
        sanitized_expr = root_expr.copy()
        if isinstance(sanitized_expr, exp.Select):
            limit_clause = sanitized_expr.args.get("limit")
            if limit_clause is None:
                sanitized_expr = sanitized_expr.limit(max_limit, copy=False)
            else:
                try:
                    limit_val_expr = limit_clause.expression
                    if isinstance(limit_val_expr, exp.Literal):
                        current_limit = int(limit_val_expr.this)
                        if current_limit > max_limit:
                            sanitized_expr = sanitized_expr.limit(max_limit, copy=False)
                    else:
                        sanitized_expr = sanitized_expr.limit(max_limit, copy=False)
                except (ValueError, TypeError, AttributeError):
                    sanitized_expr = sanitized_expr.limit(max_limit, copy=False)

        sanitized_sql = sanitized_expr.sql(dialect=dialect)

        return SQLValidationResult(
            is_valid=True,
            sanitized_sql=sanitized_sql,
            ast_type=type(root_expr).__name__,
            tables_accessed=unique_tables,
            has_mutations=has_mutations,
        )
