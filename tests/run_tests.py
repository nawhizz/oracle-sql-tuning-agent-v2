#!/usr/bin/env python3
"""회귀 테스트 자동 평가 스크립트.

빌드된 시스템 프롬프트(prompts/build/system.txt) 와 knowledge/*.md 를 컨텍스트로
Anthropic Claude API 를 호출, 시나리오 user_turns 를 순차 전송하고 expected 규칙으로
자동 채점한다.

사용법:
    python tests/run_tests.py
    python tests/run_tests.py --filter 001,005
    python tests/run_tests.py --model claude-sonnet-4-6 --judge --cache

산출물:
    tests/results/<ISO>.json   — 시나리오별 raw 결과
    tests/results/<ISO>.md     — 사람이 읽기 좋은 리포트

ANTHROPIC_API_KEY 가 설정되지 않은 경우 안내 후 종료(코드 2).
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import subprocess
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
SYSTEM_PROMPT_PATH = ROOT / "prompts" / "build" / "system.txt"
KNOWLEDGE_DIR = ROOT / "knowledge"
SCENARIOS_DIR = ROOT / "tests" / "scenarios"
RESULTS_DIR = ROOT / "tests" / "results"
CACHE_DIR = RESULTS_DIR / ".cache"

DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
DEFAULT_MAX_TOKENS = 4096

sys.path.insert(0, str(ROOT / "tests"))
from sql_validator import extract_sql_blocks, validate_sql  # noqa: E402


@dataclass
class TurnResult:
    turn: int
    user_message: str
    assistant_text: str
    failures: list[str] = field(default_factory=list)
    sql_blocks: list[str] = field(default_factory=list)
    sql_validator_errors: list[str] = field(default_factory=list)


@dataclass
class ScenarioResult:
    scenario_id: str
    title: str
    passed: bool
    turns: list[TurnResult] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    sql_validator_pass: int = 0
    sql_validator_fail: int = 0


def ensure_system_prompt() -> str:
    if not SYSTEM_PROMPT_PATH.is_file():
        print("[run_tests] system.txt 가 없어 빌드합니다...")
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "build_system_prompt.py")],
            check=True,
            cwd=ROOT,
        )
    return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")


def load_knowledge() -> str:
    parts: list[str] = []
    for path in sorted(KNOWLEDGE_DIR.glob("*.md")):
        parts.append(f"\n\n========== Project Knowledge: {path.name} ==========\n\n")
        parts.append(path.read_text(encoding="utf-8"))
    return "".join(parts).strip()


def load_scenarios(scenario_filter: list[str] | None) -> list[dict[str, Any]]:
    files = sorted(SCENARIOS_DIR.glob("*.yaml"))
    scenarios: list[dict[str, Any]] = []
    for f in files:
        data = yaml.safe_load(f.read_text(encoding="utf-8"))
        sid = str(data.get("id"))
        if scenario_filter and sid not in scenario_filter:
            continue
        data["__path"] = str(f)
        scenarios.append(data)
    return scenarios


def system_prompt_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def cache_key(prompt_hash: str, scenario_id: str, turn: int, model: str) -> Path:
    return CACHE_DIR / f"{prompt_hash}_{model.replace('/', '-')}_{scenario_id}_turn{turn}.json"


def call_claude(
    client: Any,
    system: str,
    messages: list[dict[str, str]],
    model: str,
    max_tokens: int,
) -> str:
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=messages,
    )
    parts = []
    for block in resp.content:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "".join(parts).strip()


def evaluate_turn(turn: dict[str, Any], assistant_text: str) -> list[str]:
    """시나리오 turn.expected 규칙을 평가하고 실패 사유 목록을 반환."""
    failures: list[str] = []
    expected = turn.get("expected") or {}

    text_lower = assistant_text  # 한글·SQL 키워드 모두 대소문자 보존이 의미가 있어 lower 미적용

    # must_request — 첫 정보 요청 또는 재요청에서 등장해야 할 키워드
    for kw in expected.get("must_request", []) or []:
        if kw not in text_lower:
            failures.append(f"must_request 누락: '{kw}'")

    # must_include_section — 섹션 헤더가 정확한 문자열로 등장
    for sec in expected.get("must_include_section", []) or []:
        if sec not in text_lower:
            failures.append(f"must_include_section 누락: '{sec}'")

    # must_include_phrase — 의미 매칭이 아닌 단순 부분 문자열
    for ph in expected.get("must_include_phrase", []) or []:
        if ph not in text_lower:
            failures.append(f"must_include_phrase 누락: '{ph}'")

    # forbidden_phrases — 등장하면 실패
    for ph in expected.get("forbidden_phrases", []) or []:
        if ph in text_lower:
            failures.append(f"forbidden_phrases 등장: '{ph}'")

    return failures


def llm_judge(
    client: Any,
    judge_model: str,
    scenario_title: str,
    user_message: str,
    assistant_text: str,
    expected: dict[str, Any],
) -> tuple[bool, str]:
    """위양성/위음성 보완용 LLM-as-a-judge. yes/no + 근거 한 줄 반환."""
    prompt = (
        "다음 시나리오 turn 의 응답이 expected 규칙을 의미적으로 충족하는지 "
        "JSON 객체 한 줄로 답하세요.\n"
        '응답 형식: {"satisfied": true|false, "reason": "한 문장"}\n\n'
        f"시나리오: {scenario_title}\n"
        f"사용자 메시지:\n{user_message}\n\n"
        f"에이전트 응답:\n{assistant_text}\n\n"
        f"expected:\n{json.dumps(expected, ensure_ascii=False)}\n"
    )
    text = call_claude(
        client,
        system="당신은 회귀 테스트 채점자입니다. JSON 한 줄만 출력합니다.",
        messages=[{"role": "user", "content": prompt}],
        model=judge_model,
        max_tokens=400,
    )
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return False, f"judge 응답 파싱 실패: {text[:120]}"
    try:
        data = json.loads(m.group(0))
        return bool(data.get("satisfied")), str(data.get("reason", ""))[:200]
    except json.JSONDecodeError as e:
        return False, f"judge JSON 디코드 실패: {e}"


def run_scenario(
    client: Any,
    scenario: dict[str, Any],
    system_prompt: str,
    knowledge: str,
    model: str,
    use_cache: bool,
    judge_model: str | None,
) -> ScenarioResult:
    sid = str(scenario["id"])
    title = scenario.get("title", "")
    result = ScenarioResult(scenario_id=sid, title=title, passed=True)

    prompt_hash = system_prompt_hash(system_prompt + "\n" + knowledge)
    messages: list[dict[str, str]] = []

    for turn in scenario.get("user_turns", []):
        turn_no = int(turn.get("turn", 0))
        user_msg = turn["message"]
        # 첫 턴에 PROJECT_KNOWLEDGE 주입
        if turn_no == 1:
            user_msg_full = (
                f"<PROJECT_KNOWLEDGE>\n{knowledge}\n</PROJECT_KNOWLEDGE>\n\n{user_msg}"
            )
        else:
            user_msg_full = user_msg

        messages.append({"role": "user", "content": user_msg_full})

        cache_path = cache_key(prompt_hash, sid, turn_no, model)
        assistant_text: str | None = None
        if use_cache and cache_path.is_file():
            assistant_text = json.loads(cache_path.read_text(encoding="utf-8")).get("text")

        if assistant_text is None:
            assistant_text = call_claude(
                client,
                system=system_prompt,
                messages=messages,
                model=model,
                max_tokens=DEFAULT_MAX_TOKENS,
            )
            if use_cache:
                CACHE_DIR.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(
                    json.dumps({"text": assistant_text}, ensure_ascii=False),
                    encoding="utf-8",
                )

        messages.append({"role": "assistant", "content": assistant_text})

        # 평가
        failures = evaluate_turn(turn, assistant_text)

        # SQL validator
        sql_blocks = extract_sql_blocks(assistant_text)
        sql_errors: list[str] = []
        for blk in sql_blocks:
            v = validate_sql(blk)
            if v.passed:
                result.sql_validator_pass += 1
            else:
                result.sql_validator_fail += 1
                sql_errors.extend(v.errors)
                failures.append(f"SQL validator 실패: {'; '.join(v.errors)[:200]}")

        # LLM-as-a-judge (옵션)
        if judge_model and failures and turn.get("expected"):
            ok, reason = llm_judge(
                client,
                judge_model,
                title,
                user_msg,
                assistant_text,
                turn["expected"],
            )
            if ok:
                # 의미적으로 충족 — 키워드 누락만으로 발생한 실패를 완화
                only_keyword_failures = all(
                    f.startswith("must_") or f.startswith("forbidden_")
                    for f in failures
                )
                if only_keyword_failures and not sql_errors:
                    failures = []
                else:
                    failures.append(f"judge 의미 충족({reason}) — 그러나 SQL/구조 실패 잔존")
            else:
                failures.append(f"judge 의미 미충족: {reason}")

        result.turns.append(
            TurnResult(
                turn=turn_no,
                user_message=user_msg,
                assistant_text=assistant_text,
                failures=failures,
                sql_blocks=sql_blocks,
                sql_validator_errors=sql_errors,
            )
        )
        if failures:
            result.passed = False
            result.failures.extend([f"turn {turn_no}: {f}" for f in failures])

    return result


def write_reports(results: list[ScenarioResult], timestamp: str) -> tuple[Path, Path]:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = RESULTS_DIR / f"{timestamp}.json"
    md_path = RESULTS_DIR / f"{timestamp}.md"

    json_payload = {
        "timestamp": timestamp,
        "summary": {
            "total": len(results),
            "passed": sum(1 for r in results if r.passed),
            "failed": sum(1 for r in results if not r.passed),
            "sql_pass": sum(r.sql_validator_pass for r in results),
            "sql_fail": sum(r.sql_validator_fail for r in results),
        },
        "scenarios": [asdict(r) for r in results],
    }
    json_path.write_text(json.dumps(json_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# 회귀 테스트 결과 — {timestamp}",
        "",
        "## 요약",
        "",
        f"- 시나리오: {json_payload['summary']['passed']} / {json_payload['summary']['total']} 통과",
        f"- SQL validator: {json_payload['summary']['sql_pass']} pass · {json_payload['summary']['sql_fail']} fail",
        "",
        "## 시나리오별",
        "",
        "| ID | 제목 | 통과 | 실패 사유 (요약) |",
        "|----|------|------|------------------|",
    ]
    for r in results:
        status = "✅" if r.passed else "❌"
        first_fail = r.failures[0] if r.failures else ""
        lines.append(f"| {r.scenario_id} | {r.title} | {status} | {first_fail[:90]} |")
    lines.append("")
    for r in results:
        if r.passed:
            continue
        lines.append(f"### {r.scenario_id} — {r.title}")
        for f in r.failures[:10]:
            lines.append(f"- {f}")
        lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")

    return json_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser(description="회귀 테스트 자동 평가")
    parser.add_argument("--filter", help="콤마 구분 시나리오 ID (예: 001,005,011)")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"기본 {DEFAULT_MODEL}")
    parser.add_argument("--judge", action="store_true", help="LLM-as-a-judge 보완 채점 활성화")
    parser.add_argument("--judge-model", default=None, help="judge 모델(기본: --model 과 동일)")
    parser.add_argument("--cache", action="store_true", help="응답 캐시 사용/저장")
    parser.add_argument("--dry-run", action="store_true", help="API 호출 없이 시나리오 로드만")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not args.dry_run and not api_key:
        print(
            "[run_tests] ANTHROPIC_API_KEY 가 설정되지 않았습니다.\n"
            "  1) cp .env.example .env\n"
            "  2) .env 에 ANTHROPIC_API_KEY=... 입력\n",
            file=sys.stderr,
        )
        return 2

    scenario_filter = None
    if args.filter:
        scenario_filter = [s.strip() for s in args.filter.split(",") if s.strip()]
    scenarios = load_scenarios(scenario_filter)
    if not scenarios:
        print("[run_tests] 실행할 시나리오가 없습니다.", file=sys.stderr)
        return 1
    print(f"[run_tests] 시나리오 {len(scenarios)} 건 로드")

    if args.dry_run:
        for s in scenarios:
            print(f"  - {s['id']} {s.get('title','')}")
        return 0

    system_prompt = ensure_system_prompt()
    knowledge = load_knowledge()
    print(f"[run_tests] system.txt 로드 ({len(system_prompt)}자), knowledge {len(knowledge)}자")

    # 지연 import: 의존성 부재 환경에서도 --dry-run 동작 가능
    import anthropic  # type: ignore
    client = anthropic.Anthropic(api_key=api_key)
    judge_model = (args.judge_model or args.model) if args.judge else None

    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    results: list[ScenarioResult] = []
    for s in scenarios:
        sid = str(s["id"])
        print(f"[run_tests] {sid} 실행...")
        r = run_scenario(
            client=client,
            scenario=s,
            system_prompt=system_prompt,
            knowledge=knowledge,
            model=args.model,
            use_cache=args.cache,
            judge_model=judge_model,
        )
        status = "PASS" if r.passed else "FAIL"
        print(f"  → {status} ({len(r.failures)} failures, sql {r.sql_validator_pass}/{r.sql_validator_pass + r.sql_validator_fail})")
        results.append(r)

    json_path, md_path = write_reports(results, timestamp)
    pass_n = sum(1 for r in results if r.passed)
    print(f"\n[결과] {pass_n}/{len(results)} 통과")
    print(f"  JSON: {json_path.relative_to(ROOT)}")
    print(f"  MD  : {md_path.relative_to(ROOT)}")

    return 0 if pass_n == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
