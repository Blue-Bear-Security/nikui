import pytest
import json
import os
from unittest.mock import patch, MagicMock
from nikui.engines.ollama_engine import OllamaEngine, LLMClient
from nikui.engines.semgrep_engine import SemgrepEngine
from nikui.engines.metrics_engine import MetricsEngine
from nikui.engines.dependency_engine import DependencyEngine
from nikui.engines.duplication_engine import DuplicationEngine


@pytest.fixture
def dependency_engine():
    return DependencyEngine({})


def test_dependency_engine_extract_imports(dependency_engine, tmp_path):
    code = """
import nikui.utils
from nikui.engines import ollama_engine
import requests
"""
    f = tmp_path / "test.py"
    f.write_text(code)

    # eligible_paths must be seeded so local import detection works
    dependency_engine.eligible_paths = {"nikui/utils.py", "nikui/engines/ollama_engine.py"}

    imports = dependency_engine.extract_imports(str(f))
    # Should only keep local nikui imports
    assert "nikui.utils" in imports
    assert "nikui.engines" in imports
    assert "requests" not in imports


@pytest.fixture
def ollama_engine():
    config = {"ollama": {"model": "qwen2.5-coder:7b", "sampling_rate": 0.01}}
    return OllamaEngine(config, ".", ".")


@pytest.fixture
def semgrep_engine():
    config = {"semgrep": {"configs": ["default"]}, "exclusions": {"directories": []}}
    return SemgrepEngine(config, ".")


@pytest.fixture
def metrics_engine():
    config = {
        "exclusions": {"directories": [".venv"], "patterns": ["*.tmp"]},
        "flake8": {"ignore": []},
        "stench_weights": {},
    }
    return MetricsEngine(config)


@pytest.fixture
def duplication_engine():
    config = {
        "exclusions": {"directories": [], "patterns": []},
        "duplication": {"threshold": 0.85, "min_lines": 3},
    }
    return DuplicationEngine(config)


def test_metrics_engine_respects_exclusions(metrics_engine, tmp_path):
    venv_dir = tmp_path / ".venv"
    venv_dir.mkdir()
    bad_file = venv_dir / "bad.py"
    bad_file.write_text("a" * 200)

    good_file = tmp_path / "good.py"
    good_file.write_text("print('hello')")

    findings = metrics_engine.run_stage([str(good_file)])

    for f in findings:
        assert ".venv" not in f["file_path"]


def test_parse_ollama_valid_json(ollama_engine):
    raw_output = (
        '[{"category": "Deep Nesting", "severity": "Medium", "description": "test"}]'
    )
    findings = ollama_engine._parse_output("test.py", raw_output)
    assert len(findings) == 1
    assert findings[0]["tool"] == "Ollama"


def test_parse_semgrep_results_valid(semgrep_engine):
    mock_data = {
        "results": [
            {
                "path": "test.py",
                "start": {"line": 10},
                "check_id": "security.audit.call",
                "extra": {
                    "message": "Dangerous call",
                    "severity": "ERROR",
                    "metadata": {"category": "security"},
                },
            }
        ]
    }
    findings = semgrep_engine.parse_results(mock_data)
    assert len(findings) == 1
    assert findings[0]["tool"] == "Semgrep"


def test_semgrep_categorization(semgrep_engine):
    assert (
        semgrep_engine.categorize_finding("design.complexity", "WARNING")
        == "Architectural & Design Flaw"
    )
    assert (
        semgrep_engine.categorize_finding("random.check", "INFO")
        == "Code Quality & Maintainability"
    )


def test_parse_flake8_complexity(metrics_engine):
    stdout = "test.py:73:1: C901 'func' is too complex (11)"
    findings = metrics_engine.flake8_parser.parse(stdout)
    assert len(findings) == 1
    assert findings[0]["category"] == "Architectural & Design Flaw"


def test_generic_file_scanner(metrics_engine, tmp_path):
    f = tmp_path / "long.py"
    f.write_text("a" * 200)
    lines = ["a" * 200]
    findings = metrics_engine.file_scanner.scan_lines(
        str(f), lines, max_line_length=120
    )
    assert len(findings) == 1
    assert "Line exceeds" in findings[0]["description"]


def test_duplication_engine_detects_copies(duplication_engine, tmp_path):
    code = """
def calculate_sum(a, b):
    # This is a comment
    # More lines to meet min_lines
    # More lines to meet min_lines
    # More lines to meet min_lines
    result = a + b
    return result
"""
    file1 = tmp_path / "file1.py"
    file1.write_text(code)

    file2 = tmp_path / "file2.py"
    file2.write_text(
        code.replace("calculate_sum", "add_numbers").replace("result", "val")
    )

    findings = duplication_engine.run_stage([str(file1), str(file2)])

    assert len(findings) >= 2
    assert all(f["tool"] == "Duplication" for f in findings)


def test_duplication_engine_with_llm_verification(duplication_engine, tmp_path):
    code = """
def some_logic():
    # Long enough to meet min_lines
    # Long enough to meet min_lines
    # Long enough to meet min_lines
    # Long enough to meet min_lines
    return 1 + 2 + 3 + 4 + 5 + 6 + 7 + 8 + 9 + 10
"""
    file1 = tmp_path / "f1.py"
    file1.write_text(code)
    file2 = tmp_path / "f2.py"
    file2.write_text(code)

    mock_ollama = MagicMock()
    mock_ollama.client.is_running.return_value = True
    mock_ollama.verify_duplication.return_value = (False, "Boilerplate")

    findings = duplication_engine.run_stage(
        [str(file1), str(file2)], ollama=mock_ollama
    )

    assert len(findings) == 0
    assert mock_ollama.verify_duplication.called


@patch("nikui.engines.metrics_engine.CommandRunner.run")
def test_metrics_engine_run_stage(mock_run, metrics_engine, tmp_path):
    mock_run.return_value = ("file.py:10:1: C901 complex function", "")
    f = tmp_path / "long.py"
    f.write_text("a" * 200)

    findings = metrics_engine.run_stage([str(f)])

    assert len(findings) >= 2
    assert any(f["tool"] == "Flake8" for f in findings)
    assert any(f["tool"] == "GenericMetrics" for f in findings)


@patch("requests.post")
def test_ollama_engine_analyze_file(mock_post, ollama_engine, tmp_path):
    prompt_path = tmp_path / "prompt.md"
    prompt_path.write_text("File: {filename}\nCode: {line_numbered_code}")

    source_file = tmp_path / "hello.py"
    source_file.write_text("print('hello')")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": '[{"category": "Deep Nesting", "severity": "Medium", "description": "test"}]'}}]
    }
    mock_post.return_value = mock_response

    findings = ollama_engine.analyze_file(str(source_file), str(prompt_path))

    assert len(findings) == 1
    assert findings[0]["description"] == "test"
    assert mock_post.called


def test_strip_markdown_fence(ollama_engine):
    assert ollama_engine._strip_markdown_fence('```json\n[]\n```') == '[]'
    assert ollama_engine._strip_markdown_fence('```\n[]\n```') == '[]'
    assert ollama_engine._strip_markdown_fence('[]') == '[]'
    assert ollama_engine._strip_markdown_fence('  []  ') == '[]'


@patch("requests.get")
def test_llm_client_is_running(mock_get):
    client = LLMClient("test-model", "http://localhost:8080/v1")

    mock_get.return_value = MagicMock(status_code=200)
    assert client.is_running() is True
    mock_get.assert_called_with("http://localhost:8080/v1/models", headers={"Content-Type": "application/json"}, timeout=2)

    mock_get.side_effect = Exception("conn refused")
    assert client.is_running() is False
