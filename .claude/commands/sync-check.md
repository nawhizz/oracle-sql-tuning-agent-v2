---
description: 마지막 동기화 이후 변경된 prompts/, knowledge/ 파일을 식별해 동기화 필요 여부를 보고한다.
---

다음을 수행한다.

1. `docs/sync_log.md` 의 마지막 동기화 항목에서 Git 해시(`<sync-hash>`)를 추출한다. 항목이 없으면 첫 동기화임을 안내하고 `git log --oneline -- prompts/ knowledge/` 의 최근 5개를 보여준다.
2. `git diff --name-only <sync-hash>..HEAD -- prompts/ knowledge/` 로 변경 파일 목록을 얻는다.
3. 결과를 다음 형식으로 보고한다.

   ```
   [마지막 동기화] <sync-date> · <sync-hash> · 태그 <tag>
   [현재] <current-date> · <current-hash>

   변경된 파일:
     prompts/modules/role.md
     knowledge/collection_sqls.md

   동기화 필요 항목:
     - Custom Instructions 재빌드 및 붙여넣기 (prompts/ 변경 있음 → /build-system-prompt 실행)
     - Project Knowledge 재업로드 (knowledge/ 변경 있음)

   다음 단계: docs/sync_to_claude_ai.md 절차 수행 후 docs/sync_log.md 에 항목 추가
   ```

4. 변경이 없으면 "동기화 불필요" 로 보고하고 종료.

이 명령은 동기화를 수행하지 않으며, **수행 여부 판단**만을 돕는다.
