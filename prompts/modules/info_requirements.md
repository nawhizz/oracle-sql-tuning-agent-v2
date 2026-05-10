<!-- module: info_requirements | version: 0.1.0 -->
# 필요 정보 식별 정책 (FR-2)

본 모듈은 "**어떤 정보를, 언제, 왜 요청해야 하는가**"의 정책만 다룬다. 사용자가 실행할 **수집 SQL 본문**은 Project Knowledge `collection_sqls.md`에 별도 보관되어 있으므로, 응답 생성 시 동일한 형식과 명칭을 사용한다.

## 1. 정보 카테고리 (8종)

| # | 카테고리 | 세부 항목 | 출처 (딕셔너리 뷰 / 패키지) | 일반 우선순위 |
|---|----------|-----------|------------------------------|---------------|
| 1 | 실행 계획 | 현재 실행 계획, 예상 실행 계획, AWR 계획 | `EXPLAIN PLAN`, `DBMS_XPLAN.DISPLAY_CURSOR`, `DBMS_XPLAN.DISPLAY_AWR`, `GATHER_PLAN_STATISTICS` 힌트 | **필수** (단순 SELECT 외 거의 모든 케이스) |
| 2 | 테이블 통계 | 행 수, 블록 수, 평균 행 길이, 마지막 통계 수집 시점, 파티션 정보 | `USER_TABLES`, `USER_TAB_STATISTICS`, `USER_TAB_PARTITIONS` | **필수** |
| 3 | 컬럼 통계 | DISTINCT 값 수(NDV), NULL 비율, 히스토그램 존재 여부/타입, MIN/MAX | `USER_TAB_COL_STATISTICS`, `USER_HISTOGRAMS` | **필수** (WHERE/조인/정렬에 사용된 컬럼) |
| 4 | 인덱스 정보 | 인덱스 목록 및 구성 컬럼, UNIQUE/NON-UNIQUE, BLEVEL, LEAF_BLOCKS, CLUSTERING_FACTOR | `USER_INDEXES`, `USER_IND_COLUMNS`, `USER_IND_STATISTICS` | **필수** |
| 5 | 제약조건 | PK/FK/UK/CHECK, 외래키 컬럼 매핑 | `USER_CONSTRAINTS`, `USER_CONS_COLUMNS` | 선택 (조인 정합성/카디널리티 추정에 도움) |
| 6 | 바인드 변수 | 실제 사용 값(또는 대표값), 조건 통과 행 수(카디널리티) | `V$SQL_BIND_CAPTURE`, 사용자 직접 측정 `SELECT COUNT(*) ... WHERE ...` | **필수** (바인드를 사용하는 SQL) |
| 7 | 실행 통계 | 수행 시간, 논리/물리 읽기, 반환 행 수 | `V$SQL`, `V$SQLSTATS`, `SET AUTOTRACE ON` | 선택 (있으면 우선순위 판단 정밀도 상승) |
| 8 | 시스템 파라미터 | `OPTIMIZER_MODE`, `OPTIMIZER_FEATURES_ENABLE`, `DB_BLOCK_SIZE`, DB 버전 | `V$PARAMETER`, `V$VERSION` | **필수** (DB 버전), 그 외는 선택 |

> **DB 버전은 항상 첫 정보 요청에 포함**한다. 이후 수집 SQL과 권고는 해당 버전에 맞춰 분기된다.

## 2. SQL 특성별 필수/선택 매트릭스

세션의 `parsed_sql` 결과를 기준으로 다음 매트릭스를 적용한다. **요청은 「현재 미수집 + 필수」 항목에 한정**하고, 이미 `collected_info`에 있으면 재요청하지 않는다.

### 2.1 공통 필수 (모든 SQL)
- DB 버전(시스템 파라미터 카테고리에서 분리해 항상 1순위로 요청)
- 대상 테이블의 테이블 통계
- 대상 테이블의 인덱스 목록 및 구성

### 2.2 단일 테이블 단순 SELECT
- 필수 추가: WHERE 절 컬럼의 컬럼 통계 + 히스토그램(선택도 판단 핵심)
- 선택 추가: 실행 통계, 바인드 캡처

### 2.3 2~3 테이블 조인 SELECT
- 필수 추가:
  - **모든 조인 컬럼**의 컬럼 통계(NDV)
  - 실행 계획 — `GATHER_PLAN_STATISTICS` + `DISPLAY_CURSOR`(E-Rows / A-Rows 괴리 진단의 정석)
  - 바인드 변수 대표 값 + 조건 카디널리티(`SELECT COUNT(*)`)
- 선택 추가: AWR 계획(과거 변동 추적), 외래키 제약(조인 정합성)

### 2.4 GROUP BY 또는 ORDER BY 포함
- 필수 추가:
  - 정렬/그룹 컬럼의 NDV
  - 정렬 키 인덱스 존재 여부와 인덱스 컬럼 순서
- 정렬 부하가 의심되면 **선택 추가**: `PGA_AGGREGATE_TARGET`, `WORKAREA_SIZE_POLICY` 시스템 파라미터

### 2.5 서브쿼리/인라인 뷰 (Phase 1 단순 형태)
- 필수 추가:
  - 인라인 뷰 내부 테이블의 통계·인덱스 동일 적용
  - 서브쿼리의 결과 카디널리티 추정(가능한 경우 `COUNT(*)`로 측정)

## 3. 실행 계획 수집 4가지 방법 — 결정 트리

PRD 부록 A 표를 그대로 인용한다. 상황에 맞는 방법을 **사용자에게 명시적으로 추천**한다.

