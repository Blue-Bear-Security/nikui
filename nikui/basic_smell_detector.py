import os
import subprocess
import json
import sys
import argparse
import re

def run_command(command, description):
    """Executes a shell command and captures its stdout."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            check=False
        )
        return result.stdout, result.stderr, result.returncode
    except Exception as e:
        print(f"Error running {description}: {e}", file=sys.stderr)
        return "", str(e), 1

def parse_flake8(stdout):
    """Parses flake8 output for complexity and logic errors."""
    findings = []
    pattern = r"^(.*?):(\d+):(\d+): ([A-Z]\d+) (.*)$"
    for line in stdout.splitlines():
        match = re.match(pattern, line)
        if match:
            file_path, line_num, col, code, description = match.groups()
            category = None
            if code.startswith("C9"):
                category = "Architectural & Design Flaw"
            elif code.startswith("F"):
                category = "Code Quality & Maintainability"
            if category:
                findings.append({
                    "tool": "Flake8", "file_path": file_path, "line": int(line_num),
                    "category": category, "description": f"[{code}] {description}"
                })
    return findings

def get_python_smells(scan_dirs):
    """Runs flake8 for basic python smells."""
    print("Running Flake8 (Python Quality & Complexity)...", file=sys.stderr)
    all_findings = []
    for d in scan_dirs:
        if not os.path.isdir(d): continue
        stdout, _, _ = run_command(f"flake8 --max-complexity=10 {d}", f"Flake8 on {d}")
        all_findings.extend(parse_flake8(stdout))
    return all_findings

def get_go_smells(scan_dirs):
    """Runs go vet for basic go smells."""
    print("Running Go Vet (Go Quality)...", file=sys.stderr)
    all_findings = []
    for d in scan_dirs:
        if not os.path.isdir(d): continue
        _, stderr, _ = run_command(f"go vet {d}/...", f"Go Vet on {d}")
        pattern = r"^(.*?):(\d+):(\d+): (.*)$"
        for line in stderr.splitlines():
            match = re.match(pattern, line)
            if match:
                file_path, line_num, _, description = match.groups()
                all_findings.append({
                    "tool": "GoVet", "file_path": file_path, "line": int(line_num),
                    "category": "Code Quality & Maintainability", "description": description.strip()
                })
    return all_findings

def _analyze_ts_file(file_path):
    """Analyzes a single TS/JS file for basic smells."""
    findings = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                if ": any" in line or "<any>" in line:
                    findings.append({
                        "tool": "BasicTS", "file_path": file_path, "line": i + 1,
                        "category": "Code Quality & Maintainability",
                        "description": "Usage of 'any' type detected."
                    })
                if "console.log(" in line and "//" not in line.split("console.log(")[0]:
                    findings.append({
                        "tool": "BasicTS", "file_path": file_path, "line": i + 1,
                        "category": "Code Quality & Maintainability",
                        "description": "console.log() found."
                    })
    except:
        pass
    return findings

def get_ts_basic_smells(scan_dirs):
    """Runs regex-based smells for TS/JS files."""
    print("Running basic TS/JS regex scanner...", file=sys.stderr)
    findings = []
    for d in scan_dirs:
        if not os.path.isdir(d): continue
        for root, _, files in os.walk(d):
            for file in files:
                if file.endswith((".ts", ".tsx", ".js")):
                    findings.extend(_analyze_ts_file(os.path.join(root, file)))
    return findings

def _analyze_generic_file(file_path, max_lines, max_line_length):
    """Analyzes a single file for generic metrics."""
    findings = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            if len(lines) > max_lines:
                findings.append({
                    "tool": "GenericMetrics", "file_path": file_path, "line": 1,
                    "category": "Architectural & Design Flaw",
                    "description": f"File is too large ({len(lines)} lines)."
                })
            for i, line in enumerate(lines):
                if len(line) > max_line_length:
                    findings.append({
                        "tool": "GenericMetrics", "file_path": file_path, "line": i + 1,
                        "category": "Code Quality & Maintainability",
                        "description": f"Line exceeds {max_line_length} characters."
                    })
                    break
    except:
        pass
    return findings

def get_generic_file_smells(scan_dirs):
    """Checks for file size and extreme line length smells."""
    print("Running generic file metrics scanner...", file=sys.stderr)
    findings = []
    MAX_FILE_LINES = 500
    MAX_LINE_LENGTH = 120
    for d in scan_dirs:
        if not os.path.isdir(d): continue
        for root, _, files in os.walk(d):
            for file in files:
                if file.endswith((".py", ".ts", ".tsx", ".js", ".go")):
                    findings.extend(_analyze_generic_file(os.path.join(root, file), MAX_FILE_LINES, MAX_LINE_LENGTH))
    return findings

def main():
    parser = argparse.ArgumentParser(description="Run basic (non-LLM) code smell analysis.")
    parser.add_argument("--output-file", default="basic_smells.json", help="Path to save findings.")
    parser.add_argument("--scan-dirs", nargs="+", help="Directories to scan.")
    args = parser.parse_args()

    if args.scan_dirs:
        PYTHON_DIRS = GO_DIRS = TS_DIRS = args.scan_dirs
    else:
        PYTHON_DIRS = ["."] 
        GO_DIRS = ["./handler/internal/"]
        TS_DIRS = ["./console/src/"]
    
    findings = []
    findings.extend(get_python_smells(PYTHON_DIRS))
    findings.extend(get_go_smells(GO_DIRS))
    findings.extend(get_ts_basic_smells(TS_DIRS))
    
    unique_dirs = list(dict.fromkeys(PYTHON_DIRS + GO_DIRS + TS_DIRS))
    findings.extend(get_generic_file_smells(unique_dirs))

    with open(args.output_file, 'w', encoding='utf-8') as f:
        json.dump(findings, f, indent=2)
    print(f"Basic analysis complete. Found {len(findings)} issues.", file=sys.stderr)

if __name__ == "__main__":
    main()
