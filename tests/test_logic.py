import os
import pytest
from nikui.generate_report import is_excluded
from nikui.semgrep_parser import categorize_semgrep_finding
from nikui.basic_smell_detector import _analyze_generic_file

def test_is_excluded():
    config = {
        "exclusions": {
            "directories": ["node_modules", ".git"],
            "patterns": ["*.test.js", "tests/*"]
        }
    }
    
    # Should be excluded
    assert is_excluded("node_modules/pkg/index.js", config) is True
    assert is_excluded(".git/config", config) is True
    assert is_excluded("src/app.test.js", config) is True
    assert is_excluded("tests/unit/test_app.py", config) is True
    
    # Should NOT be excluded
    assert is_excluded("src/main.py", config) is False
    assert is_excluded("lib/utils.js", config) is False

def test_categorize_semgrep_finding():
    # Security
    assert categorize_semgrep_finding("hardcoded-secret", "ERROR") == "Security Vulnerability"
    assert categorize_semgrep_finding("insecure-audit-call", "WARNING") == "Security Vulnerability"
    
    # Architecture
    assert categorize_semgrep_finding("too-much-complexity", "WARNING") == "Architectural & Design Flaw"
    
    # Best Practice
    assert categorize_semgrep_finding("correctness-best-practice", "INFO") == "Best Practices & Conventions"
    
    # Default
    assert categorize_semgrep_finding("random-check", "INFO") == "Code Quality & Maintainability"

def test_analyze_generic_file(tmp_path):
    # Create a large file
    large_file = tmp_path / "large.py"
    large_file.write_text("\n" * 600)
    
    # Create a long line file
    long_line_file = tmp_path / "long.py"
    long_line_file.write_text("a" * 150)
    
    findings_large = _analyze_generic_file(str(large_file), max_lines=500, max_line_length=120)
    assert any("File is too large" in f["description"] for f in findings_large)
    
    findings_long = _analyze_generic_file(str(long_line_file), max_lines=500, max_line_length=120)
    assert any("Line exceeds 120 characters" in f["description"] for f in findings_long)

def test_analyze_generic_file_clean(tmp_path):
    clean_file = tmp_path / "clean.py"
    clean_file.write_text("print('hello')\n")
    
    findings = _analyze_generic_file(str(clean_file), max_lines=500, max_line_length=120)
    assert len(findings) == 0
