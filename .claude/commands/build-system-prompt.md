---
description: prompts/modules/*.md 를 조립해 prompts/build/system.txt 를 생성한다.
---

다음 명령을 실행해 시스템 프롬프트를 빌드한다.

```
python scripts/build_system_prompt.py
```

빌드가 완료되면 다음을 사용자에게 보고한다.
- 산출물 경로: `prompts/build/system.md`, `prompts/build/system.txt`
- 토큰 수 근사치
- 각 모듈의 버전
- 다음 동작 권고: "Claude.ai Project Custom Instructions 동기화가 필요하면 `/sync-check` 를 실행하세요."

빌드 실패 시 누락된 모듈명 또는 헤더 형식 오류 메시지를 그대로 사용자에게 전달한다.
