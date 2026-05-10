# 튜닝 사례집

본 문서의 모든 사례는 마스킹된 공개 도메인(`ORDERS`, `CUSTOMERS`, `PRODUCTS`, `ORDER_ITEMS`, `EMPLOYEES`)으로 작성되었다. 실 회사·실 컬럼·실 데이터는 포함되지 않는다.

각 사례는 다음 7섹션 포맷을 따른다.
1. 상황
2. 제공 정보
3. 진단
4. 가설
5. 대안
6. 튜닝 SQL
7. 검증 결과

---

## 사례 1. 조인 인덱스 누락으로 인한 FULL TABLE SCAN

### 1. 상황
주문/고객 조회 SQL이 평균 60초 소요. 동일 SQL이 수개월 전에는 10초 이내였다고 보고됨.

### 2. 제공 정보
- DB 버전: 19c
- 원본 SQL:
  ```sql
  SELECT o.order_id, c.customer_name, o.total_amount
  FROM   orders o, customers c
  WHERE  o.customer_id = c.customer_id
    AND  o.order_date >= :B1
    AND  o.status      = :B2
  ORDER BY o.order_date DESC;
  ```
- 테이블 통계: `ORDERS` 1억 건, `CUSTOMERS` 500만 건, 양쪽 `LAST_ANALYZED` 7일 이내
- 컬럼 통계: `ORDER_DATE` NDV 730, `STATUS` NDV 5, 둘 다 히스토그램 없음
- 인덱스: `PK_ORDERS(ORDER_ID)`, `PK_CUSTOMERS(CUSTOMER_ID)`, `IDX_ORDERS_CUSTOMER(CUSTOMER_ID)` — `ORDER_DATE`/`STATUS` 결합 인덱스 부재
- 실행 계획: `ORDERS`에 `TABLE ACCESS FULL`, `HASH JOIN`, A-Rows 1.2M, A-Time 58초

### 3. 진단
- `ORDERS`에 `FULL TABLE SCAN` 발생 — 근거: DISPLAY_CURSOR Id=2 `TABLE ACCESS FULL`, A-Rows=1.2M
- `ORDER_DATE >= :B1 AND STATUS = :B2`의 결합 선택도 약 1.2% — 근거: A-Rows 120만 / NUM_ROWS 1억
- 결합 인덱스 부재로 옵티마이저가 FULL SCAN 선택

### 4. 가설
1. **인덱스 부재** — `(ORDER_DATE, STATUS)` 결합 인덱스가 없어 1억 건 FULL SCAN 강제
2. 통계는 노후화되지 않음 — 가설 1이 단독 원인일 가능성이 높음

### 5. 대안
1. **(권장) `IDX_ORDERS_DATE_STATUS` 결합 인덱스 추가**
   - 예상 효과: 논리적 읽기 약 95% 감소, A-Time 58초 → 5초 수준
   - 리스크: INSERT/UPDATE 시 인덱스 유지 비용 약 3% 추가
   - 적용 조건: 결합 선택도 1% 수준 유지될 때

2. 힌트만으로 임시 우회 — `FIRST_ROWS(100)`
   - 예상 효과: 5~20% 개선
   - 리스크: 부분 응답에는 빨라지나 전체 처리 시간은 큰 변화 없음

### 6. 튜닝 SQL
```sql
SELECT /*+ LEADING(o c) USE_NL(c) INDEX(o IDX_ORDERS_DATE_STATUS) */
       o.order_id, c.customer_name, o.total_amount
FROM   orders o, customers c
WHERE  o.customer_id = c.customer_id
  AND  o.order_date >= :B1
  AND  o.status      = :B2
ORDER BY o.order_date DESC;
```

DDL:
```sql
CREATE INDEX IDX_ORDERS_DATE_STATUS ON ORDERS (ORDER_DATE, STATUS) ONLINE;
EXEC DBMS_STATS.GATHER_INDEX_STATS(USER, 'IDX_ORDERS_DATE_STATUS');
```

### 7. 검증 결과
| 지표 | 원본 | 튜닝 | 개선율 |
|------|------|------|--------|
| Buffers | 1,250,000 | 48,200 | 96.1% |
| A-Time | 58.2초 | 4.7초 | 91.9% |
| A-Rows | 1,200,000 | 1,200,000 | 동일 |

---

## 사례 2. 통계 노후화로 인한 카디널리티 오추정

### 1. 상황
배치 SQL의 수행 시간이 점진적으로 증가. 6개월 전 12분 → 현재 38분.

### 2. 제공 정보
- DB 버전: 12c
- 원본 SQL:
  ```sql
  SELECT p.product_id, SUM(oi.quantity) AS total_qty
  FROM   products p, order_items oi
  WHERE  p.product_id = oi.product_id
    AND  p.category   = :B1
  GROUP BY p.product_id;
  ```
