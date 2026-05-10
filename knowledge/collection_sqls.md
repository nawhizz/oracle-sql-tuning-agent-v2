# 수집 SQL 템플릿 (Oracle 19c 기준)

본 문서는 Claude.ai Project Knowledge에 업로드되는 참고 자료다. 에이전트는 사용자에게 수집 SQL을 제시할 때 본 문서의 형식과 명칭을 그대로 따른다.

- **기준 버전**: Oracle 19c. 일부 SQL은 11g R2 이상에서 동작.
- **표기 규약**:
  - 바인드 변수는 `:PARAM_NAME` 형식.
  - 다중 테이블 필터는 `:TABLE_LIST` 자리에 사용자 SQL의 실제 테이블명을 치환.
  - 모든 SQL은 SQL\*Plus / SQL Developer / Toad에서 그대로 실행 가능. 세미콜론으로 종결.

---

## A. 실행 계획 수집

### A.0 4가지 방법 비교

| 방법 | SQL 실행 | 정보 수준 | 적합 상황 |
|------|----------|-----------|-----------|
| `EXPLAIN PLAN` | 실행 안 함 | 추정치만 (E-Rows, Cost) | 빠른 1차 확인, 실행 불가 SQL |
| `GATHER_PLAN_STATISTICS` + `DISPLAY_CURSOR` | 실제 실행 | 추정 + 실측 | **튜닝 진단의 정석** |
| `DISPLAY_CURSOR`(힌트 없이) | 이미 실행됨 | 기본 통계 | `SQL_ID`로 캐시 조회 |
| `DISPLAY_AWR` | 과거 이력 | AWR 스냅샷 | 과거 시점 / 변화 추적. EE+Diagnostics Pack |

### A.1 EXPLAIN PLAN (실행 없음)

```sql
-- 옵티마이저의 "예상" 계획만 확인. STATEMENT_ID로 before/after 구분.
EXPLAIN PLAN SET STATEMENT_ID = 'MY_PLAN' FOR
  SELECT /* <대상 SQL 전문> */ 1 FROM dual;

SELECT * FROM TABLE(DBMS_XPLAN.DISPLAY(statement_id => 'MY_PLAN', format => 'ALL'));
```

주의: Rows/Bytes/Cost는 추정치이며 바인드 실값과 Adaptive Plan은 반영되지 않는다.

### A.2 GATHER_PLAN_STATISTICS + DISPLAY_CURSOR (권장)

```sql
-- /*+ GATHER_PLAN_STATISTICS */ 힌트로 단계별 실측치(A-Rows, A-Time, Buffers, Reads) 수집.
SELECT /*+ GATHER_PLAN_STATISTICS */ 1
FROM   dual;

-- 위 SQL 실행 직후 곧바로 호출
SELECT * FROM TABLE(DBMS_XPLAN.DISPLAY_CURSOR(NULL, NULL, 'ALLSTATS LAST'));
```

출력 컬럼 해석:
- `Starts` — 단계 실행 횟수
- `E-Rows` — 옵티마이저 추정 행 수
- `A-Rows` — 실제 처리된 행 수
- `A-Time` — 단계별 실제 소요 시간
- `Buffers` — 논리적 읽기(메모리)
- `Reads` — 물리적 읽기(디스크)

`E-Rows`와 `A-Rows`의 괴리가 10배 이상이면 통계 노후화 또는 히스토그램 부재 의심.

### A.3 DISPLAY_CURSOR — 이미 실행된 SQL

```sql
-- SQL_ID를 알면 커서 캐시에서 직접 조회.
SELECT * FROM TABLE(DBMS_XPLAN.DISPLAY_CURSOR(:SQL_ID, NULL, 'ALLSTATS LAST'));
```

### A.4 DISPLAY_AWR — 과거 이력

```sql
-- AWR에 저장된 과거 계획 조회. EE + Diagnostics Pack 라이선스 필요.
SELECT * FROM TABLE(DBMS_XPLAN.DISPLAY_AWR(:SQL_ID));
```

---

## B. 테이블 통계

### B.1 기본 통계 + 통계 노후도

```sql
-- 행 수, 블록 수, 평균 행 길이, 마지막 통계 수집 시점, 경과 일수.
SELECT table_name,
       num_rows,
       blocks,
       avg_row_len,
       last_analyzed,
       ROUND(SYSDATE - last_analyzed) AS days_since_stats
FROM   user_tab_statistics
WHERE  table_name IN (:TABLE_LIST)
ORDER BY days_since_stats DESC;
```

