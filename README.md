# 🐻 Nikui Bear

**Nikui** is a bear-powered code smell and technical debt analyzer. It sniffs out hotspots in your repository by combining local LLM analysis, static security scans, structural duplication detection, and objective code metrics.

## 🚀 Features

- **🧠 Local LLM Analysis (Ollama):** Samples your code for deep semantic issues like SOLID violations, Silent Fails, and God Objects.
- **🛡️ Full Static Scan:** Comprehensive security and best-practice analysis using Semgrep.
- **👯 Code Duplication:** AST-based (Python) and structural (Go, TS, JS) duplication detection using Simhash.
- **📊 Objective Metrics:** Detects oversized files, complex functions, and forgotten debug logs.
- **🔥 Hotspot Matrix:** Prioritizes fixes using the **Stench × Churn** formula.
- **🌐 Interactive Report:** Generates a sortable HTML report with expandable findings.

## 🛠️ Setup

### 1. Install & Prep Ollama
Nikui requires **Ollama** to be running locally for deep analysis.
- **Install:** [ollama.com](https://ollama.com)
- **Pull Model:** `ollama pull qwen2.5-coder:7b` (or your preferred model configured in `config.json`)
- **Serve:** `ollama serve` (keep this running in a separate terminal)

### 2. Install Dependencies
```bash
# Install uv if you haven't
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install project
uv sync
```

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
- **prompt.md:** Customize the expert rubric used by the LLM to analyze your code.
- **nikui_results/:** All scans and reports are automatically saved here with timestamps.

## 📄 License

MIT

---
Created by **amirshk**
