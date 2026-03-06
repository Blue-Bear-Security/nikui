import os
import re
import subprocess
import sys

class MetricsEngine:
    def __init__(self, config):
        self.config = config

    def run_command(self, command):
        try:
            result = subprocess.run(
                command, shell=True, stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, text=True, encoding='utf-8'
            )
            return result.stdout, result.stderr
        except: return "", ""

    def parse_flake8(self, stdout):
        findings = []
        pattern = r"^(.*?):(\d+):(\d+): ([A-Z]\d+) (.*)$"
        for line in stdout.splitlines():
            match = re.match(pattern, line)
            if match:
                file_path, line_num, _, code, description = match.groups()
                category = "Architectural & Design Flaw" if code.startswith("C9") else "Code Quality & Maintainability"
                findings.append({
                    "tool": "Flake8", "file_path": file_path, "line": int(line_num),
                    "category": category, "description": f"[{code}] {description}"
                })
        return findings

    def _analyze_generic_file(self, file_path, max_lines=500, max_line_length=120):
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
        except: pass
        return findings

    def run_stage(self, scan_dirs):
        print("\n--- [Stage 3/3] Objective Metrics & Linting (Static) ---", file=sys.stderr)
        all_findings = []
        
        # 1. Flake8
        for d in scan_dirs:
            if os.path.isdir(d):
                stdout, _ = self.run_command(f"flake8 --max-complexity=10 {d}")
                all_findings.extend(self.parse_flake8(stdout))
        
        # 2. Generic Metrics
        for d in scan_dirs:
            if not os.path.isdir(d): continue
            for root, _, files in os.walk(d):
                for file in files:
                    if file.endswith((".py", ".ts", ".tsx", ".js", ".go")):
                        all_findings.extend(self._analyze_generic_file(os.path.join(root, file)))
        
        return all_findings
