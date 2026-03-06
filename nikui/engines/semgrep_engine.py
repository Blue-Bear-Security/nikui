import os
import json
import shlex
import subprocess
import sys


class SemgrepEngine:
    def __init__(self, config, script_dir):
        self.config = config
        self.script_dir = script_dir

    def categorize_finding(self, check_id, semgrep_severity, semgrep_category=None):
        check_id_lower = check_id.lower()
        category_lower = (semgrep_category or "").lower()

        is_security = (
            "security" in check_id_lower
            or "security" in category_lower
            or semgrep_severity == "ERROR"
            or "audit" in check_id_lower
        )
        if is_security:
            return "Security Vulnerability"

        if any(kw in check_id_lower for kw in ["design", "complexity", "architecture"]):
            return "Architectural & Design Flaw"

        if any(
            kw in check_id_lower
            for kw in ["best-practice", "correctness", "convention"]
        ):
            return "Best Practices & Conventions"

        return "Code Quality & Maintainability"

    def parse_results(self, json_data):
        findings = []
        for finding in json_data.get("results", []):
            file_path = finding.get("path")
            line = finding.get("start", {}).get("line")
            check_id = finding.get("check_id")
            message = finding.get("extra", {}).get("message")
            severity = finding.get("extra", {}).get("severity")
            category_meta = finding.get("extra", {}).get("metadata", {}).get("category")

            category = self.categorize_finding(check_id, severity, category_meta)

            findings.append(
                {
                    "tool": "Semgrep",
                    "file_path": file_path,
                    "line": line,
                    "category": category,
                    "description": f"[{check_id}] {message}",
                    "severity": "High" if severity == "ERROR" else "Medium",
                }
            )
        return findings

    def run_stage(self, temp_dir):
        print(
            "\n--- [Stage 2/3] Security & Best Practices Scan (Semgrep) ---",
            file=sys.stderr,
        )
        output_file = os.path.join(temp_dir, "semgrep.json")
        configs = " ".join([f"--config {c}" for c in self.config["semgrep"]["configs"]])
        excludes = " ".join(
            [f"--exclude {d}/" for d in self.config["exclusions"]["directories"]]
        )

        command = (
            f"semgrep scan {configs} {excludes} --json > {shlex.quote(output_file)}"
        )
        try:
            subprocess.run(
                command, shell=True, check=False, capture_output=True, text=True
            )
            if os.path.exists(output_file):
                with open(output_file, "r", encoding="utf-8") as f:
                    return self.parse_results(json.load(f))
        except Exception as e:
            print(f"Error running Semgrep: {e}", file=sys.stderr)
        return []
