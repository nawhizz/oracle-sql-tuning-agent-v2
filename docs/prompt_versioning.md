# 프롬프트 버전 관리 규칙

본 문서는 `prompts/` 와 `knowledge/` 자산의 버전 관리 정책을 정의한다. PRD §14.7 을 따른다.

## 1. 브랜치 전략

- **`main`** — 안정 버전. 항상 회귀 테스트 통과 상태를 유지.
- **`feature/<topic>`** — 기능 단위 작업 브랜치. 프롬프트·Knowledge·테스트 변경을 함께 묶음.
- **`exp/<topic>`** — 프롬프트 A/B 실험용. 머지 의도 없이 비교 검증 용도.
- **`hotfix/<topic>`** — 운영 중 발견된 결함의 긴급 수정.

PR 머지 조건:
- [ ] 회귀 테스트 (`tests/run_tests.py`) 전체 통과
- [ ] `prompts/CHANGELOG.md` 업데이트 (의미 변경 시)
- [ ] `[SYNC-REQUIRED]` 태그 판단 완료 (`docs/sync_to_claude_ai.md` §D)

## 2. 커밋 메시지 컨벤션

prefix 로 변경 영역을 명시한다.

| Prefix | 영역 |
|--------|------|
| `prompt:` | `prompts/modules/`, `prompts/CHANGELOG.md` |
| `knowledge:` | `knowledge/*.md` |
| `test:` | `tests/scenarios/`, `tests/run_tests.py`, `tests/sql_validator.py` |
| `docs:` | `docs/`, `README.md`, `CLAUDE.md` |
| `tooling:` | `scripts/`, `.claude/commands/`, `.gitignore`, `requirements.txt`, `.env.example` |

예시:
```
prompt: 히스토그램 확인 요청을 선택 → 필수로 승격 [SYNC-REQUIRED]

영향 시나리오: 006_two_table_skewed_card

근거: 히스토그램 부재가 잘못된 조인 방식 선택의 핵심 원인이 되는 사례
(tuning_cases.md 사례 4) 가 자주 발생함.
```

머리줄 포맷: `<prefix>: <한국어 한 줄 요약> [선택 태그]`
본문: 변경 사유와 영향을 한국어로 기술. 외부 참조(시나리오 ID, 사례 번호) 권장.

## 3. 릴리즈 태깅

Claude.ai Project 동기화 시점마다 `vX.Y.Z` 태그를 부여한다.

| 자릿수 | 의미 |
|--------|------|
| Major (`X`) | 시스템 프롬프트의 상태 머신·출력 포맷 등 **에이전트 동작 자체**의 큰 변경 |
| Minor (`Y`) | 새 정보 카테고리, 새 검증 규칙, 새 Knowledge 파일 등 **기능 추가** |
| Patch (`Z`) | 오타·서식·작은 문구 정리 등 **의미 동일** 변경 |

태그 푸시:
```
git tag -a v0.2.0 -m "v0.2.0: 히스토그램 필수 승격, 011 시나리오 추가"
git push origin v0.2.0
```

## 4. CHANGELOG 운영

`prompts/CHANGELOG.md` 에 릴리즈별로 다음 항목을 누적한다.

```markdown
## v0.2.0 — 2026-06-01 (a1b2c3d)

### 변경
- prompt: 히스토그램 확인 요청을 선택 → 필수로 승격
- knowledge: collection_sqls.md 의 C.2 히스토그램 섹션 보강

### 영향 시나리오
- 006_two_table_skewed_card (재검증 필요)
- 011_loop_inconsistency

### 동기화
- [SYNC-REQUIRED]: 예 → docs/sync_log.md 항목 a1b2c3d
```

`v0.X.0 백로그` 섹션은 다음 릴리즈에서 처리할 미통과 항목·관찰을 누적한다. 릴리즈 시 백로그를 본문으로 이동.

## 5. 실험 (A/B) 운영

프롬프트 변경의 효과가 불확실할 때:

1. `exp/<topic>` 브랜치에서 변경.
2. `python tests/run_tests.py --filter <영향 시나리오>` 로 비교.
3. 결과를 `tests/results/exp_<topic>.md` 로 저장.
4. 채택 시 `feature/<topic>` 으로 옮겨 정식 PR. 폐기 시 브랜치 삭제 + 결과 파일은 `tests/results/archive/` 로 이동.

## 6. 롤백 정책

장애·퇴행 발견 시:

- **즉시 대응**: Claude.ai Project Custom Instructions 를 직전 안정 태그(`vX.Y-1`)의 빌드 산출물로 교체. (`docs/sync_to_claude_ai.md` §E 참조)
- **사후 분석**: `tests/scenarios/` 에 회귀 케이스 추가 → `prompts/CHANGELOG.md` 백로그에 기록 → 다음 정식 릴리즈에서 해소.

롤백 자체는 Git 의 `git revert` 또는 `git checkout <tag>` + 새 커밋 으로 수행한다. **`--force` 푸시는 금지**.
