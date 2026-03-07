# Nikui

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.13%2B-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/github/actions/workflow/status/Blue-Bear-Security/nikui/test.yml?label=tests)](https://github.com/Blue-Bear-Security/nikui/actions)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

**Nikui** is a code smell and technical debt analyzer. It scans a repository and produces a prioritized hotspot report by combining LLM semantic analysis, static security scanning, structural duplication detection, and objective code metrics.

## Features

- **LLM Semantic Analysis:** Detects SOLID violations, silent failures, god objects, and other deep structural issues. Works with any OpenAI-compatible backend (OpenAI, MLX, LM Studio, Ollama).
- **Static Security Scan:** Comprehensive security and best-practice analysis via Semgrep.
- **Verified Duplication:** Two-tier structural detection using Simhash candidates verified by LLM to eliminate noise.
- **Objective Metrics:** Complexity scores, oversized files, and debug log detection via Flake8.
- **Hotspot Matrix:** Prioritizes findings using `Stench × Churn` — a complex file that changes frequently ranks higher than a smelly file no one touches.
- **Interactive Report:** Sortable HTML report with expandable findings per file.

## Setup

### 1. Install Dependencies
```bash
# Install uv if you haven't
curl -LsSf https://astral.sh/uv/install.sh | sh

uv sync
```

### 2. Configure an LLM Backend

Nikui works with any **OpenAI-compatible** LLM server. Set `base_url` and `model` in `config.json`.

#### Option A: OpenAI (fastest — recommended for large repos)
```json
"ollama": {
  "base_url": "https://api.openai.com/v1",
  "model": "gpt-4.1-mini",
  "workers": 4
}
```
Set your key as an environment variable — **never put it in `config.json`**:
```bash
export OPENAI_API_KEY=sk-...
```

#### Option B: MLX (Apple Silicon)
```bash
pip install mlx-lm
mlx_lm.server --model mlx-community/Qwen2.5-Coder-14B-Instruct-4bit --port 8080
```
```json
"ollama": {
  "base_url": "http://localhost:8080/v1",
  "model": "mlx-community/Qwen2.5-Coder-14B-Instruct-4bit"
}
```

#### Option C: LM Studio (Windows / Linux / Mac)
Download [LM Studio](https://lmstudio.ai), load a model, and start the local server (default port 1234).
```json
"ollama": {
  "base_url": "http://localhost:1234/v1",
  "model": "qwen2.5-coder-14b-instruct"
}
```

#### Option D: Ollama
```bash
ollama pull qwen2.5-coder:14b
ollama serve
```
```json
"ollama": {
  "base_url": "http://localhost:11434/v1",
  "model": "qwen2.5-coder:14b"
}
```

> **LLM is optional.** If no backend is running, the semantic analysis and duplication verification stages are skipped gracefully.

## Usage

```bash
# Full scan
uv run nikui smell <repo_path>

# Targeted scan (specific engines only)
uv run nikui smell <repo_path> --stages duplication semgrep

# Save to a specific output file
uv run nikui smell <repo_path> --output my_scan.json

# Generate HTML report from the latest scan
uv run nikui report <repo_path>

# Generate from a specific JSON file
uv run nikui report <repo_path> --json nikui_results/my_scan.json --html report.html
```

## How It Works: The Hotspot Matrix

`Hotspot Score = Stench × Churn`

- **Stench:** Weighted sum of all findings in a file. Weights are configurable in `config.json` (e.g., Security = 50, Architectural Flaw = 20).
- **Churn:** Number of times the file has been modified in Git history.
- **Result:** Files classified into quadrants — Toxic, Frozen, Quick Win, or Healthy.

## Configuration

- **`config.json`** — exclusion patterns, LLM settings, Semgrep rulesets, Flake8 ignores, stench weights
- **`nikui/prompts/`** — LLM rubrics for smell detection and duplication verification
- **`nikui_results/`** — all scans and reports saved automatically with timestamps

## Contributing

Contributions are welcome. To get started:

1. Fork the repo and create a branch
2. Install dependencies: `uv sync`
3. Run tests before and after your change: `uv run pytest`
4. Run the linter: `uv run flake8 nikui/`
5. Open a pull request with a clear description of what you changed and why

Good areas to contribute:
- New smell detection engines
- Prompt improvements (`nikui/prompts/`)
- Support for additional languages in the dependency engine
- Report UI enhancements (`nikui/report_template.html`)

## License

Apache 2.0 — see [LICENSE](LICENSE)

---
Created by [**amirshk**](https://github.com/amirshk)
