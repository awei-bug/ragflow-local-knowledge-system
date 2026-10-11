#
#  Copyright 2026 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parents[3]
_RUNNER_PATH = _REPO_ROOT / "enterprise-aftersales" / "acceptance" / "run_acceptance.py"
_DATASET_PATH = _REPO_ROOT / "enterprise-aftersales" / "acceptance" / "questions-20.json"


def _load_runner():
    module_name = "aftersales_acceptance_runner"
    spec = importlib.util.spec_from_file_location(module_name, _RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.p1
def test_top20_dataset_is_complete_and_unique():
    runner = _load_runner()
    suite = runner.load_suite(_DATASET_PATH)

    assert suite["minimum_score"] == 32
    assert len(suite["cases"]) == 20
    assert len({case["id"] for case in suite["cases"]}) == 20
    assert {case["mode"] for case in suite["cases"]} == {"answer", "clarify", "refuse"}


@pytest.mark.p1
def test_top20_perfect_response_passes_all_gates():
    runner = _load_runner()
    suite = runner.load_suite(_DATASET_PATH)
    responses = {}
    for case in suite["cases"]:
        if case["mode"] == "refuse":
            answer = "知识库未覆盖该问题，请转人工或知识管理员确认。"
        else:
            answer = "；".join(group[0] for group in case["term_groups"])
        responses[case["id"]] = {
            "id": case["id"],
            "answer": answer,
            "references": [{"document_name": pattern} for pattern in case.get("source_patterns", [])],
        }

    report = runner.evaluate_suite(suite, responses)

    assert report["score"] == 40
    assert report["all_required_citations_present"] is True
    assert report["all_safe_refusals_passed"] is True
    assert report["passed"] is True


@pytest.mark.p1
def test_missing_required_citation_fails_even_above_score_threshold():
    runner = _load_runner()
    suite = runner.load_suite(_DATASET_PATH)
    responses = {}
    for case in suite["cases"]:
        answer = "知识库未覆盖，请转人工。" if case["mode"] == "refuse" else "；".join(group[0] for group in case["term_groups"])
        responses[case["id"]] = {
            "id": case["id"],
            "answer": answer,
            "references": [{"document_name": pattern} for pattern in case.get("source_patterns", [])],
        }
    responses["AS-001"]["references"] = []

    report = runner.evaluate_suite(suite, responses)

    assert report["score"] == 39
    assert report["score"] >= report["minimum_score"]
    assert report["all_required_citations_present"] is False
    assert report["passed"] is False


@pytest.mark.p1
def test_library_external_answer_must_explicitly_refuse():
    runner = _load_runner()
    suite = runner.load_suite(_DATASET_PATH)
    case = next(case for case in suite["cases"] if case["id"] == "AS-016")

    unsafe = runner.evaluate_case(case, {"answer": "B200 大概率可以使用。"})
    escalated_only = runner.evaluate_case(case, {"answer": "请转人工确认。"})
    safe = runner.evaluate_case(case, {"answer": "知识库未覆盖，不能猜测兼容性，请转人工确认。"})

    assert unsafe.score == 0
    assert escalated_only.score == 1
    assert safe.score == 2
    assert safe.safe_refusal_ok is True




def _write_perfect_responses(path: Path, *, omit_citation_for: str | None = None) -> None:
    runner = _load_runner()
    suite = runner.load_suite(_DATASET_PATH)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for case in suite["cases"]:
            if case["mode"] == "refuse":
                answer = "知识库未覆盖该问题，不能猜测，请转人工或知识管理员确认。"
            else:
                answer = "；".join(group[0] for group in case["term_groups"])
            references = [{"document_name": pattern} for pattern in case.get("source_patterns", [])]
            if case["id"] == omit_citation_for:
                references = []
            handle.write(json.dumps({"id": case["id"], "answer": answer, "references": references}, ensure_ascii=False) + "\n")


@pytest.mark.p1
def test_cli_offline_run_writes_all_reports_and_returns_zero(tmp_path: Path):
    responses_path = tmp_path / "responses.jsonl"
    output_dir = tmp_path / "results"
    _write_perfect_responses(responses_path)

    completed = subprocess.run(
        [
            sys.executable,
            str(_RUNNER_PATH),
            "--dataset",
            str(_DATASET_PATH),
            "--responses",
            str(responses_path),
            "--output-dir",
            str(output_dir),
        ],
        check=False,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr.decode(errors="replace")
    assert b"score=40/40 passed=true" in completed.stdout
    report_paths = list(output_dir.glob("report-*.json"))
    markdown_paths = list(output_dir.glob("report-*.md"))
    raw_response_paths = list(output_dir.glob("responses-*.jsonl"))
    assert len(report_paths) == len(markdown_paths) == len(raw_response_paths) == 1
    report = json.loads(report_paths[0].read_text(encoding="utf-8"))
    assert report["passed"] is True
    assert report["score"] == 40


@pytest.mark.p1
def test_cli_offline_run_returns_one_when_required_citation_is_missing(tmp_path: Path):
    responses_path = tmp_path / "responses.jsonl"
    output_dir = tmp_path / "results"
    _write_perfect_responses(responses_path, omit_citation_for="AS-001")

    completed = subprocess.run(
        [
            sys.executable,
            str(_RUNNER_PATH),
            "--dataset",
            str(_DATASET_PATH),
            "--responses",
            str(responses_path),
            "--output-dir",
            str(output_dir),
        ],
        check=False,
        capture_output=True,
    )

    assert completed.returncode == 1, completed.stderr.decode(errors="replace")
    assert b"score=39/40 passed=false" in completed.stdout
    report_path = next(output_dir.glob("report-*.json"))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["score"] >= report["minimum_score"]
    assert report["all_required_citations_present"] is False
    assert report["passed"] is False


