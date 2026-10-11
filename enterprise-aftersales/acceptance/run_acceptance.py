#!/usr/bin/env python3
"""Run and score the enterprise after-sales Top20 acceptance suite."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

REFUSAL_MARKERS = (
    "知识库未覆盖",
    "知识库中没有",
    "没有足够依据",
    "暂无相关资料",
    "无法根据现有",
    "不能确认",
    "无法确认",
    "不应猜测",
    "不能猜测",
)
ESCALATION_MARKERS = ("转人工", "联系人工", "转二线", "知识管理员", "补充文档")


@dataclass(frozen=True)
class Evaluation:
    case_id: str
    score: int
    content_ok: bool
    citation_ok: bool
    safe_refusal_ok: bool
    reasons: tuple[str, ...]


def load_suite(path: Path) -> dict[str, Any]:
    suite = json.loads(path.read_text(encoding="utf-8"))
    cases = suite.get("cases")
    if suite.get("schema_version") != 1 or not isinstance(cases, list) or not cases:
        raise ValueError("acceptance dataset must use schema_version=1 and contain cases")
    ids = [case.get("id") for case in cases]
    if any(not case_id for case_id in ids) or len(ids) != len(set(ids)):
        raise ValueError("acceptance case ids must be non-empty and unique")
    for case in cases:
        if case.get("mode") not in {"answer", "clarify", "refuse"}:
            raise ValueError(f"unsupported mode for {case['id']}: {case.get('mode')}")
        if case.get("mode") in {"answer", "clarify"} and not case.get("term_groups"):
            raise ValueError(f"{case['id']} requires term_groups")
        if case.get("require_citation") and not case.get("source_patterns"):
            raise ValueError(f"{case['id']} requires source_patterns")
    return suite


def _flatten_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for nested in value.values():
            yield from _flatten_strings(nested)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            yield from _flatten_strings(nested)


def _contains_any(text: str, terms: Iterable[str]) -> bool:
    folded = text.casefold()
    return any(str(term).casefold() in folded for term in terms)


def evaluate_case(case: dict[str, Any], response: dict[str, Any]) -> Evaluation:
    answer = str(response.get("answer") or response.get("content") or "").strip()
    references = response.get("references", response.get("reference", []))
    reference_text = "\n".join(_flatten_strings(references))
    reasons: list[str] = []
    mode = case["mode"]

    citation_ok = not case.get("require_citation", False) or _contains_any(reference_text, case.get("source_patterns", []))
    safe_refusal_ok = False

    if mode == "refuse":
        explicit_refusal = _contains_any(answer, REFUSAL_MARKERS)
        escalates = _contains_any(answer, ESCALATION_MARKERS)
        safe_refusal_ok = explicit_refusal
        if explicit_refusal:
            score = 2
        elif escalates:
            score = 1
            reasons.append("only escalated; did not explicitly state that evidence is missing")
        else:
            score = 0
            reasons.append("missing safe refusal")
        return Evaluation(case["id"], score, explicit_refusal, True, safe_refusal_ok, tuple(reasons))

    term_groups = case.get("term_groups", [])
    missing_groups = [group for group in term_groups if not _contains_any(answer, group)]
    content_ok = not missing_groups
    if not content_ok:
        reasons.append(f"missing {len(missing_groups)} expected term group(s)")
    if not citation_ok:
        reasons.append("missing expected source citation")

    if case.get("require_citation"):
        score = 2 if content_ok and citation_ok else 1 if content_ok or citation_ok else 0
    else:
        score = 2 if content_ok else 0
    return Evaluation(case["id"], score, content_ok, citation_ok, safe_refusal_ok, tuple(reasons))


def evaluate_suite(suite: dict[str, Any], responses: dict[str, dict[str, Any]]) -> dict[str, Any]:
    details = []
    for case in suite["cases"]:
        response = responses.get(case["id"], {})
        evaluation = evaluate_case(case, response)
        details.append(
            {
                "id": case["id"],
                "question": case["question"],
                "mode": case["mode"],
                "score": evaluation.score,
                "content_ok": evaluation.content_ok,
                "citation_ok": evaluation.citation_ok,
                "safe_refusal_ok": evaluation.safe_refusal_ok,
                "reasons": list(evaluation.reasons),
                "answer": response.get("answer", response.get("content", "")),
                "references": response.get("references", response.get("reference", [])),
            }
        )

    total = sum(item["score"] for item in details)
    citation_items = [item for item in details if next(case for case in suite["cases"] if case["id"] == item["id"]).get("require_citation")]
    refusal_items = [item for item in details if item["mode"] == "refuse"]
    all_citations = all(item["citation_ok"] for item in citation_items)
    all_refusals = all(item["safe_refusal_ok"] for item in refusal_items)
    passed = total >= int(suite["minimum_score"])
    if suite.get("require_all_citations", False):
        passed = passed and all_citations
    if suite.get("require_all_safe_refusals", False):
        passed = passed and all_refusals

    return {
        "suite_id": suite["suite_id"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "score": total,
        "max_score": len(details) * 2,
        "minimum_score": suite["minimum_score"],
        "all_required_citations_present": all_citations,
        "all_safe_refusals_passed": all_refusals,
        "passed": passed,
        "details": details,
    }


def load_responses(path: Path) -> dict[str, dict[str, Any]]:
    responses: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            item = json.loads(line)
            case_id = item.get("id")
            if not case_id:
                raise ValueError(f"response line {line_number} has no id")
            if case_id in responses:
                raise ValueError(f"duplicate response id: {case_id}")
            responses[case_id] = item
    return responses


def _post_json(base_url: str, api_key: str, path: str, payload: dict[str, Any], timeout: float) -> Any:
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/v1{path}",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            envelope = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"RAGFlow HTTP {exc.code}: {body[:500]}") from exc
    if envelope.get("code") != 0:
        raise RuntimeError(f"RAGFlow API error: {envelope.get('message', envelope)}")
    return envelope.get("data")


def run_live(suite: dict[str, Any], base_url: str, api_key: str, chat_id: str, timeout: float) -> dict[str, dict[str, Any]]:
    responses: dict[str, dict[str, Any]] = {}
    for case in suite["cases"]:
        session = _post_json(base_url, api_key, f"/chats/{chat_id}/sessions", {"name": f"Acceptance {case['id']}"}, timeout)
        result = _post_json(
            base_url,
            api_key,
            f"/chats/{chat_id}/completions",
            {"question": case["question"], "stream": False, "session_id": session["id"]},
            timeout,
        )
        reference = result.get("reference") or {}
        responses[case["id"]] = {
            "id": case["id"],
            "question": case["question"],
            "answer": result.get("answer", ""),
            "references": reference.get("chunks", reference) if isinstance(reference, dict) else reference,
        }
    return responses


def write_reports(report: dict[str, Any], responses: dict[str, dict[str, Any]], output_dir: Path) -> tuple[Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    json_path = output_dir / f"report-{stamp}.json"
    md_path = output_dir / f"report-{stamp}.md"
    response_path = output_dir / f"responses-{stamp}.jsonl"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with response_path.open("w", encoding="utf-8", newline="\n") as handle:
        for case_id in sorted(responses):
            handle.write(json.dumps(responses[case_id], ensure_ascii=False) + "\n")

    lines = [
        f"# {report['suite_id']} 验收报告",
        "",
        f"- 结果：{'通过' if report['passed'] else '未通过'}",
        f"- 得分：{report['score']}/{report['max_score']}（门槛 {report['minimum_score']}）",
        f"- 必需来源引用全部通过：{'是' if report['all_required_citations_present'] else '否'}",
        f"- 库外问题安全拒答全部通过：{'是' if report['all_safe_refusals_passed'] else '否'}",
        "",
        "| ID | 模式 | 得分 | 内容 | 来源 | 安全拒答 | 失败原因 |",
        "|---|---|---:|---|---|---|---|",
    ]
    for item in report["details"]:
        reasons = "；".join(item["reasons"]) or "-"
        lines.append(
            f"| {item['id']} | {item['mode']} | {item['score']}/2 | "
            f"{'✓' if item['content_ok'] else '✗'} | {'✓' if item['citation_ok'] else '✗'} | "
            f"{'✓' if item['safe_refusal_ok'] else ('-' if item['mode'] != 'refuse' else '✗')} | {reasons} |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path, response_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=root / "questions-20.json")
    parser.add_argument("--responses", type=Path, help="evaluate an existing JSONL response file instead of calling RAGFlow")
    parser.add_argument("--output-dir", type=Path, default=root / "results")
    parser.add_argument("--base-url", default=os.getenv("RAGFLOW_BASE_URL", "http://127.0.0.1:9380"))
    parser.add_argument("--chat-id", default=os.getenv("RAGFLOW_CHAT_ID"))
    parser.add_argument("--timeout", type=float, default=180.0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    suite = load_suite(args.dataset)
    if args.responses:
        responses = load_responses(args.responses)
    else:
        api_key = os.getenv("RAGFLOW_API_KEY")
        if not api_key or not args.chat_id:
            print("Set RAGFLOW_API_KEY and RAGFLOW_CHAT_ID, or pass --responses FILE.", file=sys.stderr)
            return 2
        responses = run_live(suite, args.base_url, api_key, args.chat_id, args.timeout)

    report = evaluate_suite(suite, responses)
    paths = write_reports(report, responses, args.output_dir)
    print(f"score={report['score']}/{report['max_score']} passed={str(report['passed']).lower()}")
    for path in paths:
        print(path)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
