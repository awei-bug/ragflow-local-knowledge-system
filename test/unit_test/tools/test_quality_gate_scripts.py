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
import sys
from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_tool(name: str):
    module_name = f"enterprise_ci_{name}"
    path = _REPO_ROOT / "tools" / "ci" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.p1
def test_test_deletion_parser_only_returns_automated_tests():
    tool = _load_tool("check_test_deletions")
    raw = b"D\0test/unit_test/api/test_auth.py\0D\0internal/parser/parser_test.go\0D\0api/auth.py\0"

    assert tool.parse_deleted_paths(raw) == ["test/unit_test/api/test_auth.py", "internal/parser/parser_test.go"]


@pytest.mark.p1
def test_test_deletion_allowlist_requires_a_reason(tmp_path: Path):
    tool = _load_tool("check_test_deletions")
    allowlist = tmp_path / "allowlist.txt"
    allowlist.write_text("test/unit_test/api/test_auth.py\n", encoding="utf-8")

    with pytest.raises(ValueError, match=r"path \| reason"):
        tool.load_allowlist(allowlist)


@pytest.mark.p1
def test_diff_parser_tracks_only_added_in_scope_python_lines():
    tool = _load_tool("check_diff_coverage")
    diff = """diff --git a/api/example.py b/api/example.py
--- a/api/example.py
+++ b/api/example.py
@@ -4,0 +5,3 @@
+covered = True
+missing = True
+# not executable
diff --git a/test/unit_test/test_example.py b/test/unit_test/test_example.py
--- a/test/unit_test/test_example.py
+++ b/test/unit_test/test_example.py
@@ -0,0 +1 @@
+def test_example(): pass
"""

    assert tool.collect_changed_lines(diff) == {"api/example.py": {5, 6, 7}}


@pytest.mark.p1
def test_diff_coverage_default_scope_includes_common_security_code():
    tool = _load_tool("check_diff_coverage")
    diff = """diff --git a/common/security_config.py b/common/security_config.py
--- a/common/security_config.py
+++ b/common/security_config.py
@@ -10,0 +11,1 @@
+return True
"""

    assert tool.collect_changed_lines(diff) == {"common/security_config.py": {11}}


@pytest.mark.p1
def test_diff_coverage_counts_only_executable_changed_lines(tmp_path: Path):
    tool = _load_tool("check_diff_coverage")
    coverage_path = tmp_path / "coverage.json"
    coverage_path.write_text(
        json.dumps(
            {
                "files": {
                    "api/example.py": {
                        "executed_lines": [5],
                        "missing_lines": [6],
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    coverage = tool.load_coverage(coverage_path)

    covered, statements, missing, unmeasured = tool.evaluate({"api/example.py": {5, 6, 7}}, coverage)

    assert covered == 1
    assert statements == 2
    assert missing == {"api/example.py": [6]}
    assert unmeasured == []


@pytest.mark.p1
def test_diff_coverage_rejects_changed_files_absent_from_measurement():
    tool = _load_tool("check_diff_coverage")

    covered, statements, missing, unmeasured = tool.evaluate({"memory/new_policy.py": {1}}, {})

    assert covered == 0
    assert statements == 0
    assert missing == {}
    assert unmeasured == ["memory/new_policy.py"]