- 테이블 통계: `PRODUCTS` `NUM_ROWS=50,000`, `LAST_ANALYZED` 192일 경과; `ORDER_ITEMS` `NUM_ROWS=200만`, `LAST_ANALYZED` 200일 경과
- 실제 행 수(사용자 측정): `PRODUCTS` 약 18만, `ORDER_ITEMS` 약 1억 2천만
- 실행 계획: `NESTED LOOPS`, A-Rows 1억 2천만, E-Rows 200만 (60배 괴리)

### 3. 진단
- `E-Rows`(200만) ≪ `A-Rows`(1.2억) — 60배 괴리. 통계 일관성 검증 실패
- `PRODUCTS.LAST_ANALYZED` 192일, `ORDER_ITEMS.LAST_ANALYZED` 200일 — 유효성 강한 경고
- `NESTED LOOPS`로 1.2억 회 inner 접근 — 부적합

### 4. 가설
1. **통계 노후화** — 통계상 행 수가 실제의 3~60배 차이. 옵티마이저가 NL JOIN을 잘못 선택
2. 통계 갱신만으로 `HASH JOIN`으로 자동 전환될 가능성 높음

### 5. 대안
1. **(권장) 통계 재수집 후 재실행**
   - 예상 효과: HASH JOIN 자동 선택 시 60~80% 개선
   - 리스크: 통계 수집 자체의 부하 (대상 테이블이 커서 시간 소요)
   - 적용 조건: 야간 배치 직전 또는 유지보수 시간

2. 힌트로 즉시 강제 — `USE_HASH(oi)`
   - 예상 효과: 50~70% 개선
   - 리스크: 통계 갱신 후 옵티마이저가 더 나은 선택을 했을 수 있는데 힌트로 고정해 버림

### 6. 튜닝 SQL
권장안은 SQL을 수정하지 않고 통계만 재수집:
```sql
EXEC DBMS_STATS.GATHER_TABLE_STATS(USER, 'PRODUCTS', cascade => TRUE, method_opt => 'FOR ALL INDEXED COLUMNS SIZE AUTO');
EXEC DBMS_STATS.GATHER_TABLE_STATS(USER, 'ORDER_ITEMS', cascade => TRUE, method_opt => 'FOR ALL INDEXED COLUMNS SIZE AUTO');
```

차선:
```sql
SELECT /*+ USE_HASH(oi) */
       p.product_id, SUM(oi.quantity) AS total_qty
FROM   products p, order_items oi
WHERE  p.product_id = oi.product_id
  AND  p.category   = :B1
GROUP BY p.product_id;
```

### 7. 검증 결과
통계 재수집 후 자동 HASH JOIN 전환:
| 지표 | 원본 | 통계 갱신 후 | 개선율 |
|------|------|--------------|--------|
| A-Time | 38분 | 9분 30초 | 75% |
| Buffers | 4,800,000 | 980,000 | 79.6% |
| 조인 방식 | NESTED LOOPS | HASH JOIN | — |

---

## 사례 3. ORDER BY 정렬 부하 — 인덱스 활용

### 1. 상황
주문 목록 페이지네이션 SQL의 응답 시간이 800ms~1.5초. 페이지당 50건 표시.

### 2. 제공 정보
- DB 버전: 19c
- 원본 SQL:
  ```sql
  SELECT order_id, customer_id, order_date, status
  FROM   orders
  WHERE  customer_id = :B1
  ORDER BY order_date DESC
  FETCH FIRST 50 ROWS ONLY;
  ```
- 테이블 통계: `ORDERS` 1억 건, 평균 고객당 주문 1,200건
- 컬럼 통계: `CUSTOMER_ID` NDV 약 8만, 균등 분포
- 인덱스: `IDX_ORDERS_CUSTOMER(CUSTOMER_ID)` — `ORDER_DATE`는 미포함
- 실행 계획: `INDEX RANGE SCAN` → `TABLE ACCESS BY INDEX ROWID` → `SORT ORDER BY` (1,200행 정렬)

### 3. 진단
- 1,200행 정렬 자체는 부담스럽지 않으나, ROWID로 1,200회 랜덤 I/O 발생
- `CLUSTERING_FACTOR` 값이 `NUM_ROWS`에 근접 → 인덱스 스캔 후 랜덤 I/O 다수
- ORDER BY가 인덱스 정렬 순서를 활용하지 못함

### 4. 가설
1. `(CUSTOMER_ID, ORDER_DATE DESC)` 결합 인덱스로 정렬 제거 가능
2. 추가로 SELECT 컬럼이 적어 커버링 인덱스 후보가 됨

### 5. 대안
1. **(권장) `(CUSTOMER_ID, ORDER_DATE DESC)` 결합 인덱스**
   - 예상 효과: SORT 제거, 50행만 읽으면 종료. 응답 시간 50~100ms 수준
   - 리스크: INSERT 시 인덱스 유지 비용
   - 적용 조건: 고객별 주문 정렬 조회가 자주 발생

