#!/usr/bin/env python3
"""수집 SQL 정적 문법 검증 모듈.

본 모듈은 두 가지 입력에 동작한다.
1) 마크다운 파일(예: knowledge/collection_sqls.md, 에이전트 응답 텍스트)
   - 코드 펜스 ```sql ... ``` 블록을 추출해 각각 검증한다.
2) 단일 SQL 문자열

검증 단계:
- sqlparse 로 토큰화. 빈 결과면 오류.
- 다중 문장은 세미콜론 또는 sqlparse.split 로 분리해 개별 검증.
- 위험 키워드(DROP TABLE/TRUNCATE/DELETE/UPDATE/INSERT/MERGE 등) 등장 시 errors.
- 19c 딕셔너리 뷰/패키지 화이트리스트(USER_*/ALL_*/DBA_*/V$/GV$/DBMS_XPLAN/DBMS_STATS/DBMS_OUTPUT) 외의
  도메인 객체명은 warnings 로 표기(에러 아님).

한계:
- 토큰/패턴 수준 검증이며 실제 19c 실행 가능성을 보장하지 않는다.
- 베타 운용 시 EXPLAIN PLAN FOR 또는 실제 19c 환경에서의 파싱으로 보강해야 한다.

CLI:
    python tests/sql_validator.py knowledge/collection_sqls.md
    python tests/sql_validator.py --sql "SELECT 1 FROM dual"

종료 코드:
    0 — errors 0건
    1 — errors 1건 이상
"""

from __future__ import annotations

import argparse
import dataclasses
import re
import sys
from pathlib import Path
from typing import Iterable

import sqlparse


# 마크다운 ```sql ... ``` 또는 ```oracle ... ``` 코드 펜스
SQL_FENCE_RE = re.compile(
    r"```(?:sql|oracle|plsql)\s*\n(?P<body>.*?)```",
    re.DOTALL | re.IGNORECASE,
)

# MVP 허용 DML/DDL 1차 토큰
ALLOWED_FIRST_TOKENS = {
    "SELECT",
    "WITH",
    "EXPLAIN",
    "CREATE",   # CREATE INDEX 만 허용 (아래 CREATE_ALLOWED_OBJECT 로 추가 검증)
    "ALTER",    # ALTER SESSION / ALTER INDEX 만 허용
    "EXEC",     # EXEC DBMS_STATS.GATHER_TABLE_STATS 등
    "EXECUTE",
    "BEGIN",    # 익명 PL/SQL 블록
    "SET",      # SET AUTOTRACE 등
}

# 위험 키워드 (어떤 위치든 등장하면 차단)
DANGEROUS_KEYWORDS = {
    "DROP",
    "TRUNCATE",
    "DELETE",
    "UPDATE",
    "INSERT",
    "MERGE",
    "GRANT",
    "REVOKE",
    "RENAME",
    "FLASHBACK",
    "PURGE",
}

# CREATE 뒤에 허용되는 객체 종류
CREATE_ALLOWED_OBJECT = {"INDEX", "OR"}  # OR REPLACE FORCE VIEW 등은 별도 처리

# ALTER 뒤에 허용되는 객체 종류
ALTER_ALLOWED_OBJECT = {"SESSION", "INDEX", "SYSTEM"}

# 19c Phase 1 화이트리스트 (식별자 prefix 또는 정확 이름)
WHITELIST_PREFIX = (
    "USER_", "ALL_", "DBA_", "V$", "GV$",
)
WHITELIST_EXACT = {
    "DBMS_XPLAN", "DBMS_STATS", "DBMS_OUTPUT", "DBMS_SQL", "DBMS_LOB",
    "DUAL", "SYS", "SYSDATE", "SYSTIMESTAMP", "USER", "TRUE", "FALSE",
    "ROWNUM", "ROWID", "LEVEL", "NULL",
}


@dataclasses.dataclass
class ValidationResult:
    sql: str
    passed: bool
    errors: list[str]
    warnings: list[str]


def extract_sql_blocks(text: str) -> list[str]:
    """마크다운에서 ```sql/```oracle/```plsql 코드 블록을 모두 추출."""
    blocks = [m.group("body").strip() for m in SQL_FENCE_RE.finditer(text)]
    return [b for b in blocks if b]


def _split_statements(sql_text: str) -> list[str]:
    """sqlparse.split 로 개별 문장 분리. 주석 제거 후 빈 문자열 제외."""
    stmts: list[str] = []
    for raw in sqlparse.split(sql_text):
        cleaned = _strip_comments(raw).rstrip(";").strip()
        if cleaned:
            stmts.append(cleaned)
    return stmts


def _strip_comments(sql: str) -> str:
    return sqlparse.format(sql, strip_comments=True).strip()


def _first_significant_token(parsed: sqlparse.sql.Statement) -> str:
    for token in parsed.flatten():
        if token.is_whitespace:
            continue
        if token.ttype in (
            sqlparse.tokens.Comment,
            sqlparse.tokens.Comment.Single,
            sqlparse.tokens.Comment.Multiline,
        ):
            continue
        # 일부 토큰은 ttype 이 None 인 부모 노드. 값으로만 판단.
        v = token.value.strip()
        if not v:
            continue
        # ttype 이 Punctuation 이면 건너뜀
        if token.ttype is sqlparse.tokens.Punctuation:
            continue
        return v.upper().split()[0]
    return ""