### B.2 파티션 정보

```sql
-- 파티션 테이블이면 파티션별 행 수와 최근 통계 시점 확인.
SELECT table_name,
       partition_name,
       num_rows,
       blocks,
       last_analyzed
FROM   user_tab_partitions
WHERE  table_name IN (:TABLE_LIST)
ORDER BY table_name, partition_position;
```

---

## C. 컬럼 통계

### C.1 기본 컬럼 통계

```sql
-- WHERE/조인/정렬 컬럼의 NDV·NULL 비율·히스토그램 존재 여부.
SELECT column_name,
       num_distinct,
       num_nulls,
       density,
       histogram,
       low_value,
       high_value
FROM   user_tab_col_statistics
WHERE  table_name = :TABLE_NAME
  AND  column_name IN (:COLUMN_LIST);
```

### C.2 히스토그램 상세

```sql
-- 히스토그램 endpoint 분포. FREQUENCY/HEIGHT BALANCED/HYBRID/TOP-FREQUENCY 타입 모두 동일 뷰.
SELECT endpoint_number,
       endpoint_value,
       endpoint_actual_value
FROM   user_histograms
WHERE  table_name  = :TABLE_NAME
  AND  column_name = :COLUMN_NAME
ORDER BY endpoint_number;
```

히스토그램 타입 해석:
- `NONE` — 히스토그램 없음. 균등 분포 가정
- `FREQUENCY` — NDV ≤ 254. 모든 값에 endpoint
- `HEIGHT BALANCED` (12c 미만) / `HYBRID` (12c+) — NDV > 254
- `TOP-FREQUENCY` (12c+) — 상위 값이 데이터의 대부분일 때

---

## D. 인덱스

### D.1 인덱스 목록 및 구성

```sql
-- 인덱스 이름·구성 컬럼·UNIQUE 여부.
SELECT i.table_name,
       i.index_name,
       i.uniqueness,
       i.index_type,
       ic.column_name,
       ic.column_position
FROM   user_indexes i
  JOIN user_ind_columns ic
    ON i.index_name = ic.index_name
WHERE  i.table_name IN (:TABLE_LIST)
ORDER BY i.table_name, i.index_name, ic.column_position;
```

### D.2 인덱스 통계 + 클러스터링 팩터

```sql
-- BLEVEL, LEAF_BLOCKS, CLUSTERING_FACTOR. CF가 BLOCKS에 가까우면 좋음, NUM_ROWS에 가까우면 나쁨.
SELECT i.index_name,
       i.blevel,
       i.leaf_blocks,
       i.num_rows,
       i.clustering_factor,
       t.blocks AS table_blocks
FROM   user_indexes i
  JOIN user_tables  t ON i.table_name = t.table_name
WHERE  i.table_name = :TABLE_NAME;
```

---

## E. 제약조건

```sql
-- PK/FK/UK/CHECK 및 외래키 컬럼 매핑.
SELECT c.constraint_name,
       c.constraint_type,
       c.table_name,
       cc.column_name,
       c.r_constraint_name AS referenced_constraint
FROM   user_constraints c
  LEFT JOIN user_cons_columns cc
    ON c.constraint_name = cc.constraint_name
WHERE  c.table_name IN (:TABLE_LIST)
ORDER BY c.table_name, c.constraint_type, cc.position;
```

---

## F. 바인드 변수

### F.1 캡처된 바인드 값

```sql
-- 옵티마이저가 마지막으로 본 바인드 값. SQL_ID 필요.
SELECT sql_id,
       name,
       position,
       datatype_string,
       value_string,
       last_captured
FROM   v$sql_bind_capture
WHERE  sql_id = :SQL_ID
ORDER BY position;
```

### F.2 카디널리티 직접 측정

```sql
-- 사용자가 대표 값을 알려주면 그 조건의 실제 행 수를 측정.
SELECT COUNT(*) AS matching_rows
FROM   :TABLE_NAME
WHERE  :PREDICATE_PLACEHOLDER;
```

예시 치환:
```sql
SELECT COUNT(*) FROM orders
WHERE order_date >= TO_DATE('2026-01-01','YYYY-MM-DD')
  AND status = 'SHIPPED';
```

