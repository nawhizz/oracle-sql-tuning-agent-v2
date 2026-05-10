# Claude.ai Project 동기화 절차

본 문서는 본 저장소(`source of truth`)의 자산을 **Claude.ai Project**(실행 환경)에 반영하는 수동 절차를 정의한다. PRD §14.5 를 따른다.

Claude.ai Project는 현재 API 기반 프로그램적 업데이트를 공식 지원하지 않으므로, 모든 단계는 수동이며 `docs/sync_log.md` 로 추적한다. 이 한계는 Stage 2 (자체 웹 UI) 이후 해소된다.

---

## A. 시스템 프롬프트 동기화 (4 단계)

### A-1. 빌드
```
python scripts/build_system_prompt.py
```
- 출력: `prompts/build/system.txt` 와 `prompts/build/system.md`
- 토큰 근사치를 확인하고 Claude.ai Project Custom Instructions 한도를 초과하지 않는지 점검한다.

### A-2. 복사
- `prompts/build/system.txt` 의 전체 내용을 클립보드에 복사한다.

### A-3. 붙여넣기
- Claude.ai 에 로그인 → 대상 Project 선택 → **Custom Instructions** 편집 모드 진입.
- 기존 내용을 모두 지우고, 복사한 텍스트를 붙여넣고 저장한다.

### A-4. 기록
- 본 저장소에서 `git rev-parse --short HEAD` 로 현재 해시를 얻는다.
- `docs/sync_log.md` 에 항목 추가(아래 양식 참조).
- 해당 동기화에 부여할 태그가 있으면 `git tag vX.Y.Z` 후 push.

---

## B. Knowledge 파일 동기화 (4 단계)

### B-1. 변경 식별
```
/sync-check
```
- 또는 직접 `git diff --name-only <last-sync-hash>..HEAD -- knowledge/`
- 변경된 `knowledge/*.md` 파일 목록을 얻는다.

### B-2. 기존 파일 삭제
- Claude.ai Project > **Project Knowledge** 화면에서 변경 대상 파일을 삭제한다.
- 파일명 일치 시 **반드시 삭제 후 재업로드** (덮어쓰기 미지원).

### B-3. 재업로드
- 본 저장소의 최신 `knowledge/<file>.md` 를 업로드한다.
- 추적 용이성을 위해 파일명에 버전 해시 접미어를 붙일 수 있다(선택, 예: `collection_sqls_v3.md`). 단, 사용 시 모든 Knowledge 파일에 일관 적용.

### B-4. 검증
- Claude.ai Project 의 새 대화에서 시범 질의로 Knowledge 검색이 동작하는지 확인.
- 예: "DBMS_XPLAN.DISPLAY_CURSOR 사용 SQL 알려줘" → `collection_sqls.md` 의 A.2 섹션을 인용해야 함.

---

## C. `docs/sync_log.md` 양식

매 동기화마다 다음 표에 한 행을 추가한다.

```markdown
| 일시 | Git 해시 | 태그 | 변경 요약 | 담당 |
|------|----------|------|-----------|------|
| 2026-05-10 18:30 | a1b2c3d | v0.1.0 | 초기 시스템 프롬프트 + Knowledge 4종 | nawhizz |
```

규칙:
- `일시` — 로컬 시간, 분 단위까지.
- `Git 해시` — `git rev-parse --short HEAD` 결과.
- `태그` — 정식 릴리즈 동기화는 `vX.Y.Z`, 임시 동기화는 `-`.
- `변경 요약` — 시스템 프롬프트와 Knowledge 양쪽의 핵심 변경 1~2줄.
- 동기화를 일으킨 커밋의 메시지에 `[SYNC-REQUIRED]` 태그가 포함되어 있는지 확인.

---

## D. `[SYNC-REQUIRED]` 커밋 태그

다음에 해당하는 커밋은 메시지에 `[SYNC-REQUIRED]` 태그를 붙인다.

| 변경 영역 | SYNC-REQUIRED 필요? |
|-----------|---------------------|
| `prompts/modules/*.md` 의 의미 변경 | 예 |
| `prompts/modules/*.md` 의 단순 오타·서식 정리 | 선택 (다음 정식 동기화에 합류) |
| `knowledge/*.md` 의 어떤 변경 | 예 |
| `tests/`, `scripts/`, `docs/`, `.claude/commands/`, README, CLAUDE.md | 아니오 |

PR 머지 전 체크리스트:
- [ ] 회귀 테스트 통과 (`/run-tests`)
- [ ] `prompts/CHANGELOG.md` 업데이트
- [ ] `[SYNC-REQUIRED]` 태그 부착 여부 결정
- [ ] 동기화 후 `docs/sync_log.md` 항목 추가

---

## E. 롤백 절차

특정 태그로 되돌릴 때:

1. `git checkout vX.Y.Z` 로 임시 작업 트리 확보.
2. `python scripts/build_system_prompt.py` 로 해당 시점 빌드.
3. Claude.ai Project Custom Instructions 와 Knowledge 를 해당 시점 자산으로 교체 (A·B 절차 반복).
4. `docs/sync_log.md` 에 롤백 사실 기록 (태그 컬럼은 `rollback->vX.Y.Z`).
5. main 브랜치 작업은 별도 hotfix 브랜치에서 재개.

---

## F. 자주 묻는 질문

**Q. Project Knowledge 의 파일을 자동 동기화할 수 있나?**
A. 현재 Claude.ai Project 는 공식 API 미제공. 자체 웹 UI(Stage 2) 단계에서 Anthropic API 의 `system` 파라미터와 RAG/컨텍스트 주입으로 자동화한다.

**Q. Custom Instructions 토큰 한도를 초과하면?**
A. `prompts/modules/` 의 비핵심 예시·중복 표현을 제거하거나, 일부 가이드를 Knowledge 로 이동. 빌드 시 토큰 근사치 출력으로 점검.

**Q. 회귀 테스트는 어떤 환경에서 도는가?**
A. Anthropic Claude API. 본 저장소의 `tests/run_tests.py` 가 `prompts/build/system.txt` 를 system 파라미터로 전달하므로 Claude.ai Project 동작과 약간의 차이가 있을 수 있다(PRD §14.9). 정식 릴리즈 전 Claude.ai Project 에서도 핵심 시나리오 1~2개를 수동 재검증한다.
