# 🐻 Nikui Bear

**Nikui** is a bear-powered code smell and technical debt analyzer. It sniffs out hotspots in your repository by combining local LLM analysis, static security scans, structural duplication detection, and objective code metrics.

## 🚀 Features

- **🧠 Local LLM Analysis:** Samples your code for deep semantic issues like SOLID violations, Silent Fails, and God Objects. Works with any OpenAI-compatible backend (MLX, LM Studio, Ollama).
- **🛡️ Full Static Scan:** Comprehensive security and best-practice analysis using Semgrep.
- **👯 Verified Duplication:** Two-tier structural duplication detection using Simhash candidates verified by local LLM for zero-noise results.
- **📊 Objective Metrics:** Detects oversized files, complex functions, and forgotten debug logs.
- **🔥 Hotspot Matrix:** Prioritizes fixes using the **Stench × Churn** formula.
- **🌐 Interactive Report:** Generates a sortable HTML report with expandable findings.

## 🛠️ Setup

### 1. Install Dependencies
```bash
# Install uv if you haven't
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install project
uv sync
```

### 2. Start a Local LLM Backend

Nikui uses any **OpenAI-compatible** local LLM server. Set `base_url` and `model` in `config.json` to match your backend.

#### Option A: MLX (Apple Silicon — recommended for Mac)
```bash
pip install mlx-lm
mlx_lm.server --model mlx-community/Qwen2.5-Coder-14B-Instruct-4bit --port 8080
```
`config.json`:
```json
"ollama": {
  "base_url": "http://localhost:8080/v1",
  "model": "mlx-community/Qwen2.5-Coder-14B-Instruct-4bit"
}
```

#### Option B: LM Studio (Windows / Linux / Mac)
1. Download [LM Studio](https://lmstudio.ai), load a model, and start the local server (default port 1234).

`config.json`:
```json
"ollama": {
  "base_url": "http://localhost:1234/v1",
  "model": "qwen2.5-coder-14b-instruct"
}
```

#### Option C: Ollama
```bash
ollama pull qwen2.5-coder:14b
ollama serve
```
`config.json`:
```json
"ollama": {
  "base_url": "http://localhost:11434/v1",
  "model": "qwen2.5-coder:14b"
}
```

#### Option D: OpenAI (fastest — recommended for large repos)
`config.json`:
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
uv run nikui smell <repo_path>
```

> **LLM is optional.** If no backend is running, the semantic analysis and duplication verification stages are skipped gracefully.

## 📖 Usage

### 1. Run the analysis
```bash
# Full scan
uv run nikui smell <repo_path>

# Targeted scan (only specific engines)
uv run nikui smell <repo_path> --stages duplication semgrep

# Save to a specific JSON file
uv run nikui smell <repo_path> --output my_scan.json
```

### 2. Generate the report
```bash
# Generate HTML report from the latest results
uv run nikui report <repo_path>

# Generate from a specific JSON file
uv run nikui report <repo_path> --json nikui_results/my_scan.json --html report.html
```

## 🧮 How it Works: The Hotspot Matrix

Nikui doesn't just list bugs; it prioritizes them using a **Hotspot Score**:

`Hotspot Score = Stench × Churn`

- **Stench:** The weighted sum of all findings in a file. Weights are defined in `config.json` (e.g., Security = 50, Architectural Flaw = 20).
- **Churn:** The number of times a file has been modified in Git history.
- **Result:** A complex file that changes frequently gets a massive score, while a "smelly" file that hasn't been touched in years is deprioritized.

## ⚙️ Configuration

- **config.json:** Define exclusion patterns, tool-specific settings (like Flake8 ignores), and stench weights.
- **nikui/prompts/:** Customize the expert rubrics used by the LLM:
    - `smell_analysis.md`: Rubric for deep semantic code smells.
    - `duplication_verification.md`: Rubric for two-tier duplication verification.
- **nikui_results/:** All scans and reports are automatically saved here with timestamps.

## 🤝 Contributing

Contributions are welcome! To get started:

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

## 📄 License

Apache 2.0

---
Created by [**amirshk**](https://github.com/amirshk)
