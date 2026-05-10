# 프롬프트 변경 이력

본 문서는 `prompts/modules/` 하위 시스템 프롬프트의 변경을 기록한다. Claude.ai Project 동기화는 `docs/sync_log.md` 에서 별도 추적한다.

## v0.1.0 — MVP 초기 릴리즈 (Stage 1 + Phase 1)

### 시스템 프롬프트 모듈 5종
- `role.md` v0.1.0 — 정체성, 금지 표현 5종(경험상/일반적으로/보통은/아마도/대체로), Phase 1 SQL 범위(단일~3 테이블 SELECT), Oracle 19c 우선 지원, PRD §5 비기능 요구사항.
- `state_machine.md` v0.1.0 — 6 상태 다이어그램(INIT/SQL_ANALYSIS/INFO_REQUEST/INFO_VALIDATION/TUNING/DELIVERY)·전이 조건, FR-1 SQL 파싱 출력 형식, FR-6 SessionContext 9 키, 재시작 명령 3종.
- `info_requirements.md` v0.1.0 — 8 정보 카테고리, SQL 특성별 필수/선택 매트릭스 5종, 실행 계획 4가지 결정 트리, 권한 부족 5종 대체 경로, FR-3 정보 요청 출력 형식.
- `validation_rules.md` v0.1.0 — 검증 4종(형식/완전성/일관성/유효성) 임계값, 재요청 응답 3 섹션 헤더 고정([수신 완료]/[아직 필요]/[재요청 수집 SQL]).
- `output_format.md` v0.1.0 — 6 섹션 헤더 고정([진단 요약]/[가설]/[튜닝 대안]/[튜닝된 SQL — 권장안 기준]/[DDL (필요 시)]/[검증 방법]), 3단계 검증 가이드, 이상 상황 해석 5종.

### Knowledge 자산 4종
- `collection_sqls.md` — 9 섹션, 수집 SQL 정적 검증 20/20 PASS.
- `hints_reference.md` — 22 힌트 (4항 포맷).
- `dictionary_views.md` — 11g R2 / 12c / 19c / 21c 4 버전 분기 가이드.
- `tuning_cases.md` — 4 사례 (7 섹션 포맷).

### 인프라
- `scripts/build_system_prompt.py` — 모듈 조립 빌드.
- `tests/run_tests.py` — Anthropic API 자동 평가 (시나리오 11건, --filter/--judge/--cache).
- `tests/sql_validator.py` — SQL 정적 문법 검증, 단위 테스트 16/16 OK.
- 슬래시 커맨드 5종.
- 동기화 절차서 / 버전 관리 규칙 / 베타 운용 계획.

### 영향 시나리오
- 회귀 테스트 시나리오 11건 모두 본 v0.1.0 모듈을 기준으로 작성됨.

---

## v0.2.0 백로그

베타 운용(`docs/beta_rollout_plan.md`) 결과 및 실 API 회귀 검증에서 발견되는 항목을 누적한다.

- _현재 비어 있음_

후보 영역(잠재 백로그):
- (TBD) 응답 길이 최적화 — 실 API 응답이 토큰 한도를 초과하는 시나리오 발견 시.
- (TBD) `info_requirements` 의 SQL 특성 매트릭스에 서브쿼리/CTE 분기 보강.
- (TBD) `validation_rules` 의 일관성 임계값을 베타 데이터로 보정.
