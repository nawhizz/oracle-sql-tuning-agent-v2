# MVP v0.1.0 산출물 최종 체크리스트

본 문서는 v0.1.0 Claude.ai Project 동기화 직전 점검 항목이다. 모든 체크박스가 충족된 상태에서 동기화 절차(`docs/sync_to_claude_ai.md`)를 진행한다.

## 1. 저장소 골격 (T01)
- [x] 디렉토리: `prompts/modules/`, `knowledge/`, `tests/scenarios/`, `tests/results/`, `docs/`, `scripts/`, `.claude/commands/`
- [x] 루트 파일: `README.md`, `CLAUDE.md`, `.gitignore`, `requirements.txt`, `.env.example`
- [x] 추적 파일: `prompts/CHANGELOG.md`, `docs/sync_log.md`, `docs/sync_to_claude_ai.md`, `docs/prompt_versioning.md`

## 2. 시스템 프롬프트 모듈 5종 (T02 ~ T04)
- [x] `prompts/modules/role.md` — 정체성/금지 표현 5종/Phase 1 SQL 범위/지원 버전/비기능 요구사항
- [x] `prompts/modules/state_machine.md` — 6 상태 다이어그램·전이 조건·SessionContext·재시작 명령
- [x] `prompts/modules/info_requirements.md` — 8 카테고리 표·SQL 특성 매트릭스 5종·실행 계획 결정 트리·권한 대체 5종
- [x] `prompts/modules/validation_rules.md` — 검증 4종 임계값·재요청 3섹션 헤더 고정
- [x] `prompts/modules/output_format.md` — 6 섹션 헤더 고정·3단계 검증 가이드·이상 상황 해석 5종

## 3. Knowledge 자산 4종 (T05 ~ T06)
- [x] `knowledge/collection_sqls.md` — 9 섹션(A 실행 계획 4종/B 테이블/C 컬럼+히스토그램/D 인덱스/E 제약/F 바인드/G 실행 통계/H 시스템 파라미터/I 권한 대안)
- [x] `knowledge/hints_reference.md` — 22개 힌트 (문법/효과/조건/주의 4항)
- [x] `knowledge/dictionary_views.md` — 11g R2 / 12c / 19c / 21c 4 버전 차이 표·분기 가이드
- [x] `knowledge/tuning_cases.md` — 4 사례 (7 섹션 포맷 모두 충족)

## 4. 빌드/동기화 도구 (T07)
- [x] `scripts/build_system_prompt.py` — 모듈 조립·토큰 근사치·git hash 메타 주입
- [x] `.claude/commands/build-system-prompt.md`
- [x] `.claude/commands/run-tests.md`
- [x] `.claude/commands/new-scenario.md`
- [x] `.claude/commands/prompt-diff.md`
- [x] `.claude/commands/sync-check.md`
- [x] `docs/sync_to_claude_ai.md` — 시스템 프롬프트 4단계 + Knowledge 4단계 + sync_log 양식 + [SYNC-REQUIRED] 표 + 롤백 + FAQ
- [x] `docs/prompt_versioning.md` — 브랜치/커밋 prefix 5종/SemVer/CHANGELOG 양식/A·B 실험/롤백

## 5. 회귀 테스트 (T08 ~ T10)
- [x] `tests/scenarios/` 11개 YAML — 단일 2 / 2 테이블 4 / 3 테이블 2 / 루프 3 (모두 4 턴 이상)
- [x] `tests/run_tests.py` — Anthropic API 호출, --filter/--model/--judge/--cache/--dry-run, JSON+MD 리포트
- [x] `tests/sql_validator.py` — 코드 펜스 추출, 위험 키워드 11종 차단, 1차 토큰 화이트리스트
- [x] `tests/test_sql_validator.py` — 16개 단위 테스트 OK
- [x] dry-run 11/11 시나리오 로드 OK
- [x] sql_validator 검증: `knowledge/collection_sqls.md` 20/20 PASS

## 6. PRD §7.2 Go/No-Go 자동 측정 결과

| # | 기준 | 자동 측정 가능 | 본 시점 결과 | 메모 |
|---|------|----------------|--------------|------|
| ① | 시나리오 정확 식별 (≥10건) | 예 | 시나리오 11건 작성·dry-run 통과 | 실 API 호출 시 must_request 통과율 산출 (T11 단계 6 참조) |
| ② | 재요청 루프 동작 | 예 | 시나리오 009/010/011 모두 4 턴 ≥ | 실 API 호출 시 [수신 완료]/[아직 필요]/[재요청 수집 SQL] 헤더 매칭 측정 |
| ③ | 수집 SQL 19c 문법 무오류 | 예 | knowledge/collection_sqls.md **20/20 PASS**, 단위 테스트 16/16 OK | sql_validator |
| ④ | 포맷 일관성 ([진단/가설/대안/SQL/검증]) | 예 | 시나리오 11건 expected.must_include_section 헤더 고정 | 실 API 호출 시 매칭 측정 |
| ⑤ | 사용자 수용률 ≥ 70% | 아니오 | `docs/beta_rollout_plan.md` 작성 완료 | 4주 베타 운용으로 측정 |

## 7. 베타 운용 (Go/No-Go ⑤) (T11)
- [x] `docs/beta_rollout_plan.md` — 모집 5~10명, 피드백 양식 7항, 5개 지표, GO/CONDITIONAL/NO 의사결정

## 8. 동기화 직전 점검
- [ ] `git init`(없는 경우) 후 모든 파일 첫 커밋. 커밋 메시지: `docs: MVP v0.1.0 초기 산출물 [SYNC-REQUIRED]`
- [ ] `git tag -a v0.1.0 -m "v0.1.0: 초기 시스템 프롬프트 + Knowledge 4종 + 시나리오 11건 + 자동 평가 파이프라인"`
- [ ] `python scripts/build_system_prompt.py` 재실행 후 토큰 근사치 확인 (현재 ~8,070 토큰)
- [ ] `prompts/build/system.txt` 복사 → Claude.ai Project Custom Instructions 붙여넣기
- [ ] `knowledge/*.md` 4종 → Claude.ai Project Knowledge 업로드
- [ ] `docs/sync_log.md` 에 항목 추가
- [ ] (선택) `python tests/run_tests.py --cache` 로 11건 일괄 회귀 검증, 결과를 `tests/results/` 보관
- [ ] 베타 운용 시작 (안내 메일 + 온보딩 세션)

## 9. 미통과/잔여 항목 → v0.2.0 백로그

본 시점에서는 자동 측정 항목 모두 통과(③ 100%, ① ② ④ 는 dry-run 단계). 실 API 호출 회귀 검증 후 발견되는 항목과 베타 피드백을 기반으로 `prompts/CHANGELOG.md` 의 `v0.2.0 백로그` 섹션에 누적한다.
