import pytest
import os
from nikui.engines.duplication_engine import DuplicationEngine

@pytest.fixture
def duplication_engine():
    config = {
        "exclusions": {"directories": [], "patterns": []},
        "duplication": {"threshold": 0.85, "min_lines": 3},
    }
    return DuplicationEngine(config)

def test_duplication_go_files(duplication_engine, tmp_path):
    go_code = """
package main
import "fmt"
func HelloWorld() {
    fmt.Println("Hello, World!")
    fmt.Println("This is a test.")
}
"""
    file1 = tmp_path / "main.go"
    file1.write_text(go_code)

    file2 = tmp_path / "other.go"
    # Identical code but different comments/whitespace
    file2.write_text(go_code.replace("Hello", "Hi") + "\n// Some comment")

    findings = duplication_engine.run_stage([str(tmp_path)])
    
    assert len(findings) >= 2
    assert any("main.go" in f["file_path"] for f in findings)
    assert any("other.go" in f["file_path"] for f in findings)

def test_duplication_ts_files(duplication_engine, tmp_path):
    ts_code = """
export const logger = (msg: string) => {
    console.log("LOG:", msg);
    console.log("Timestamp:", new Date());
};
"""
    file1 = tmp_path / "logger.ts"
    file1.write_text(ts_code)

    file2 = tmp_path / "utils.ts"
    file2.write_text(ts_code)

    findings = duplication_engine.run_stage([str(tmp_path)])
    assert len(findings) >= 2
