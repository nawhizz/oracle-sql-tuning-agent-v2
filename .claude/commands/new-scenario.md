---
description: tests/scenarios/ 에 신규 회귀 테스트 시나리오 YAML 템플릿을 생성한다.
---

사용자가 인자로 다음 3개를 제공한다.
- `id` — 3자리 숫자 (예: `012`)
- `slug` — 영문 짧은 식별자 (예: `multi_join_with_view`)
- `intent` — 한국어 한 문장 의도 (예: "인라인 뷰가 포함된 3-테이블 조인에서 정보 식별 정확도 검증")

다음 절차를 수행한다.

1. `tests/scenarios/{id}_{slug}.yaml` 가 이미 존재하면 중단하고 알림.
2. 다음 템플릿으로 파일을 생성한다.

```yaml
id: <id>
title: "<한 줄 제목>"
intent: "<intent 인자값>"
db_version: "19c"

input_sql: |
  -- 마스킹된 공개 도메인 SQL만 사용 (ORDERS/CUSTOMERS/PRODUCTS/ORDER_ITEMS/EMPLOYEES/DEPARTMENTS)
  SELECT ...
  FROM   ...
  WHERE  ...;

user_turns:
  - turn: 1
    message: |
      위 SQL 튜닝해 주세요.
    expected:
      must_request:
        - "DB 버전"
        - "테이블 통계"
        - "인덱스"
      must_include_phrase:
        - "복사해서"
      forbidden_phrases:
        - "경험상"
        - "일반적으로"
        - "보통은"
        - "아마도"
        - "대체로"

  - turn: 2
    message: |
      [수집 결과 붙여넣기]
    expected:
      must_include_section:
        - "[진단 요약]"
        - "[가설]"
        - "[튜닝 대안]"
        - "[튜닝된 SQL — 권장안 기준]"
        - "[검증 방법]"
      forbidden_phrases:
        - "경험상"
        - "일반적으로"

pass_criteria:
  - all_must_request_satisfied
  - all_must_include_section_present
  - no_forbidden_phrases
```

3. 사용자에게 파일 경로와 다음 단계("재요청 루프 시나리오면 user_turns 를 4개 이상으로 확장하세요") 를 안내한다.
