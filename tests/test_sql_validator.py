"""sql_validator 단위 테스트.

`python -m unittest tests.test_sql_validator` 또는
`.venv/bin/python -m unittest tests/test_sql_validator.py` 로 실행.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

from sql_validator import (  # noqa: E402  (sys.path 조정 후 import)
    extract_sql_blocks,
    validate_sql,
)


class TestExtractSqlBlocks(unittest.TestCase):
    def test_extracts_sql_fence(self) -> None:
        text = """앞부분 텍스트
```sql
SELECT 1 FROM dual;
```
뒷부분"""
        blocks = extract_sql_blocks(text)
        self.assertEqual(len(blocks), 1)
        self.assertIn("SELECT 1", blocks[0])

    def test_multiple_fences(self) -> None:
        text = "```sql\nSELECT 1 FROM dual;\n```\n중간\n```oracle\nSELECT 2 FROM dual;\n```"
        blocks = extract_sql_blocks(text)
        self.assertEqual(len(blocks), 2)


class TestValidateSqlAllowed(unittest.TestCase):
    def test_simple_select(self) -> None:
        r = validate_sql("SELECT 1 FROM dual")
        self.assertTrue(r.passed, msg=r.errors)

    def test_select_with_comment(self) -> None:
        sql = (
            "-- DB 버전 확인\n"
            "SELECT banner FROM v$version WHERE rownum = 1;"
        )
        r = validate_sql(sql)
        self.assertTrue(r.passed, msg=r.errors)

    def test_explain_plan(self) -> None:
        sql = "EXPLAIN PLAN SET STATEMENT_ID = 'X' FOR SELECT 1 FROM dual"
        r = validate_sql(sql)
        self.assertTrue(r.passed, msg=r.errors)

    def test_create_index_allowed(self) -> None:
        r = validate_sql(
            "CREATE INDEX IDX_ORDERS_DATE_STATUS ON ORDERS (ORDER_DATE, STATUS) ONLINE;"
        )
        self.assertTrue(r.passed, msg=r.errors)

    def test_alter_session_allowed(self) -> None:
        r = validate_sql("ALTER SESSION SET STATISTICS_LEVEL = ALL;")
        self.assertTrue(r.passed, msg=r.errors)

    def test_exec_dbms_stats_allowed(self) -> None:
        r = validate_sql(
            "EXEC DBMS_STATS.GATHER_TABLE_STATS(USER, 'ORDERS', cascade => TRUE);"
        )
        self.assertTrue(r.passed, msg=r.errors)


class TestValidateSqlBlocked(unittest.TestCase):
    def test_drop_table_blocked(self) -> None:
        r = validate_sql("DROP TABLE orders;")
        self.assertFalse(r.passed)
        self.assertTrue(any("DROP" in e for e in r.errors))

    def test_truncate_blocked(self) -> None:
        r = validate_sql("TRUNCATE TABLE orders;")
        self.assertFalse(r.passed)
        self.assertTrue(any("TRUNCATE" in e for e in r.errors))

    def test_delete_blocked(self) -> None:
        r = validate_sql("DELETE FROM orders WHERE id = 1;")
        self.assertFalse(r.passed)
        self.assertTrue(any("DELETE" in e for e in r.errors))

    def test_update_blocked(self) -> None:
        r = validate_sql("UPDATE orders SET status='X' WHERE id = 1;")
        self.assertFalse(r.passed)
        self.assertTrue(any("UPDATE" in e for e in r.errors))

    def test_insert_blocked(self) -> None:
        r = validate_sql("INSERT INTO orders (id) VALUES (1);")
        self.assertFalse(r.passed)
        self.assertTrue(any("INSERT" in e for e in r.errors))

    def test_create_table_blocked(self) -> None:
        r = validate_sql("CREATE TABLE foo (a NUMBER);")
        self.assertFalse(r.passed)
        # CREATE TABLE 은 INDEX 가 아니므로 차단
        self.assertTrue(any("CREATE" in e for e in r.errors))


class TestValidateMultiStatement(unittest.TestCase):
    def test_two_selects_pass(self) -> None:
        sql = "SELECT 1 FROM dual; SELECT 2 FROM dual;"
        r = validate_sql(sql)
        self.assertTrue(r.passed, msg=r.errors)

    def test_mixed_safe_and_unsafe(self) -> None:
        sql = "SELECT 1 FROM dual; DROP TABLE x;"
        r = validate_sql(sql)
        self.assertFalse(r.passed)
        self.assertTrue(any("DROP" in e for e in r.errors))


if __name__ == "__main__":
    unittest.main()