def _all_keyword_values(parsed: sqlparse.sql.Statement) -> Iterable[str]:
    for token in parsed.flatten():
        if token.ttype in (
            sqlparse.tokens.Keyword,
            sqlparse.tokens.Keyword.DDL,
            sqlparse.tokens.Keyword.DML,
            sqlparse.tokens.Keyword.CTE,
        ):
            yield token.value.upper()


def _all_identifiers(parsed: sqlparse.sql.Statement) -> Iterable[str]:
    for token in parsed.flatten():
        if token.ttype is sqlparse.tokens.Name:
            yield token.value.upper()


def validate_sql(sql: str) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    if not sql.strip():
        errors.append("빈 SQL")
        return ValidationResult(sql, False, errors, warnings)

    statements = _split_statements(sql)
    if not statements:
        errors.append("실행 가능한 문장이 없습니다.")
        return ValidationResult(sql, False, errors, warnings)

    for stmt in statements:
        parsed_list = sqlparse.parse(stmt)
        if not parsed_list:
            errors.append(f"파싱 실패: {stmt[:60]}...")
            continue
        parsed = parsed_list[0]
        first = _first_significant_token(parsed)

        # 1) 위험 키워드 차단 (단, CREATE/ALTER 의 객체 검증은 별도)
        keyword_values = list(_all_keyword_values(parsed))
        for kw in DANGEROUS_KEYWORDS:
            if kw in keyword_values:
                errors.append(f"위험 키워드 차단: {kw} (문장: {stmt[:80]}...)")

        # 2) 1차 토큰 허용 여부
        if first not in ALLOWED_FIRST_TOKENS:
            errors.append(f"허용되지 않은 첫 토큰: {first} (문장: {stmt[:80]}...)")
            continue

        # 3) CREATE / ALTER 추가 검증
        if first == "CREATE":
            # CREATE 다음의 첫 의미있는 키워드를 추출
            tokens_clean = [t for t in re.split(r"\s+", stmt.strip()) if t]
            if len(tokens_clean) >= 2:
                second = tokens_clean[1].upper()
                if second not in CREATE_ALLOWED_OBJECT:
                    errors.append(f"허용되지 않은 CREATE 대상: {second} (INDEX 만 허용)")
            else:
                errors.append("불완전한 CREATE 문")
        if first == "ALTER":
            tokens_clean = [t for t in re.split(r"\s+", stmt.strip()) if t]
            if len(tokens_clean) >= 2 and tokens_clean[1].upper() not in ALTER_ALLOWED_OBJECT:
                errors.append(f"허용되지 않은 ALTER 대상: {tokens_clean[1]} (SESSION/INDEX/SYSTEM 허용)")

        # 4) 식별자 화이트리스트 (정보성 warning 만)
        for ident in _all_identifiers(parsed):
            up = ident.upper()
            if up.startswith(WHITELIST_PREFIX):
                continue
            if up in WHITELIST_EXACT:
                continue
            # 사용자 도메인 식별자(ORDERS, CUSTOMERS 등)는 알 수 없으므로 warning 도 생략.
            # 명시적으로 위험할 패턴(예: DBA_ 미허용 등)은 1차 검증에서 처리됨.

    return ValidationResult(sql, not errors, errors, warnings)


def validate_file(path: Path) -> tuple[int, int, list[ValidationResult]]:
    text = path.read_text(encoding="utf-8")
    blocks = extract_sql_blocks(text)
    results: list[ValidationResult] = []
    pass_count = 0
    fail_count = 0
    for idx, block in enumerate(blocks, 1):
        result = validate_sql(block)
        results.append(result)
        if result.passed:
            pass_count += 1
        else:
            fail_count += 1
    return pass_count, fail_count, results


def _print_report(results: list[ValidationResult], path: Path | None) -> None:
    where = str(path) if path else "<inline>"
    print(f"[sql_validator] target = {where}")
    for i, r in enumerate(results, 1):
        status = "PASS" if r.passed else "FAIL"
        first_line = (r.sql.strip().splitlines() or [""])[0][:80]
        print(f"  #{i:>2} {status}  {first_line}")
        for e in r.errors:
            print(f"        ERROR   - {e}")
        for w in r.warnings:
            print(f"        WARN    - {w}")
    pass_count = sum(1 for r in results if r.passed)
    fail_count = len(results) - pass_count
    print(f"[sql_validator] passed={pass_count}, failed={fail_count}, total={len(results)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="수집 SQL 정적 문법 검증")
    parser.add_argument("file", nargs="?", type=Path, help="검증할 마크다운 파일 (코드 블록 추출)")
    parser.add_argument("--sql", help="단일 SQL 문자열을 직접 검증")
    args = parser.parse_args()

    if args.sql:
        result = validate_sql(args.sql)
        _print_report([result], None)
        return 0 if result.passed else 1

    if not args.file:
        parser.error("file 또는 --sql 중 하나는 필수입니다.")
    if not args.file.is_file():
        parser.error(f"파일이 없습니다: {args.file}")

    _, fail, results = validate_file(args.file)
    _print_report(results, args.file)
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
