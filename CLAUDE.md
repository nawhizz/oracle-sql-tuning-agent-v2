# Oracle SQL 튜닝 에이전트 — 개발 가이드

## 프로젝트 성격

본 저장소는 **Claude.ai Project로 배포되는 SQL 튜닝 에이전트의 프롬프트와 Knowledge 자산을 관리**한다. Claude.ai Project는 실행 환경, 본 저장소가 source of truth이다.

요구사항 정의는 `docs/oracle_sql_tuning_agent_prd_v1.4.docx`(PRD v1.4)이다. 모든 작업은 PRD를 1차 출처로 참조한다.

## 작업 규칙

1. **시스템 프롬프트 수정 시** `prompts/CHANGELOG.md`에 변경 요약을 기록한다.
2. **프롬프트 변경은 반드시 `tests/scenarios/`의 기존 시나리오로 회귀 검증**한다. 미통과 시 머지 금지.
3. **새 정보 카테고리 추가 시** `prompts/modules/info_requirements.md`와 `knowledge/collection_sqls.md`를 함께 수정한다.
4. **Claude.ai Project 동기화는 `docs/sync_to_claude_ai.md` 절차를 준수**한다. 동기화 후 `docs/sync_log.md`에 항목 추가.

## 참조 파일

- @prompts/system.md (또는 빌드 산출물 `prompts/build/system.txt`)
- @knowledge/collection_sqls.md

## 금지 사항

- **민감한 회사 데이터를 Knowledge·시나리오·문서에 포함하지 않는다.**
- **실제 운영 SQL을 시나리오에 그대로 사용하지 않는다(마스킹 필수).**
- 외부 DB에 직접 접속하는 코드/도구를 추가하지 않는다(MVP 비목표).
- Claude.ai 외부 SaaS에 사용자 데이터를 전송하는 기능을 추가하지 않는다.

## 커밋 메시지 컨벤션

prefix를 통해 변경 영역을 명시한다:

| Prefix | 영역 |
|---|---|
| `prompt:` | `prompts/modules/`, `prompts/CHANGELOG.md` |
| `knowledge:` | `knowledge/*.md` |
| `test:` | `tests/scenarios/`, `tests/run_tests.py`, `tests/sql_validator.py` |
| `docs:` | `docs/`, `README.md`, `CLAUDE.md` |
| `tooling:` | `scripts/`, `.claude/commands/`, `.gitignore`, `requirements.txt` |

예: `prompt: 히스토그램 확인 요청을 선택 → 필수로 승격`

Claude.ai Project 동기화가 필요한 변경에는 커밋 메시지에 `[SYNC-REQUIRED]` 태그를 포함한다.

## 릴리즈 태깅

Claude.ai Project 동기화 시점마다 Git 태그(`v0.1.0`, `v0.2.0` …)를 생성한다. 롤백은 태그 기준으로 수행한다.

## 언어 규칙

- 문서·주석·커밋 메시지: **한국어**
- SQL 키워드 및 Oracle 고유 용어(`DBMS_XPLAN`, `UNIQUE SCAN`, `GATHER_PLAN_STATISTICS` 등): **영문 원문 유지**
- 변수명·함수명·파일명: 영문 snake_case
