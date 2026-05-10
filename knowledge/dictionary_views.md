# 버전별 딕셔너리 뷰 차이 (11g R2 / 12c / 19c / 21c)

본 문서는 Phase 1 SQL 튜닝 정보 수집에 영향을 주는 변경만 정리한다. 모든 버전 비교가 아니라 **에이전트가 권고를 분기해야 할 정도의 차이**에 한정.

## 0. 빠른 참조 표

| 항목 | 11g R2 | 12c | 19c | 21c | Phase 1 영향 |
|------|--------|-----|-----|-----|---------------|
| 컬럼 통계 잠금 (`STATTYPE_LOCKED`) | 있음 (제한) | `USER_TAB_STATISTICS`에 정식 | 동일 | 동일 | 통계 노후도 판단 시 잠금 여부 확인 |
| 적응형 계획 / 적응형 통계 | 없음 | 도입(기본 ON) | 적응형 통계 기본 OFF | 동일 | 12c 이상에서 `note` 섹션의 `dynamic statistics used` 해석 |
| 히스토그램 타입 | `FREQUENCY`, `HEIGHT BALANCED` | `FREQUENCY`, `HEIGHT BALANCED`, **`HYBRID`**, **`TOP-FREQUENCY`** | 동일 | 동일 | 12c+에서 HYBRID/TOP-FREQUENCY 해석 |
| `DBMS_XPLAN.DISPLAY_CURSOR` 포맷 | `ALLSTATS LAST` 동일 | 동일 | 동일 | 동일 | 변동 없음 |
| `DBMS_XPLAN.DISPLAY_AWR` | EE+Diagnostics Pack | 동일 | 동일 | 동일 | 라이선스 확인 |
| 자동 인덱스 (`DBMS_AUTO_INDEX`) | 없음 | 없음 | **19c+** (Exadata, ADB) | 강화 | 19c+에서 `SYS_AI_*` 인덱스 등장 가능. 사용자에게 자동 인덱스 활성화 여부 확인 |
| `OPTIMIZER_FEATURES_ENABLE` 기본값 | `11.2.0.4` | `12.x.x.x` | `19.1.0` | `21.1.0` | 비표준 설정 시 옵티마이저 동작이 과거 버전 호환 |
| `V$SQL_BIND_CAPTURE` | 사용 가능 | 동일 | 동일 | 동일 | 변동 없음 |
| `USER_TAB_PARTITIONS` | 동일 | `INTERVAL` 파티션 추가 메타 | 동일 | 동일 | 인터벌 파티션 식별 시 12c+ 필요 |
| Real-Time Statistics | 없음 | 없음 | **19c+** | 강화 | DML 후 실시간 통계로 옵티마이저 동작이 더 빠르게 변동 |
| 매크로 SQL 매크로 | 없음 | 없음 | 없음 | **21c+** | Phase 1 범위 외 |

## 1. 11g R2 → 12c

### 1.1 적응형 기능 도입
- 12c부터 **Adaptive Plan**과 **Adaptive Statistics**가 기본 활성화. 실행 시 옵티마이저가 계획을 변경할 수 있다.
- `DBMS_XPLAN.DISPLAY_CURSOR` 출력 하단의 `Note` 섹션에 다음이 등장할 수 있음:
  - `- this is an adaptive plan`
  - `- dynamic statistics used: dynamic sampling (level=N)`
- 12.2부터 적응형 통계는 기본 OFF, 적응형 계획은 기본 ON.

### 1.2 히스토그램 신규 타입
- `HYBRID`, `TOP-FREQUENCY` 타입 추가. NDV가 254를 넘으면서 데이터 분포가 편향된 경우에 자동 선택.
- 11g 코드를 그대로 적용하면 `HEIGHT BALANCED`로 표기되며 정밀도가 더 낮다.

### 1.3 컬럼 통계 잠금
- `USER_TAB_STATISTICS.STATTYPE_LOCKED`가 정식 컬럼으로 노출. `DATA`, `CACHE`, `ALL` 등의 값.

## 2. 12c → 19c

