import pytest
import json
import os
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
    
    # Run the stage on the tmp_path
    # Note: We need a way to pass is_excluded to MetricsEngine or have it use config
    findings = metrics_engine.run_stage([str(tmp_path)])
    
    # findings should NOT contain bad.py
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
    findings = metrics_engine.parse_flake8(stdout)
    assert len(findings) == 1
    assert findings[0]["category"] == "Architectural & Design Flaw"

def test_metrics_engine_unreadable_file(metrics_engine, tmp_path):
    # Create a file that is unreadable (e.g. no read permission)
    unreadable = tmp_path / "unreadable.py"
    unreadable.write_text("print('no')")
    os.chmod(str(unreadable), 0o000)
    
    # This should not crash the scanner
    findings = metrics_engine._analyze_generic_file(str(unreadable))
    assert len(findings) == 0
    
    # Restore permissions to cleanup
    os.chmod(str(unreadable), 0o644)
