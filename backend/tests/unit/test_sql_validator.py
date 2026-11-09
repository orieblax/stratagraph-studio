"""Unit tests for AST-level SQLSecurityValidator."""

import pytest

from src.modules.security_guardrails.domain.exceptions import SQLSecurityViolationError
from src.modules.security_guardrails.infrastructure.sql_validator import SQLSecurityValidator


@pytest.fixture
def validator() -> SQLSecurityValidator:
    return SQLSecurityValidator()


def test_valid_select_query_appends_limit(validator: SQLSecurityValidator) -> None:
    sql = "SELECT id, name FROM customers"
    res = validator.validate_and_rewrite(sql, read_only=True, max_limit=100)
    assert res.is_valid is True
    assert "LIMIT 100" in res.sanitized_sql.upper()
    assert res.has_mutations is False
    assert "customers" in res.tables_accessed


def test_select_query_with_smaller_limit_preserved(validator: SQLSecurityValidator) -> None:
    sql = "SELECT id FROM orders LIMIT 25"
    res = validator.validate_and_rewrite(sql, read_only=True, max_limit=100)
    assert res.is_valid is True
    assert "LIMIT 25" in res.sanitized_sql.upper()


def test_select_query_with_large_limit_clamped(validator: SQLSecurityValidator) -> None:
    sql = "SELECT id FROM logs LIMIT 5000"
    res = validator.validate_and_rewrite(sql, read_only=True, max_limit=100)
    assert res.is_valid is True
    assert "LIMIT 100" in res.sanitized_sql.upper()


def test_reject_multi_statement_batch_injection(validator: SQLSecurityValidator) -> None:
    sql = "SELECT id FROM products; DROP TABLE products;"
    with pytest.raises(SQLSecurityViolationError, match="Multi-statement execution rejected"):
        validator.validate_and_rewrite(sql, read_only=False)


def test_reject_forbidden_ddl_drop(validator: SQLSecurityValidator) -> None:
    sql = "DROP TABLE users"
    with pytest.raises(SQLSecurityViolationError, match="Forbidden SQL operation detected"):
        validator.validate_and_rewrite(sql, read_only=False)


def test_reject_forbidden_ddl_truncate(validator: SQLSecurityValidator) -> None:
    sql = "TRUNCATE TABLE transactions"
    with pytest.raises(SQLSecurityViolationError, match="Forbidden SQL operation detected"):
        validator.validate_and_rewrite(sql, read_only=False)


def test_reject_forbidden_ddl_alter(validator: SQLSecurityValidator) -> None:
    sql = "ALTER TABLE users ADD COLUMN role VARCHAR"
    with pytest.raises(SQLSecurityViolationError, match="Forbidden SQL operation detected"):
        validator.validate_and_rewrite(sql, read_only=False)


def test_reject_mutations_in_read_only_mode(validator: SQLSecurityValidator) -> None:
    sql = "INSERT INTO audit_logs (event) VALUES ('test')"
    with pytest.raises(SQLSecurityViolationError, match="Data mutation rejected"):
        validator.validate_and_rewrite(sql, read_only=True)


def test_allow_mutations_when_read_only_false(validator: SQLSecurityValidator) -> None:
    sql = "INSERT INTO audit_logs (event) VALUES ('test')"
    res = validator.validate_and_rewrite(sql, read_only=False)
    assert res.is_valid is True
    assert res.has_mutations is True
    assert "audit_logs" in res.tables_accessed


def test_table_allowlist_enforcement(validator: SQLSecurityValidator) -> None:
    allowed = {"customers", "orders"}
    valid_sql = "SELECT * FROM customers JOIN orders ON customers.id = orders.customer_id"
    res = validator.validate_and_rewrite(valid_sql, allowed_tables=allowed)
    assert res.is_valid is True

    unauthorized_sql = "SELECT * FROM secrets"
    with pytest.raises(SQLSecurityViolationError, match="Access to unauthorized table"):
        validator.validate_and_rewrite(unauthorized_sql, allowed_tables=allowed)


def test_empty_query_raises_error(validator: SQLSecurityValidator) -> None:
    with pytest.raises(SQLSecurityViolationError, match="Empty SQL query"):
        validator.validate_and_rewrite("   ")