### 2.1 자동 인덱스 (Auto Indexing)
- 19c부터 `DBMS_AUTO_INDEX` 패키지로 자동 인덱스 추천/생성. Exadata와 Autonomous Database에서 더 적극적으로 동작.
- 자동 인덱스는 `SYS_AI_` 접두사. 일반 `USER_INDEXES`에 노출되며 `AUTO`=`YES` 컬럼으로 식별.
- **권고 시 사용자에게 다음을 확인**: 자동 인덱스 활성화 여부, `AUTO_INDEX_MODE` 파라미터.

### 2.2 Real-Time Statistics
- DML 직후 실시간으로 통계가 갱신되어 옵티마이저가 즉시 반영. `LAST_ANALYZED`가 갱신되지 않더라도 `NUM_ROWS` 등은 최신값.
- 진단 시 `LAST_ANALYZED`만으로 노후도를 판단하면 오해할 수 있음. 19c+에서는 `USER_TAB_STATISTICS.STALE_STATS`도 함께 확인.

### 2.3 SQL Quarantine (19c+)
- 비효율적 SQL 계획을 격리. 19.7+ 일부 환경에서 가용.
- Phase 1 범위에서는 정보 제공만.

## 3. 19c → 21c

- `OPTIMIZER_FEATURES_ENABLE` 기본값 `21.1.0`으로 상향.
- SQL Macro 도입(`SQL_MACRO`) — Phase 1 범위 외.
- Real-Time Statistics 강화 — 권고는 19c와 동일.

## 4. 에이전트 동작 분기 가이드

세션 초기에 사용자가 제공한 `V$VERSION` 값에 따라 다음을 분기한다.

```
DB_VERSION = "11.2.x"
  ├ 히스토그램 권고: FREQUENCY / HEIGHT BALANCED만 언급
  ├ Adaptive 관련 NOTE 해석: 미적용 (등장하지 않음)
  └ Auto Indexing: 미언급

DB_VERSION = "12.x" 또는 "18.x"
  ├ 히스토그램 4종 모두 언급
  ├ Adaptive Plan/Statistics NOTE 해석 포함
  └ Auto Indexing: 미언급

DB_VERSION = "19.x"
  ├ 히스토그램 4종
  ├ Adaptive Plan(기본 ON) / Adaptive Statistics(기본 OFF)
  ├ Real-Time Statistics 가능성 고려: STALE_STATS와 LAST_ANALYZED 동시 확인 권고
  └ Auto Indexing 활성화 여부 확인. SYS_AI_* 인덱스 식별

DB_VERSION = "21.x"
  └ 19c와 동일하되 OFE 기본값만 차이
```

## 5. 자주 사용되는 뷰의 버전별 가용성

| 뷰 | 11g R2 | 12c | 19c | 21c |
|----|:------:|:---:|:---:|:---:|
| `USER_TABLES` | O | O | O | O |
| `USER_TAB_STATISTICS` | O | O | O | O |
| `USER_TAB_COL_STATISTICS` | O | O | O | O |
| `USER_HISTOGRAMS` | O | O | O | O |
| `USER_INDEXES` | O | O | O | O |
| `USER_IND_COLUMNS` | O | O | O | O |
| `USER_IND_STATISTICS` | O | O | O | O |
| `USER_CONSTRAINTS` | O | O | O | O |
| `USER_CONS_COLUMNS` | O | O | O | O |
| `V$SQL` | O | O | O | O |
| `V$SQLSTATS` | O | O | O | O |
| `V$SQL_BIND_CAPTURE` | O | O | O | O |
| `V$PARAMETER` | O | O | O | O |
| `V$VERSION` | O | O | O | O |
| `DBMS_XPLAN.DISPLAY` | O | O | O | O |
| `DBMS_XPLAN.DISPLAY_CURSOR` | O | O | O | O |
| `DBMS_XPLAN.DISPLAY_AWR` | O¹ | O¹ | O¹ | O¹ |

¹ EE + Diagnostics Pack 라이선스 필요.

Phase 1 범위에서 사용하는 모든 뷰는 11g R2 이상 전 버전에서 가용하다. 분기는 주로 **해석 방법**에서 발생한다.
