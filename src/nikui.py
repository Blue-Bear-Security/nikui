import argparse
import json
import subprocess
import sys
import os
import re
import random
import fnmatch
import shlex

# Define temporary file paths relative to the project root
TEMP_DIR = os.path.join(os.getcwd(), ".gemini", "tmp")
OLLAMA_RAW_OUTPUT_FILE = os.path.join(TEMP_DIR, "ollama_raw_output.json")
SEMGREP_RAW_OUTPUT_FILE = os.path.join(TEMP_DIR, "semgrep_raw_output.json")
SEMGREP_CATEGORIZED_OUTPUT_FILE = os.path.join(TEMP_DIR, "categorized_semgrep_findings.json")
BASIC_SMELLS_OUTPUT_FILE = os.path.join(TEMP_DIR, "basic_smells.json")

# Ensure the temporary directory exists
os.makedirs(TEMP_DIR, exist_ok=True)

# List of directories to scan for code files.
CODE_DIRS_TO_SCAN = [
    "./bluebear-backend/",
    "./console/src/",
    "./handler/internal/",
]

# File extensions to consider for scanning
FILE_EXTENSIONS = (".py", ".js", ".ts", ".tsx", ".go")

# Patterns to exclude test files/directories
TEST_FILE_PATTERNS_TO_EXCLUDE = [
    "*/tests/*", "*/test/*", "test_*.py", "*.test.js", "*.test.ts", "*.test.tsx", "*_test.go", "tests/*", "test/*"
]

# Exact file paths to ignore
IGNORED_FILES_EXACT = [
    "console/tailwind.config.js", "commitlint.config.js", "console/jest.config.js",
    "console/jest.setup.js", "console/next.config.js", "console/postcss.config.js",
    "console/vitest.config.ts", "console/next-env.d.ts", "bluebear-backend/sst.config.ts",
    "bluebear-backend/services/shared/migrations/versions/",
    "bluebear-backend/services/shared/migrations/env.py",
    "bluebear-backend/services/shared/migrations/migration_utils.py",
    "handler/homebrew/test/local-test/stub_server.py",
    "handler/homebrew/test/stub_server.py",
    "handler/homebrew/test/test_oauth_flow.py",
]

def is_excluded(filepath):
    """Checks if a given filepath should be excluded based on defined patterns."""
    normalized_filepath = os.path.normpath(filepath)
    
    for ignored_path in IGNORED_FILES_EXACT:
        normalized_ignored_path = os.path.normpath(ignored_path)
        if normalized_ignored_path.endswith(os.sep) and normalized_filepath.startswith(normalized_ignored_path):
            return True
        elif normalized_filepath == normalized_ignored_path:
            return True
            
    filename = os.path.basename(filepath)
    for pattern in TEST_FILE_PATTERNS_TO_EXCLUDE:
        if fnmatch.fnmatch(filepath, pattern) or fnmatch.fnmatch(filename, pattern):
            return True
            
    # Extra safety exclusions
    if any(x in filepath for x in ["/tests/", "/test/", "/tools/", "/research/", "/ops-agent/", "/scripts/"]):
        return True
    if any(filepath.startswith(x) for x in ["tests/", "test/", "tools/", "research/", "ops-agent/", "scripts/"]):
        return True
        
    return False

def run_command(command, description, capture_output=True, check=True):
    """Executes a shell command and optionally captures its stdout."""
    print(f"Running: {description}...", file=sys.stderr)
    try:
        result = subprocess.run(
            command, shell=True,
            stdout=subprocess.PIPE if capture_output else None,
            stderr=None, text=True, check=check, cwd=os.getcwd(), encoding='utf-8'
        )
        return result.stdout if capture_output else ""
    except subprocess.CalledProcessError as e:
        print(f"Error running {description}: {e}", file=sys.stderr)
        sys.exit(1)

