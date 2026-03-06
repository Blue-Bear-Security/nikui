import os
import re
import json
import random
import requests
import sys

class OllamaEngine:
    def __init__(self, config, script_dir, project_root):
        self.config = config
        self.script_dir = script_dir
        self.project_root = project_root
        self.model = config.get("ollama", {}).get("model", "qwen2.5-coder:7b")
        self.url = "http://localhost:11434/api/generate"
        self.sampling_rate = config.get("ollama", {}).get("sampling_rate", 0.01)

    def is_running(self):
        try:
            response = requests.get("http://localhost:11434", timeout=2)
            return response.status_code == 200
        except requests.exceptions.ConnectionError:
            print("Warning: Ollama service is not reachable (connection refused).", file=sys.stderr)
            return False
        except Exception as e:
            print(f"Warning: Unexpected error checking Ollama: {e}", file=sys.stderr)
            return False

    def _load_prompt(self, prompt_path, filename, code):
        if not os.path.exists(prompt_path):
            return None
        with open(prompt_path, "r", encoding="utf-8") as f:
            template = f.read()
        return template.format(filename=filename, code=code)

    def analyze_file(self, file_path, prompt_path):
        """Analyzes a single file using the LLM."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                code = f.read()
        except Exception as e:
            print(f"Error reading file {file_path}: {e}", file=sys.stderr)
            return []

        prompt = self._load_prompt(prompt_path, file_path, code)
        if not prompt:
            print(f"Error: Prompt template not found at {prompt_path}", file=sys.stderr)
            return []

        try:
            response = requests.post(
                self.url, 
                json={"model": self.model, "prompt": prompt, "stream": False}, 
                timeout=120
            )
            response.raise_for_status()
            raw_output = response.json().get("response", "")
            return self._parse_output(file_path, raw_output)
        except Exception as e:
            print(f"Error during Ollama analysis for {file_path}: {e}", file=sys.stderr)
            return []

    def _parse_output(self, file_path, raw_output):
        findings = []
        json_array_regex = r"\[\s*(?:\{.*?\}(?:,\s*\{.*?\})*)?\s*\]"
        matches = re.finditer(json_array_regex, raw_output, re.DOTALL)
        
        category_map = {
            "Deep Nesting": "Code Quality & Maintainability",
            "Poor Naming": "Best Practices & Conventions",
            "Violations of SOLID principles": "Architectural & Design Flaw",
            "God Objects / Shotgun Surgery": "Architectural & Design Flaw",
            "Improper Error Handling & Silent Failures": "Improper Error Handling & Silent Failures"
        }

        for match in matches:
            try:
                file_findings = json.loads(match.group(0))
                if isinstance(file_findings, list):
                    for fnd in file_findings:
                        findings.append({
                            "tool": "Ollama",
                            "file_path": file_path,
                            "line": None,
                            "category": category_map.get(fnd.get("category"), "Code Quality & Maintainability"),
                            "severity": fnd.get("severity", "Medium"),
                            "description": fnd.get("description", "")
                        })
                    return findings
            except Exception as e:
                print(f"Error parsing Ollama result for {file_path}: {e}", file=sys.stderr)
                continue
        return findings

    def run_stage(self, eligible_files):
        """Orchestrates the LLM stage for a list of files."""
        if not self.is_running():
            print("⚠️  Ollama not running. Skipping stage.", file=sys.stderr)
            return []

        sample_size = max(1, int(len(eligible_files) * self.sampling_rate)) if eligible_files else 0
        sampled_files = random.sample(eligible_files, sample_size)
        
        print(f"Analyzing {sample_size} files ({self.sampling_rate*100}% sample of {len(eligible_files)} total)...", file=sys.stderr)
        
        all_findings = []
        prompt_path = os.path.join(self.project_root, "prompt.md")
        
        for i, p in enumerate(sampled_files):
            sys.stderr.write(f"\rProgress: [{i+1}/{sample_size}] files analyzed...")
            sys.stderr.flush()
            all_findings.extend(self.analyze_file(p, prompt_path))
            
        print("", file=sys.stderr)
        return all_findings