2. 커버링 인덱스 — `(CUSTOMER_ID, ORDER_DATE DESC, ORDER_ID, STATUS)`
   - 예상 효과: 테이블 미접근. 응답 시간 30~60ms
   - 리스크: 인덱스 크기 증가, INSERT 비용 더 큼

### 6. 튜닝 SQL
SQL 자체는 수정 불필요. DDL만:
```sql
CREATE INDEX IDX_ORDERS_CUST_DATE ON ORDERS (CUSTOMER_ID, ORDER_DATE DESC) ONLINE;
EXEC DBMS_STATS.GATHER_INDEX_STATS(USER, 'IDX_ORDERS_CUST_DATE');
```

힌트로 명시 권고(옵티마이저가 자동 선택하지 않을 경우):
```sql
SELECT /*+ INDEX(orders IDX_ORDERS_CUST_DATE) */
       order_id, customer_id, order_date, status
FROM   orders
WHERE  customer_id = :B1
ORDER BY order_date DESC
FETCH FIRST 50 ROWS ONLY;
```

### 7. 검증 결과
| 지표 | 원본 | 튜닝 | 개선율 |
|------|------|------|--------|
| Buffers | 1,250 | 54 | 95.7% |
| A-Time | 1,180ms | 62ms | 94.7% |
| SORT ORDER BY | 발생 | 제거 | — |

---

## 사례 4. 히스토그램 부재로 인한 잘못된 조인 방식

### 1. 상황
직원 검색 SQL이 일부 부서에서만 매우 느림. 동일 SQL인데 부서 코드에 따라 50ms ~ 12초 차이.

### 2. 제공 정보
- DB 버전: 12c
- 원본 SQL:
  ```sql
  SELECT e.employee_id, e.last_name, d.department_name
  FROM   employees e, departments d
  WHERE  e.department_id = d.department_id
    AND  e.department_id = :B1;
  ```
- 테이블 통계: `EMPLOYEES` 100만, `DEPARTMENTS` 50, `LAST_ANALYZED` 5일 이내
- 컬럼 통계: `EMPLOYEES.DEPARTMENT_ID` NDV 50, `HISTOGRAM = NONE`
- 실제 분포: 50개 부서 중 1개가 전체의 60%, 나머지 49개가 균등 분포
- 인덱스: `IDX_EMPLOYEES_DEPT(DEPARTMENT_ID)`
- 바인드 카디널리티: 작은 부서 조회 시 약 800행 / 큰 부서 조회 시 60만 행

### 3. 진단
- 옵티마이저는 NDV=50, 균등 분포 가정 → 평균 카디널리티 2만 추정 (`A-Rows`와 큰 괴리)
- 큰 부서 조회 시 `INDEX RANGE SCAN` + `TABLE ACCESS BY INDEX ROWID` 60만 회 → 부적합
- 히스토그램 부재가 데이터 편향을 옵티마이저에 전달하지 못함

### 4. 가설
1. **히스토그램 부재** — 빈도 분포를 옵티마이저가 인식하지 못해 모든 바인드 값에 동일 계획 적용
2. 큰 부서 조회 시에는 `FULL TABLE SCAN` + `HASH JOIN`이 유리

### 5. 대안
1. **(권장) `DEPARTMENT_ID` 컬럼에 히스토그램 추가**
   - 예상 효과: 옵티마이저가 바인드 피킹으로 적절한 계획 선택. 큰 부서 70% 개선, 작은 부서 변동 없음
   - 리스크: 첫 실행 후 계획이 캐시에 고정될 수 있음 (`bind sensitive` 효과)
   - 적용 조건: 12c 이상에서는 `TOP-FREQUENCY` 또는 `HYBRID` 자동 선택

2. SQL 분기 — 큰 부서/작은 부서를 어플리케이션에서 판별 후 다른 SQL 사용
   - 예상 효과: 안정적
   - 리스크: 어플리케이션 변경, 임계값 유지보수 필요

### 6. 튜닝 SQL
SQL 자체는 수정 불필요:
```sql
EXEC DBMS_STATS.GATHER_TABLE_STATS(USER, 'EMPLOYEES',
       method_opt => 'FOR COLUMNS DEPARTMENT_ID SIZE AUTO');
```

큰 부서 강제 시:
```sql
SELECT /*+ FULL(e) USE_HASH(d) */
       e.employee_id, e.last_name, d.department_name
FROM   employees e, departments d
WHERE  e.department_id = d.department_id
  AND  e.department_id = :B1;
```

### 7. 검증 결과
히스토그램 추가 후:
| 지표 | 큰 부서 원본 | 큰 부서 튜닝 | 작은 부서 원본 | 작은 부서 튜닝 |
|------|--------------|---------------|----------------|------------------|
| A-Time | 11.8초 | 2.4초 | 48ms | 51ms |
| Buffers | 612,000 | 184,000 | 920 | 920 |
| 조인 방식 | NL | HASH | NL | NL |
