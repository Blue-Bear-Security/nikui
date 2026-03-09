import math
import re
import subprocess
import sys
import os
from nikui.utils import is_excluded


class CommandRunner:
    @staticmethod
    def run(cmd_list):
        try:
            result = subprocess.run(
                cmd_list,
                shell=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
            )
            return result.stdout, result.stderr
        except Exception as e:
            print(f"Error running command {' '.join(cmd_list)}: {e}", file=sys.stderr)
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
                category = (
                    "Architectural & Design Flaw"
                    if code.startswith("C9")
                    else "Code Quality & Maintainability"
                )
                findings.append(
                    {
                        "tool": "Flake8",
                        "file_path": file_path,
                        "line": int(line_num),
                        "category": category,
                        "description": f"[{code}] {description}",
                    }
                )
        return findings


class MaintainabilityAnalyzer:
    @staticmethod
    def analyze(file_path, lines, ext):
        """
        Calculates a proxy Maintainability Index (MI) based on the Microsoft standard (0-100).
        Flags files with a score below 20 (Red) or 50 (Yellow).
        """
        if ext not in [".py", ".ts", ".tsx", ".js", ".go"]:
            return []

        # Count actual lines of code (ignore empty or pure comments)
        loc = len(
            [
                line_str
                for line_str in lines
                if line_str.strip() and not line_str.strip().startswith(("#", "//"))
            ]
        )

        if loc < 10:
            return []

        # Proxy for cyclomatic complexity based on branching keywords
        complexity = 1
        for line in lines:
            complexity += len(re.findall(r"\b(if|for|while|case|catch|except)\b", line))
            complexity += len(re.findall(r"(\&\&|\|\|)", line))

        # Proxy for Halstead Volume (V = N * log2(n)) -> simplified to LOC * log(LOC)
        volume = loc * math.log(loc + 1)

        # MI Formula: MAX(0, (171 - 5.2 * ln(V) - 0.23 * G - 16.2 * ln(LOC)) * 100 / 171)
        mi_raw = (
            171
            - 5.2 * math.log(volume + 1)
            - 0.23 * complexity
            - 16.2 * math.log(loc + 1)
        )
        mi = max(0.0, min(100.0, mi_raw * 100 / 171))

        if mi < 20:
            return [
                {
                    "tool": "MaintainabilityIndex",
                    "file_path": file_path,
                    "line": 1,
                    "category": "Architectural & Design Flaw",
                    "severity": "High",
                    "description": f"Critical Maintainability Index ({mi:.1f}/100). The logic is highly complex and structurally dense.",
                }
            ]
        elif mi < 50:
            return [
                {
                    "tool": "MaintainabilityIndex",
                    "file_path": file_path,
                    "line": 1,
                    "category": "Code Quality & Maintainability",
                    "severity": "Medium",
                    "description": f"Low Maintainability Index ({mi:.1f}/100). Consider refactoring to reduce complexity.",
                }
            ]
        return []


class IaCScanner:
    @staticmethod
    def scan(file_path, lines, ext, filename):
        """Scans Infrastructure-as-Code files for common deployment smells."""
        if ext not in [".yml", ".yaml", ".sh", ".tf"] and filename != "Dockerfile":
            return []

        findings = []
        for i, line in enumerate(lines):
            # Floating / Unpinned versions
            if re.search(r"(image:|FROM)\s+[^\s]+:latest\b", line, re.IGNORECASE):
                findings.append(
                    {
                        "tool": "IaCScanner",
                        "file_path": file_path,
                        "line": i + 1,
                        "category": "Best Practices & Conventions",
                        "severity": "High",
                        "description": "Unpinned dependency version (':latest'). This can lead to unpredictable builds and breaks reproducible infrastructure.",
                    }
                )
            # Hardcoded unsecured URLs (excluding standard local/schema patterns)
            if re.search(r"\bhttp://[a-zA-Z0-9\.\-]+\b", line) and not any(
                safe in line
                for safe in ["localhost", "127.0.0.1", "schema.org", "w3.org"]
            ):
                findings.append(
                    {
                        "tool": "IaCScanner",
                        "file_path": file_path,
                        "line": i + 1,
                        "category": "Security Vulnerability",
                        "severity": "Medium",
                        "description": "Hardcoded unsecured HTTP URL detected. Use HTTPS or inject via environment variables.",
                    }
                )
        return findings


class GenericFileScanner:
    def __init__(self, config):
        self.config = config

    def scan_lines(self, file_path, lines, max_lines=500, max_line_length=120):
        findings = []
        if len(lines) > max_lines:
            findings.append(
                {
                    "tool": "GenericMetrics",
                    "file_path": file_path,
                    "line": 1,
                    "category": "Architectural & Design Flaw",
                    "severity": "Medium",
                    "description": f"File is too large ({len(lines)} lines). Violates Single Responsibility.",
                }
            )
        for i, line in enumerate(lines):
            if len(line) > max_line_length:
                findings.append(
                    {
                        "tool": "GenericMetrics",
                        "file_path": file_path,
                        "line": i + 1,
                        "category": "Code Quality & Maintainability",
                        "severity": "Low",
                        "description": f"Line exceeds {max_line_length} characters.",
                    }
                )
                break  # Only report the first overly long line to avoid noise
        return findings


class MetricsEngine:
    def __init__(self, config):
        self.config = config
        self.flake8_parser = Flake8Parser(config)
        self.file_scanner = GenericFileScanner(config)

    def run_stage(self, eligible_files):
        print(
            "\n--- [Stage 3/5] Objective Metrics, IaC & Linting ---",
            file=sys.stderr,
        )
        all_findings = []

        # 1. Flake8 (Python only)
        py_files = [f for f in eligible_files if f.endswith(".py")]
        if py_files:
            ignore_list = ",".join(self.config.get("flake8", {}).get("ignore", []))
            flake8_cmd = ["flake8", "--max-complexity=10"]
            if ignore_list:
                flake8_cmd.append(f"--ignore={ignore_list}")
            flake8_cmd.extend(py_files)
            
            stdout, _ = CommandRunner.run(flake8_cmd)
            all_findings.extend(self.flake8_parser.parse(stdout))

        # 2. Universal File Metrics, MI, and IaC Scans
        for file_path in eligible_files:
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
            except Exception as e:
                print(f"Error reading file {file_path}: {e}", file=sys.stderr)
                continue

            ext = os.path.splitext(file_path)[1]
            filename = os.path.basename(file_path)

            # Generic Size & Length
            all_findings.extend(self.file_scanner.scan_lines(file_path, lines))

            # Maintainability Index (MI)
            all_findings.extend(MaintainabilityAnalyzer.analyze(file_path, lines, ext))

            # Infrastructure-as-Code checks
            all_findings.extend(IaCScanner.scan(file_path, lines, ext, filename))

        return all_findings
