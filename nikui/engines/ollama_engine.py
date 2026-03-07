import os
import re
import json
import random
import requests
import sys


class OllamaClient:
    def __init__(self, model):
        self.model = model
        self.url = "http://localhost:11434/api/generate"

    def is_running(self):
        try:
            response = requests.get("http://localhost:11434", timeout=2)
            return response.status_code == 200
        except requests.exceptions.ConnectionError:
            print(
                "Warning: Ollama service is not reachable (connection refused).",
                file=sys.stderr,
            )
            return False
        except Exception as e:
            print(f"Warning: Unexpected error checking Ollama: {e}", file=sys.stderr)
            return False

    def generate(self, prompt):
        try:
            response = requests.post(
                self.url,
                json={"model": self.model, "prompt": prompt, "stream": False},
                timeout=180,
            )
            response.raise_for_status()
            return response.json().get("response", "")
        except Exception as e:
            print(f"Error during Ollama API request: {e}", file=sys.stderr)
            return ""


class PromptLoader:
    @staticmethod
    def load(prompt_path, **kwargs):
        if not os.path.exists(prompt_path):
            return None
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                template = f.read()
            return template.format(**kwargs)
        except Exception as e:
            print(f"Error loading prompt: {e}", file=sys.stderr)
            return None


class OllamaEngine:
    def __init__(self, config, script_dir, project_root):
        self.config = config
        self.script_dir = script_dir
        self.project_root = project_root
        self.model = config.get("ollama", {}).get("model", "qwen2.5-coder:7b")
        self.sampling_rate = config.get("ollama", {}).get("sampling_rate", 0.01)
        self.client = OllamaClient(self.model)

    def _number_code(self, code):
        """Prefixes each line of code with its line number."""
        lines = code.splitlines()
        numbered = [f"{i+1}: {line}" for i, line in enumerate(lines)]
        return "\n".join(numbered)

    def verify_duplication(self, file_a, code_a, file_b, code_b):
        """Uses LLM to verify if two blocks are actually duplicates."""
        prompt_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "prompts",
            "duplication_verification.md",
        )
        prompt = PromptLoader.load(
            prompt_path, file_a=file_a, code_a=code_a, file_b=file_b, code_b=code_b
        )
        if not prompt:
            return True, "Template missing, assuming duplicate"

        raw_output = self.client.generate(prompt)
        if not raw_output:
            return True, "LLM failed, assuming duplicate"

        try:
            # Clean possible markdown wrap
            clean_json = re.search(r"\{.*\}", raw_output, re.DOTALL)
            if clean_json:
                data = json.loads(clean_json.group(0))
                return data.get("status") == "DUPLICATE", data.get("reason", "")
        except Exception:
            pass
        return True, "Parse failed, assuming duplicate"

    def analyze_file(self, file_path, prompt_path):
        """Analyzes a single file using the LLM."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                code = f.read()
        except Exception as e:
            print(f"Error reading file {file_path}: {e}", file=sys.stderr)
            return []

        # New: Send code with line numbers for the improved prompt
        numbered_code = self._number_code(code)
        prompt = PromptLoader.load(
            prompt_path, filename=file_path, line_numbered_code=numbered_code
        )
        if not prompt:
            print(
                f"Error: Prompt template not found or invalid at {prompt_path}",
                file=sys.stderr,
            )
            return []

        raw_output = self.client.generate(prompt)
        if not raw_output:
            return []

        return self._parse_output(file_path, raw_output)

    def _parse_output(self, file_path, raw_output):
        findings = []
        # Look for JSON array block
        json_array_regex = r"\[\s*\{.*\}\s*\]"
        match = re.search(json_array_regex, raw_output, re.DOTALL)

        if not match:
            return []

        try:
            file_findings = json.loads(match.group(0))
            if isinstance(file_findings, list):
                for fnd in file_findings:
                    # Map 'line_range' to 'line' for backward compatibility with dashboard
                    line_val = fnd.get("line_range", "N/A")
                    try:
                        # Try to extract the first number from "10-20" or similar
                        line_display = int(str(line_val).split("-")[0])
                    except:
                        line_display = None

                    findings.append(
                        {
                            "tool": "Ollama",
                            "file_path": file_path,
                            "line": line_display,
                            "line_range": line_val,
                            "category": fnd.get("category", "Code Quality"),
                            "severity": fnd.get("severity", "Medium"),
                            "description": fnd.get("description", ""),
                        }
                    )
                return findings
        except Exception as e:
            print(f"Error parsing Ollama result for {file_path}: {e}", file=sys.stderr)

        return findings

    def run_stage(self, eligible_files):
        """Orchestrates the LLM stage for a list of files."""
        if not self.client.is_running():
            print("⚠️  Ollama not running. Skipping stage.", file=sys.stderr)
            return []

        sample_size = (
            max(1, int(len(eligible_files) * self.sampling_rate))
            if eligible_files
            else 0
        )
        sampled_files = random.sample(eligible_files, sample_size)

        print(
            f"Analyzing {sample_size} files ({self.sampling_rate*100}% sample of {len(eligible_files)} total)...",
            file=sys.stderr,
        )

        all_findings = []
        prompt_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "prompts", "smell_analysis.md"
        )

        for i, p in enumerate(sampled_files):
            sys.stderr.write(f"\rProgress: [{i+1}/{sample_size}] files analyzed...")
            sys.stderr.flush()
            all_findings.extend(self.analyze_file(p, prompt_path))

        print("", file=sys.stderr)
        return all_findings
