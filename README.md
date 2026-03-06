# 🐻 Nikui

**Nikui** is a bear-powered code smell and technical debt analyzer. It sniffs out hotspots in your repository by combining local LLM analysis, static security scans, and objective code metrics.

## 🚀 Features

- **🧠 Local LLM Analysis (Ollama):** Samples 5% of your code for deep semantic issues like SOLID violations, Silent Fails, and God Objects.
- **🛡️ Full Static Scan:** Comprehensive security and best-practice analysis using Semgrep (`owasp-top-10`, `security-audit`, `secrets`).
- **📊 Objective Metrics:** Detects oversized files, complex functions (Cyclomatic Complexity), and forgotten debug logs.
- **🔥 Hotspot Matrix:** Prioritizes fixes using the **Stench × Churn** formula—targeting the messiest parts of your codebase that change the most often.
- **🌐 Interactive Report:** Generates a sortable HTML report with expandable findings.

## 🧮 The Stench Score

Nikui calculates a "Stench Score" for every file:
`Stench = Σ (Category Weight × Severity Multiplier)`

- **Weights:** Security (50), Silent Fails (30), Architecture (20), Code Quality (5).
- **Multipliers:** High (3x), Medium (2x), Low (1x).

## 🛠️ Setup

1. **Install Ollama:** [ollama.com](https://ollama.com)
2. **Pull the model:** `ollama pull qwen2.5-coder:7b`
3. **Install uv:** `curl -LsSf https://astral.sh/uv/install.sh | sh`

## 📖 Usage

```bash
# 1. Start Ollama
ollama serve

# 2. Run the analysis
uv run python3 src/nikui.py

# 3. Generate the report
uv run python3 src/generate_report.py

# 4. View results
open analysis_report.html
```

## 📄 License

MIT

---
Created by **amirshk**
