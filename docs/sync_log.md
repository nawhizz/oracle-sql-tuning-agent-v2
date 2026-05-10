# Claude.ai Project 동기화 기록

본 문서는 본 저장소의 `prompts/`, `knowledge/` 자산을 Claude.ai Project로 반영한 이력을 기록한다. 동기화 절차는 `docs/sync_to_claude_ai.md`를 참조한다.

| 일시 | Git 해시 | 태그 | 변경 요약 | 담당 |
|------|----------|------|-----------|------|
| 2026-05-10 20:35 | fd01f9f | v0.1.0 | 초기 시스템 프롬프트 5종(role/state_machine/info_requirements/validation_rules/output_format @ v0.1.0) + Knowledge 4종(collection_sqls/hints_reference/dictionary_views/tuning_cases) Claude.ai Project 1차 동기화 | nawhizz |

## 사용 규칙

1. 동기화를 수행한 직후 위 표에 한 행을 추가한다.
2. `Git 해시`는 동기화 시점의 `git rev-parse --short HEAD` 값을 기재한다.
3. `태그`는 해당 동기화에 부여한 릴리즈 태그(`v0.1.0` 등)를 기재한다. 비공식 동기화는 `-`로 표기.
4. `변경 요약`은 시스템 프롬프트와 Knowledge 양쪽의 주요 변경을 1~2줄로 작성한다.
5. 동기화를 일으킨 커밋 메시지에 `[SYNC-REQUIRED]` 태그가 포함되어 있는지 확인한다.