def _process_ollama_file_output(file_path, raw_output_block, all_findings_list):
    """Helper to process a single file's raw Ollama output block."""
    json_array_regex = r"\[\s*(?:\{.*?\}(?:,\s*\{.*?\})*)?\s*\]"
    matches = re.finditer(json_array_regex, raw_output_block, re.DOTALL)
    
    found = False
    for match in matches:
        try:
            file_findings = json.loads(match.group(0))
            if isinstance(file_findings, list) and all(isinstance(f, dict) for f in file_findings):
                found = True
                for finding in file_findings:
                    category_map = {
                        "Deep Nesting": "Code Quality & Maintainability",
                        "Poor Naming": "Best Practices & Conventions",
                        "Violations of SOLID principles": "Architectural & Design Flaw",
                        "God Objects / Shotgun Surgery": "Architectural & Design Flaw",
                        "Improper Error Handling & Silent Failures": "Improper Error Handling & Silent Failures"
                    }
                    description = finding.get("description", "")
                    if "no issues" in description.lower() or "no code smells" in description.lower():
                        continue
                    all_findings_list.append({
                        "tool": "Ollama",
                        "file_path": file_path,
                        "line": None,
                        "category": category_map.get(finding.get("category"), "Code Quality & Maintainability"),
                        "severity": finding.get("severity", "Medium"),
                        "description": description
                    })
                break
        except json.JSONDecodeError:
            continue
    if not found and "no issues were found" not in raw_output_block.lower():
        print(f"Warning: No valid JSON for {file_path}", file=sys.stderr)

def get_ollama_findings():
    """Runs Ollama on 5% sample of files."""
    print("Starting Ollama scan (5% sampling)...", file=sys.stderr)
    all_ollama_findings = []
    eligible_files = []
    for code_dir in CODE_DIRS_TO_SCAN:
        if not os.path.isdir(code_dir): continue
        for root, _, files in os.walk(code_dir):
            for file in files:
                filepath = os.path.join(root, file)
                if not is_excluded(filepath) and any(filepath.endswith(ext) for ext in FILE_EXTENSIONS):
                    eligible_files.append(filepath)
    
    sample_size = max(1, int(len(eligible_files) * 0.05)) if eligible_files else 0
    sampled_files = random.sample(eligible_files, sample_size)
    print(f"Sampling {sample_size} out of {len(eligible_files)} files.", file=sys.stderr)

    for filepath in sampled_files:
        print(f"Processing (Ollama): {filepath}", file=sys.stderr)
        quoted_path = shlex.quote(filepath)
        stdout = run_command(f"uv run --with requests python3 src/code_smell_detector.py --quiet --file-path {quoted_path}", 
                             f"Ollama scan for {filepath}", capture_output=True, check=False)
        _process_ollama_file_output(filepath, stdout, all_ollama_findings)
    return all_ollama_findings, sampled_files

def get_basic_findings():
    """Runs basic non-LLM code smell detector on all directories."""
    print("Starting basic analysis (Flake8, GoVet, BasicTS) on full repository...", file=sys.stderr)
    dirs_str = " ".join(shlex.quote(d) for d in CODE_DIRS_TO_SCAN)
    run_command(f"python3 src/basic_smell_detector.py --output-file {shlex.quote(BASIC_SMELLS_OUTPUT_FILE)} --scan-dirs {dirs_str}",
                "Basic Smell Detector", capture_output=False)
    try:
        with open(BASIC_SMELLS_OUTPUT_FILE, 'r', encoding='utf-8') as f:
            findings = json.load(f)
            return [f for f in findings if not is_excluded(f.get("file_path", ""))]
    except:
        return []

def get_semgrep_findings():
    """Runs Semgrep on full repo using security and best-practice rules."""
    print("Starting Semgrep scan...", file=sys.stderr)
    semgrep_command = (
        "semgrep scan "
        "--config p/security-audit "
        "--config p/secrets "
        "--config p/best-practices "
        "--config p/owasp-top-10 "
        "--config default "
        "--config p/python "
        "--config p/react "
        "--exclude scripts/ --exclude research/ --exclude ops-agent/ --exclude tools/ --exclude '**/tests/**' --exclude '**/test/**' "
        f"--json > {shlex.quote(SEMGREP_RAW_OUTPUT_FILE)}"
    )
    run_command(semgrep_command, "Semgrep Raw Scan", capture_output=False, check=False)
    stdout = run_command(f"python3 src/semgrep_parser.py {shlex.quote(SEMGREP_RAW_OUTPUT_FILE)}", "Semgrep Parser", capture_output=True)
    try:
        return json.loads(stdout)
    except:
        return []

def main():
    parser = argparse.ArgumentParser(description="Analyze code for smells with 5% sampling.")
    parser.add_argument("--output-file", default="analysis_report.json", help="Path to save report.")
    args = parser.parse_args()

    all_findings = []
    ollama_findings, sampled_files = get_ollama_findings()
    all_findings.extend(ollama_findings)
    all_findings.extend(get_semgrep_findings())
    all_findings.extend(get_basic_findings())

    with open(args.output_file, 'w', encoding='utf-8') as f:
        json.dump(all_findings, f, indent=2)
    print(f"\nAnalysis complete. Report saved to {args.output_file}", file=sys.stderr)

if __name__ == "__main__":
    main()
