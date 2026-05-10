---
description: 회귀 테스트 시나리오를 Anthropic Claude API로 실행하고 통과율을 보고한다.
---

다음 단계를 순서대로 수행한다.

1. `prompts/build/system.txt` 가 존재하는지 확인. 없으면 먼저 `python scripts/build_system_prompt.py` 를 실행한다.
2. 사용자가 인자로 시나리오 ID를 제공했다면 해당 ID만, 아니면 전체를 실행한다.
   ```
   python tests/run_tests.py [--filter <id1,id2,...>] [--model <model_id>] [--judge]
   ```
3. 실행 후 다음을 보고한다.
   - 시나리오별 pass/fail 표
   - 카테고리별 통과율 (must_request / must_include_section / forbidden_phrases / sql_validator)
   - 결과 파일 경로 (`tests/results/<timestamp>.json`, `tests/results/<timestamp>.md`)
   - 실패가 있으면 우선순위 상위 3개 시나리오의 실패 사유 인용

`ANTHROPIC_API_KEY` 가 설정되지 않았으면 `.env` 작성을 안내하고 중단한다.
