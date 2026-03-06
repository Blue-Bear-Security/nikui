import os
import json
import pytest
from unittest.mock import patch, MagicMock
from nikui.generate_report import generate_reports
from nikui.utils import is_excluded


@pytest.fixture
def mock_config(tmp_path):
    config = {
        "exclusions": {"directories": [".git", "node_modules"], "patterns": ["*.test.js"]},
        "stench_weights": {
            "Security Vulnerability": 50,
            "Code Quality & Maintainability": 5,
        },
    }
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config))
    return str(config_path)


@pytest.fixture
def mock_findings(tmp_path):
    findings = [
        {
            "file_path": "heavy_debt.py",
            "category": "Security Vulnerability",
            "severity": "High",
            "description": "Critical issue",
        },
        {
            "file_path": "clean_file.py",
            "category": "Code Quality & Maintainability",
            "severity": "Low",
            "description": "Minor issue",
        },
    ]
    json_path = tmp_path / "findings.json"
    json_path.write_text(json.dumps(findings))
    return str(json_path)


def test_is_excluded():
    config = {
        "exclusions": {
            "directories": ["node_modules", ".git"],
            "patterns": ["*.test.js", "tests/*"],
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


@patch("nikui.generate_report.get_git_metadata")
def test_generate_reports_scoring(mock_git, tmp_path, mock_config, mock_findings):
    # heavy_debt.py: Stench = 50 * 3.0 (High) = 150. Churn = 10. Hotspot = 1500.
    # clean_file.py: Stench = 5 * 1.0 (Low) = 5. Churn = 2. Hotspot = 10.
    def git_side_effect(path):
        if "heavy_debt" in path:
            return 10, 1000000
        return 2, 1000000

    mock_git.side_effect = git_side_effect

    html_path = str(tmp_path / "report.html")

    # We need to mock report_template.html location because generate_report uses __file__
    with patch("nikui.generate_report.HtmlReporter.render") as mock_render:
        generate_reports(str(tmp_path), mock_findings, html_path, mock_config)

        # Check that the sorted findings passed to render are correct
        args, _ = mock_render.call_args
        sorted_files = args[0]  # sorted_files is now the 1st argument to render

        # Find heavy_debt.py in results
        heavy_stats = next(s for p, s in sorted_files if p == "heavy_debt.py")
        assert heavy_stats["stench"] == 150
        assert heavy_stats["hotspot_score"] == 1500

        clean_stats = next(s for p, s in sorted_files if p == "clean_file.py")
        assert clean_stats["stench"] == 5
        assert clean_stats["hotspot_score"] == 10
