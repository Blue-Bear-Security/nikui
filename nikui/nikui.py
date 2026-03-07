import argparse
import json
import sys
import os
import time

from nikui.utils import is_excluded
from nikui.engines.ollama_engine import OllamaEngine
from nikui.engines.semgrep_engine import SemgrepEngine
from nikui.engines.metrics_engine import MetricsEngine
from nikui.engines.duplication_engine import DuplicationEngine


def load_config(config_path):
    if not os.path.exists(config_path):
        print(f"Error: {config_path} not found.")
        sys.exit(1)
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(prog="nikui")
    parser.add_argument("repo_path")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--output", default="analysis_report.json")
    args = parser.parse_args()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    if not os.path.isdir(args.repo_path):
        print(f"Error: {args.repo_path} is not a directory.")
        sys.exit(1)
    os.chdir(args.repo_path)
    config = load_config(os.path.abspath(os.path.join(project_root, args.config)))
    temp_dir = os.path.join(os.getcwd(), ".nikui_tmp")
    os.makedirs(temp_dir, exist_ok=True)
    print(
        f"Nikui Analysis Plan:\n1. Deep Semantic Analysis (Ollama)\n2. Security & Best Practices (Semgrep)\n3. Objective Metrics (Flake8/GoVet/Regex)\nTarget: {args.repo_path}"
    )

    eligible_files = []
    for root, _, files in os.walk("."):
        for f in files:
            path = os.path.join(root, f)
            if not is_excluded(path, config) and path.endswith(
                (".py", ".js", ".ts", ".tsx", ".go")
            ):
                eligible_files.append(path)

    all_findings = []

    # Stage 1: Ollama
    print("\n--- [Stage 1/3] Deep Semantic Analysis (LLM) ---", file=sys.stderr)
    ollama = OllamaEngine(config, script_dir, project_root)
    all_findings.extend(ollama.run_stage(eligible_files))

    # Stage 2: Semgrep
    semgrep = SemgrepEngine(config, script_dir)
    all_findings.extend(semgrep.run_stage(temp_dir))
    # Stage 3: Metrics
    metrics = MetricsEngine(config)
    all_findings.extend(metrics.run_stage(["."]))

    # Stage 4: Duplication
    duplication = DuplicationEngine(config)
    all_findings.extend(duplication.run_stage(["."]))

    # Ensure results directory exists

    results_dir = os.path.join(os.getcwd(), "results")
    os.makedirs(results_dir, exist_ok=True)

    repo_name = os.path.basename(os.path.abspath(args.repo_path)) or "repo"
    timestamp = time.strftime("%Y%m%d_%H%M")

    # Default output path if none provided
    if args.output == "analysis_report.json":
        final_output_path = os.path.join(results_dir, f"{repo_name}_{timestamp}.json")
    else:
        final_output_path = os.path.abspath(os.path.join(project_root, args.output))

    with open(final_output_path, "w", encoding="utf-8") as f:
        json.dump(all_findings, f, indent=2)

    print(f"\n✅ Analysis complete. Results saved to {final_output_path}")


if __name__ == "__main__":
    main()
