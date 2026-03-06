import pytest
import json
from nikui.engines.ollama_engine import OllamaEngine
from nikui.engines.semgrep_engine import SemgrepEngine
from nikui.engines.metrics_engine import MetricsEngine

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
    return MetricsEngine({})

def test_parse_ollama_valid_json(ollama_engine):
    raw_output = '[{"category": "Deep Nesting", "severity": "Medium", "description": "test"}]'
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
                    "metadata": {"category": "security"}
                }
            }
        ]
    }
    findings = semgrep_engine.parse_results(mock_data)
    assert len(findings) == 1
    assert findings[0]["tool"] == "Semgrep"

def test_parse_flake8_complexity(metrics_engine):
    stdout = "test.py:73:1: C901 'func' is too complex (11)"
    findings = metrics_engine.parse_flake8(stdout)
    assert len(findings) == 1
    assert findings[0]["category"] == "Architectural & Design Flaw"

def test_analyze_generic_file(metrics_engine, tmp_path):
    f = tmp_path / "long.py"
    f.write_text("a" * 200)
    findings = metrics_engine._analyze_generic_file(str(f), max_line_length=120)
    assert len(findings) == 1
    assert "Line exceeds" in findings[0]["description"]
