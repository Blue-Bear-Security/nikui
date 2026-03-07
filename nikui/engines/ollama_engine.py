import os
import re
import json
import random
import requests
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed


class LLMClient:
    """OpenAI-compatible client. Works with OpenAI, MLX, LM Studio, Ollama (/v1), etc."""

    def __init__(self, model, base_url="http://localhost:8080/v1", api_key=None):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.headers = {"Content-Type": "application/json"}
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"

    def is_running(self):
        try:
            response = requests.get(f"{self.base_url}/models", headers=self.headers, timeout=2)
            # 401 means the server is reachable but needs auth — treat as running
            return response.status_code in (200, 401)
        except requests.exceptions.ConnectionError:
            print(
                f"Warning: LLM service is not reachable at {self.base_url}.",
                file=sys.stderr,
            )
            return False
        except Exception as e:
            print(f"Warning: Unexpected error checking LLM service: {e}", file=sys.stderr)
            return False

    def generate(self, prompt, _retries=4):
        for attempt in range(_retries):
            try:
                response = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers=self.headers,
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 1024,
                        "stream": False,
                    },
                    timeout=180,
                )
                if response.status_code == 429:
                    wait = int(response.headers.get("Retry-After", 2 ** attempt))
                    print(f"\nRate limited. Retrying in {wait}s...", file=sys.stderr)
                    time.sleep(wait)
                    continue
                response.raise_for_status()
                message = response.json()["choices"][0]["message"]
                return message.get("content") or message.get("reasoning", "")
            except requests.exceptions.HTTPError:
                raise
            except Exception as e:
                print(f"Error during LLM API request: {e}", file=sys.stderr)
                return ""
        print("Error: LLM request failed after retries (rate limit).", file=sys.stderr)
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
        llm_config = config.get("ollama", {})
        self.model = llm_config.get("model", "qwen2.5-coder:14b")
        self.sampling_rate = llm_config.get("sampling_rate", 0.01)
        base_url = llm_config.get("base_url", "http://localhost:8080/v1")
        api_key = llm_config.get("api_key") or os.environ.get("OPENAI_API_KEY")
        self.client = LLMClient(self.model, base_url, api_key)

    def _number_code(self, code):
        """Prefixes each line of code with its line number."""
        lines = code.splitlines()
        numbered = [f"{i+1}: {line}" for i, line in enumerate(lines)]
        return "\n".join(numbered)

    def _strip_markdown_fence(self, text):
        """Remove a single markdown code fence wrapper if present."""
        text = text.strip()
        match = re.match(r"^```(?:json)?\s*([\s\S]*?)\s*```$", text)
        if match:
            return match.group(1).strip()
        return text

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
            data = json.loads(self._strip_markdown_fence(raw_output))
            return data.get("status") == "DUPLICATE", data.get("reason", "")
        except (json.JSONDecodeError, AttributeError):
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
        if not raw_output or not raw_output.strip():
            return []

        return self._parse_output(file_path, raw_output)

    def _parse_output(self, file_path, raw_output):
        text = self._strip_markdown_fence(raw_output)
        try:
            file_findings = json.loads(text)
        except json.JSONDecodeError as e:
            print(f"Error parsing LLM JSON for {file_path}: {e}", file=sys.stderr)
            return []

        if not isinstance(file_findings, list):
            print(f"Warning: LLM output for {file_path} is not a JSON array", file=sys.stderr)
            return []

        findings = []
        for fnd in file_findings:
            line_val = fnd.get("line_range", "N/A")
            try:
                line_display = int(str(line_val).split("-")[0])
            except (ValueError, AttributeError):
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

    def run_stage(self, eligible_files):
        """Orchestrates the LLM stage for a list of files."""
        if not self.client.is_running():
            print("⚠️  LLM service not running. Skipping stage.", file=sys.stderr)
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

        prompt_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "prompts", "smell_analysis.md"
        )

        all_findings = []
        completed = 0
        workers = self.config.get("ollama", {}).get("workers", 4)

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(self.analyze_file, p, prompt_path): p for p in sampled_files}
            for future in as_completed(futures):
                completed += 1
                sys.stderr.write(f"\rProgress: [{completed}/{sample_size}] files analyzed...")
                sys.stderr.flush()
                all_findings.extend(future.result())

        print("", file=sys.stderr)
        return all_findings