---

## G. 실행 통계

### G.1 V$SQLSTATS — 누적 통계

```sql
-- 수행 시간·논리/물리 읽기·반환 행 수.
SELECT sql_id,
       executions,
       elapsed_time / 1e6   AS elapsed_sec,
       cpu_time     / 1e6   AS cpu_sec,
       buffer_gets,
       disk_reads,
       rows_processed
FROM   v$sqlstats
WHERE  sql_text LIKE :SQL_TEXT_PATTERN;
```

### G.2 SET AUTOTRACE (SQL\*Plus 전용)

```sql
-- SQL*Plus 세션에서 통계와 계획을 함께 출력.
SET AUTOTRACE ON STATISTICS;
SELECT 1 FROM dual;
SET AUTOTRACE OFF;
```

---

## H. 시스템 파라미터

### H.1 DB 버전

```sql
-- 응답 권고를 버전에 맞춰 조정하기 위해 항상 첫 정보 요청에 포함.
SELECT banner FROM v$version WHERE rownum = 1;
```

### H.2 옵티마이저 핵심 파라미터

```sql
-- OPTIMIZER_MODE, OPTIMIZER_FEATURES_ENABLE, DB_BLOCK_SIZE 등.
SELECT name, value
FROM   v$parameter
WHERE  name IN ('optimizer_mode',
                'optimizer_features_enable',
                'db_block_size',
                'cursor_sharing',
                'optimizer_index_cost_adj',
                'optimizer_index_caching');
```

---

## I. 권한 부족 시 대안

`USER_*` 뷰에 접근할 수 없거나 다른 스키마 객체 정보가 필요할 때 다음 매핑을 사용한다.

| `USER_*` | `ALL_*` | `DBA_*` | 비고 |
|----------|---------|---------|------|
| `USER_TABLES` | `ALL_TABLES` | `DBA_TABLES` | `OWNER` 컬럼 추가 |
| `USER_TAB_STATISTICS` | `ALL_TAB_STATISTICS` | `DBA_TAB_STATISTICS` | |
| `USER_TAB_COL_STATISTICS` | `ALL_TAB_COL_STATISTICS` | `DBA_TAB_COL_STATISTICS` | |
| `USER_HISTOGRAMS` | `ALL_HISTOGRAMS` | `DBA_HISTOGRAMS` | |
| `USER_INDEXES` | `ALL_INDEXES` | `DBA_INDEXES` | |
| `USER_IND_COLUMNS` | `ALL_IND_COLUMNS` | `DBA_IND_COLUMNS` | |
| `USER_CONSTRAINTS` | `ALL_CONSTRAINTS` | `DBA_CONSTRAINTS` | |
| `USER_CONS_COLUMNS` | `ALL_CONS_COLUMNS` | `DBA_CONS_COLUMNS` | |

`V$` 뷰 권한이 거부되면:
- `V$SQL`, `V$SQLSTATS`, `V$SQL_BIND_CAPTURE`, `V$PARAMETER` 모두 `SELECT` 권한이 별도로 필요
- 권한 부재 시 정적 통계(`USER_TAB_STATISTICS` 등)만으로 진행하고 응답에 한계 고지

`DBA_*` 뷰 접근에는 `DBA` 롤, `SELECT ANY DICTIONARY`, 또는 `SELECT_CATALOG_ROLE` 중 하나가 필요하다.

`DBMS_XPLAN.DISPLAY_AWR`은 Enterprise Edition + Diagnostics Pack 라이선스를 요구한다. 라이선스 미보유 시 `DISPLAY_CURSOR` 또는 `EXPLAIN PLAN`으로 대체.

---

## 부록: 통계 재수집 권고 SQL

```sql
-- 통계 노후화가 감지되면 사용자에게 다음을 권고.
EXEC DBMS_STATS.GATHER_TABLE_STATS(USER, :TABLE_NAME, cascade => TRUE, method_opt => 'FOR ALL INDEXED COLUMNS SIZE AUTO');
```

```sql
-- 특정 컬럼의 히스토그램 부재가 의심되면.
EXEC DBMS_STATS.GATHER_TABLE_STATS(USER, :TABLE_NAME, method_opt => 'FOR COLUMNS :COLUMN_NAME SIZE AUTO');
```
