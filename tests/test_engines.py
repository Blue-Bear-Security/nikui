import pytest
import json
import os
from unittest.mock import patch, MagicMock
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
    config = {
        "exclusions": {
            "directories": [".venv"],
            "patterns": ["*.tmp"]
        }
    }
    return MetricsEngine(config)

def test_metrics_engine_respects_exclusions(metrics_engine, tmp_path):
    # Create a dummy .venv directory and a file inside it
    venv_dir = tmp_path / ".venv"
    venv_dir.mkdir()
    bad_file = venv_dir / "bad.py"
    bad_file.write_text("a" * 200) # Should trigger line length smell if scanned
    
    # Create a normal file
    good_file = tmp_path / "good.py"
    good_file.write_text("print('hello')")
    
    findings = metrics_engine.run_stage([str(tmp_path)])
    
    for f in findings:
        assert ".venv" not in f["file_path"]

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
    findings = metrics_engine.flake8_parser.parse(stdout)
    assert len(findings) == 1
    assert findings[0]["category"] == "Architectural & Design Flaw"

@patch("nikui.engines.metrics_engine.CommandRunner.run")
def test_metrics_engine_run_stage(mock_run, metrics_engine, tmp_path):
    # Mock flake8 output
    mock_run.return_value = ("file.py:10:1: C901 complex function", "")
    
    # Create dummy file for generic metrics
    f = tmp_path / "long.py"
    f.write_text("a" * 200)
    
    findings = metrics_engine.run_stage([str(tmp_path)])
    
    # Should have 1 from flake8 and 1 from generic metrics
    assert len(findings) >= 2
    assert any(f["tool"] == "Flake8" for f in findings)
    assert any(f["tool"] == "GenericMetrics" for f in findings)

@patch("requests.post")
def test_ollama_engine_analyze_file(mock_post, ollama_engine, tmp_path):
    prompt_path = tmp_path / "prompt.md"
    prompt_path.write_text("File: {filename}\nCode: {code}")
    
    source_file = tmp_path / "hello.py"
    source_file.write_text("print('hello')")
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"response": '[{"category": "Deep Nesting", "severity": "Medium", "description": "test"}]'}
    mock_post.return_value = mock_response
    
    findings = ollama_engine.analyze_file(str(source_file), str(prompt_path))
    
    assert len(findings) == 1
    assert findings[0]["description"] == "test"
    assert mock_post.called
