#!/usr/bin/env python3
"""prompts/modules/*.md 를 정해진 순서로 조립해 단일 시스템 프롬프트 텍스트로 빌드한다.

산출물:
  - prompts/build/system.md  : 모듈 헤더 주석을 보존한 마크다운
  - prompts/build/system.txt : Claude.ai Project Custom Instructions 붙여넣기용 단일 텍스트

사용법:
  python scripts/build_system_prompt.py
  python scripts/build_system_prompt.py --output-dir prompts/releases/v0.1.0
"""

from __future__ import annotations

import argparse
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODULES_DIR = ROOT / "prompts" / "modules"
DEFAULT_OUTPUT_DIR = ROOT / "prompts" / "build"

MODULE_ORDER = [
    "role",
    "state_machine",
    "info_requirements",
    "validation_rules",
    "output_format",
]

MODULE_HEADER_RE = re.compile(r"^<!--\s*module:\s*(?P<name>\w+)\s*\|\s*version:\s*(?P<version>[\w.\-]+)\s*-->\s*$")


def git_short_hash() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def approx_token_count(text: str) -> int:
    """한글 1.5자/토큰, 그 외 4자/토큰 휴리스틱."""
    korean = len(re.findall(r"[가-힣]", text))
    other = len(text) - korean
    return int(korean / 1.5 + other / 4)


def load_module(name: str) -> tuple[str, str]:
    path = MODULES_DIR / f"{name}.md"
    if not path.is_file():
        raise FileNotFoundError(f"필수 모듈 파일이 없습니다: {path}")
    raw = path.read_text(encoding="utf-8")
    lines = raw.splitlines()
    version = "0.0.0"
    body_lines: list[str] = []
    header_seen = False
    for line in lines:
        if not header_seen:
            m = MODULE_HEADER_RE.match(line)
            if m:
                if m.group("name") != name:
                    raise ValueError(
                        f"{path} 헤더의 모듈명이 일치하지 않습니다: 기대 {name}, 실제 {m.group('name')}"
                    )
                version = m.group("version")
                header_seen = True
                continue
            # 헤더가 첫 줄이 아니면 빈 줄까지 통과
            if line.strip() == "":
                continue
        body_lines.append(line)
    if not header_seen:
        raise ValueError(f"{path} 에 모듈 헤더 주석이 없습니다 (예: <!-- module: {name} | version: 0.1.0 -->)")
    body = "\n".join(body_lines).strip()
    return version, body


def build(output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    git_hash = git_short_hash()

    sections_md: list[str] = []
    sections_txt: list[str] = []
    versions: dict[str, str] = {}
    for name in MODULE_ORDER:
        version, body = load_module(name)
        versions[name] = version
        sections_md.append(f"<!-- ===== module: {name} | version: {version} ===== -->\n\n{body}\n")
        # txt 버전은 메타 주석을 단순 헤더로 변환
        sections_txt.append(f"========== {name} (v{version}) ==========\n\n{body}\n")

    meta_md = (
        "<!--\n"
        f"build: oracle-sql-tuning-agent system prompt\n"
        f"timestamp: {timestamp}\n"
        f"git: {git_hash}\n"
        f"modules: {', '.join(f'{n}@{v}' for n, v in versions.items())}\n"
        "-->\n\n"
    )
    meta_txt = (
        "/* ============================================================\n"
        f"   Oracle SQL 튜닝 에이전트 — 시스템 프롬프트 (빌드 산출물)\n"
        f"   timestamp : {timestamp}\n"
        f"   git       : {git_hash}\n"
        f"   modules   : {', '.join(f'{n}@{v}' for n, v in versions.items())}\n"
        "   ============================================================ */\n\n"
    )

    md_text = meta_md + "\n".join(sections_md)
    txt_text = meta_txt + "\n".join(sections_txt)

    md_path = output_dir / "system.md"
    txt_path = output_dir / "system.txt"
    md_path.write_text(md_text, encoding="utf-8")
    txt_path.write_text(txt_text, encoding="utf-8")

    # 출력 디렉토리에 .gitignore 자동 배치 (build 산출물은 버전관리 제외)
    if output_dir.resolve() == DEFAULT_OUTPUT_DIR.resolve():
        (output_dir / ".gitignore").write_text("*\n!.gitignore\n", encoding="utf-8")

    return {
        "md_path": md_path,
        "txt_path": txt_path,
        "tokens_md": approx_token_count(md_text),
        "tokens_txt": approx_token_count(txt_text),
        "git_hash": git_hash,
        "timestamp": timestamp,
        "versions": versions,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="시스템 프롬프트 모듈 빌드")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="빌드 산출물 디렉토리 (기본: prompts/build)",
    )
    args = parser.parse_args()

    result = build(args.output_dir.resolve())
    print(f"[빌드 완료] {result['timestamp']} (git {result['git_hash']})")
    print(f"  - {result['md_path'].relative_to(ROOT)}  (~{result['tokens_md']} tokens)")
    print(f"  - {result['txt_path'].relative_to(ROOT)}  (~{result['tokens_txt']} tokens)")
    print("  - 모듈 버전:")
    for name, version in result["versions"].items():
        print(f"      {name:<22} v{version}")


if __name__ == "__main__":
    main()
