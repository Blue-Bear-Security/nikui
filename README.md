# 🐻 Nikui Bear

**Nikui** is a bear-powered code smell and technical debt analyzer. It sniffs out hotspots in your repository by combining local LLM analysis, static security scans, and objective code metrics.

## 🚀 Features

- **🧠 Local LLM Analysis (Ollama):** Samples your code for deep semantic issues like SOLID violations, Silent Fails, and God Objects.
- **🛡️ Full Static Scan:** Comprehensive security and best-practice analysis using Semgrep.
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
curl -LsSf https://astral.sh/uv/install.sh \| sh

# Install project
uv sync
```

## 📖 Usage

```bash
# 1. Run the analysis on a target repository
uv run nikui smell <repo_path>

# 2. Generate the interactive report
uv run nikui report <repo_path>

# 3. View results
open analysis_report.html
```

## ⚙️ Configuration

- **config.json:** Define exclusion patterns, stench weights, and tool settings.
- **prompt.md:** Customize the expert rubric used by the LLM to analyze your code.

## 📄 License

MIT

---
Created by **amirshk**
