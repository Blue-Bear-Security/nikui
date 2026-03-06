import os
import re
import subprocess
import sys
from nikui.utils import is_excluded

class CommandRunner:
    @staticmethod
    def run(command):
        try:
            result = subprocess.run(
                command, shell=True, stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, text=True, encoding='utf-8'
            )
            return result.stdout, result.stderr
        except Exception as e:
            print(f"Error running command {command}: {e}", file=sys.stderr)
            return "", str(e)

class Flake8Parser:
    def __init__(self, config):
        self.config = config

    def parse(self, stdout):
        findings = []
        pattern = r"^(.*?):(\d+):(\d+): ([A-Z]\d+) (.*)$"
        for line in stdout.splitlines():
            match = re.match(pattern, line)
            if match:
                file_path, line_num, _, code, description = match.groups()
                if is_excluded(file_path, self.config):
                    continue
                category = "Architectural & Design Flaw" if code.startswith("C9") else "Code Quality & Maintainability"
                findings.append({
                    "tool": "Flake8", "file_path": file_path, "line": int(line_num),
                    "category": category, "description": f"[{code}] {description}"
                })
        return findings

class GenericFileScanner:
    def __init__(self, config):
        self.config = config

    def scan_file(self, file_path, max_lines=500, max_line_length=120):
        if is_excluded(file_path, self.config):
            return []
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
        except Exception as e:
            print(f"Error reading file {file_path}: {e}", file=sys.stderr)
        return findings

class MetricsEngine:
    def __init__(self, config):
        self.config = config
        self.flake8_parser = Flake8Parser(config)
        self.file_scanner = GenericFileScanner(config)

    def run_stage(self, scan_dirs):
        print("\n--- [Stage 3/3] Objective Metrics & Linting (Static) ---", file=sys.stderr)
        all_findings = []
        
        # 1. Flake8
        exclude_list = ",".join(self.config.get("exclusions", {}).get("directories", []))
        for d in scan_dirs:
            if os.path.isdir(d):
                flake8_cmd = f"flake8 --max-complexity=10 --exclude={exclude_list} {d}"
                stdout, _ = CommandRunner.run(flake8_cmd)
                all_findings.extend(self.flake8_parser.parse(stdout))
        
        # 2. Generic Metrics
        for d in scan_dirs:
            if not os.path.isdir(d): continue
            for root, _, files in os.walk(d):
                dirs_to_skip = [dr for dr in self.config.get("exclusions", {}).get("directories", []) if dr in root.split(os.sep)]
                if dirs_to_skip:
                    continue
                
                for file in files:
                    file_path = os.path.join(root, file)
                    if file.endswith((".py", ".ts", ".tsx", ".js", ".go")):
                        all_findings.extend(self.file_scanner.scan_file(file_path))
        
        return all_findings
