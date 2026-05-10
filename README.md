# Oracle SQL 튜닝 에이전트

DB 미접속 환경에서 사용자 제공 정보를 기반으로 동작하는 대화형 Oracle SQL 튜닝 에이전트.

## 저장소 성격

- 본 저장소는 **Claude.ai Project로 배포되는 SQL 튜닝 에이전트의 source of truth**이다.
- Claude.ai Project는 실행 환경일 뿐이며, 시스템 프롬프트와 Knowledge 자산의 원본은 모두 이곳에서 Git으로 관리된다.
- 자세한 배경은 `docs/oracle_sql_tuning_agent_prd_v1.4.docx`(PRD v1.4)을 참조한다.

## 디렉토리 구조

```
oracle-sql-tuning-agent-v2/
├── CLAUDE.md                   # Claude Code 개발 규칙
├── README.md                   # 본 문서
├── requirements.txt            # 빌드/테스트 스크립트 의존성
├── .env.example                # 환경 변수 자리표시자
│
├── prompts/
│   ├── system.md               # (T07 빌드 산출물의 메인 텍스트는 prompts/build/ 에 생성)
│   ├── modules/                # 모듈식 시스템 프롬프트 원본
│   │   ├── role.md
│   │   ├── state_machine.md
│   │   ├── info_requirements.md
│   │   ├── validation_rules.md
│   │   └── output_format.md
│   └── CHANGELOG.md            # 프롬프트 변경 이력
│
├── knowledge/                  # Project Knowledge 업로드용 자산
│   ├── collection_sqls.md
│   ├── hints_reference.md
│   ├── dictionary_views.md
│   └── tuning_cases.md
│
├── tests/
│   ├── scenarios/              # YAML 회귀 테스트 시나리오
│   ├── run_tests.py            # 자동 평가 스크립트
│   ├── sql_validator.py        # 수집 SQL 정적 문법 검증
│   └── results/                # 회귀 테스트 결과(.gitignore)
│
├── scripts/
│   └── build_system_prompt.py  # modules/ → 단일 시스템 프롬프트 빌드
│
├── docs/
│   ├── oracle_sql_tuning_agent_prd_v1.4.docx
│   ├── sync_to_claude_ai.md    # Claude.ai Project 수동 동기화 절차
│   ├── sync_log.md             # 동기화 기록
│   └── prompt_versioning.md    # 브랜치/커밋/태그 규칙
│
└── .claude/commands/           # Claude Code 슬래시 커맨드 정의
```

## 빠른 시작

```bash
# 1) 가상환경 및 의존성
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2) 환경 변수
cp .env.example .env
# .env 에 ANTHROPIC_API_KEY 입력

# 3) 시스템 프롬프트 빌드
python scripts/build_system_prompt.py

# 4) 회귀 테스트 실행
python tests/run_tests.py
```

## Claude.ai Project 동기화

빌드된 시스템 프롬프트와 Knowledge 파일을 Claude.ai Project에 반영하는 절차는 `docs/sync_to_claude_ai.md`를 따른다. 동기화 시점마다 `docs/sync_log.md`에 일시·Git 해시·태그·요약을 기록한다.

## 라이선스 / 보안

- 민감한 회사 데이터, 실 운영 SQL은 어떠한 디렉토리에도 포함하지 않는다.
- 시나리오와 Knowledge에 사용되는 스키마는 모두 마스킹된 공개 도메인(예: ORDERS, CUSTOMERS, ORDER_ITEMS)이다.