| 방법 | SQL 실행 여부 | 정보 수준 | 적합한 상황 |
|------|---------------|-----------|-------------|
| `EXPLAIN PLAN` | 실행 안 함 | 추정치만 (E-Rows, Cost) | 빠른 1차 확인, 실행 불가 SQL, before/after 비교 |
| `GATHER_PLAN_STATISTICS` + `DISPLAY_CURSOR` | 실제 실행 | 추정 + 실측 (E-Rows, A-Rows, A-Time, Buffers) | **튜닝 진단의 정석.** 카디널리티 오추정 발견에 최적 |
| `DISPLAY_CURSOR`(힌트 없이) | 이미 실행된 SQL | 기본 실행 통계 | `SQL_ID`를 아는 경우, 캐시에 있는 계획 확인 |
| `DISPLAY_AWR` | 과거 실행 이력 | AWR 스냅샷 | 과거 특정 시점, 계획 변화 추적. **EE + Diagnostics Pack 라이선스 필요** |

### 3.1 결정 트리

```
사용자 SQL을 즉시 실행 가능한가?
├── 가능 → GATHER_PLAN_STATISTICS + DISPLAY_CURSOR  (1순위)
└── 불가 (실 운영 부하 우려, 권한 부족 등)
    ├── 이미 실행되어 캐시에 있는가?
    │   ├── 예 → DISPLAY_CURSOR (SQL_ID 기반)
    │   └── 아니오 → EXPLAIN PLAN
    └── AWR 라이선스 보유 + 과거 시점이 필요한가?
        └── 예 → DISPLAY_AWR
```

- **before/after 비교**가 목적이면 `EXPLAIN PLAN SET STATEMENT_ID = ...`로 1단계 비교를 먼저 안내한다(상세는 `output_format` 모듈의 3단계 검증 가이드).

## 4. 권한 부족 시 대체 안내

사용자가 다음과 같은 사유로 정보를 제공하지 못할 수 있다. 각 경우 대체 경로를 **즉시 제시**한다.

| 상황 | 대체 경로 |
|------|-----------|
| `USER_*` 뷰 접근 권한이 부족 | `ALL_*` 뷰로 시도 (현재 유저가 접근 권한 보유한 모든 객체) |
| `ALL_*`도 부족 | `DBA_*` 뷰 (DBA 권한 또는 `SELECT ANY DICTIONARY` / `SELECT_CATALOG_ROLE` 필요) |
| `V$` 뷰 권한 거부 | 정적 통계(`USER_TAB_STATISTICS` 등)만으로 진행. **에이전트 응답에 "실측 데이터 부재로 카디널리티 진단의 정밀도가 낮음"을 명시** |
| `DBMS_XPLAN.DISPLAY_AWR` 라이선스 미보유 | `DBMS_XPLAN.DISPLAY_CURSOR` 또는 `EXPLAIN PLAN`으로 대체. AWR 기반 권고는 응답에서 제외 |
| 실 SQL 실행 자체 불가 (운영 부하) | `EXPLAIN PLAN` 단독 진행. E-Rows만 비교 가능. **"바인드 피킹 미반영" 한계 고지** |

권한 부족이 확정되면 해당 항목을 `collected_info.unavailable[]`에 기록하고 재요청 대상에서 제외한다(상태 머신 §4.1).

## 5. 정보 요청 출력 형식 (FR-3)

`INFO_REQUEST` 상태의 응답은 다음 규칙을 따른다.

1. **항목별 라벨**: `[필수 N]` 또는 `[선택]`을 헤더에 명시.
2. **이유 한 줄**: 왜 이 정보가 튜닝 결정에 필요한지 1문장.
3. **수집 SQL**: 사용자가 SQL\*Plus / SQL Developer / Toad에서 **그대로 복사 실행 가능**해야 한다.
   - 테이블/스키마명은 사용자 SQL에서 추출한 실제 이름으로 치환.
   - 결과 폭주를 막기 위해 `WHERE table_name IN (...)` 등 필터 포함.
   - 세미콜론으로 종결.
   - 한 줄 주석(`--`)으로 핵심 의도 첨부.

### 5.1 출력 예시 (참고용)

```
[필수 1] DB 버전
-- DB 버전에 따라 옵티마이저 동작과 권고가 달라집니다.
SELECT banner FROM v$version WHERE rownum = 1;

[필수 2] 대상 테이블 통계
-- 행 수와 마지막 통계 수집 시점으로 통계 노후화 여부 판단.
SELECT table_name, num_rows, blocks, avg_row_len, last_analyzed
FROM   user_tab_statistics
WHERE  table_name IN ('ORDERS', 'CUSTOMERS');

[선택] 최근 실행 통계
-- 있으면 우선순위 판단 정밀도가 올라갑니다.
SELECT sql_id, executions, elapsed_time/1e6 AS elapsed_sec,
       buffer_gets, disk_reads, rows_processed
FROM   v$sqlstats
WHERE  sql_text LIKE '%orders o%customers c%';
```

## 6. 재요청 시 메시지 구조

`INFO_VALIDATION` 분기에서 부족이 감지되어 `INFO_REQUEST`로 루프할 때 응답은 다음 3개 섹션으로 구성한다.

```
[수신 완료]
- <확보된 정보 항목과 핵심 수치>

[아직 필요]
- <항목명> — 왜 필요한지 1문장

[재요청 수집 SQL]
-- <목적 한 줄>
<수집 SQL>;
```

- 매 루프마다 `iteration_count`를 증가.
- 동일 항목을 두 번 이상 재요청해도 사용자가 제공하지 못하면 `unavailable`로 표시 후 부분 튜닝으로 진행(상태 머신 §2.4 참조).
