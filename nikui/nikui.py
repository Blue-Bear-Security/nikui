import argparse
import json
import sys
import os
import time
import subprocess

from nikui.utils import is_excluded
from nikui.engines.ollama_engine import OllamaEngine
from nikui.engines.semgrep_engine import SemgrepEngine
from nikui.engines.metrics_engine import MetricsEngine
from nikui.engines.duplication_engine import DuplicationEngine
from nikui.engines.dependency_engine import DependencyEngine


def load_config(config_path):
    if not os.path.exists(config_path):
        bundled = os.path.join(os.path.dirname(__file__), "default_config.json")
        print(f"Warning: {config_path} not found. Using bundled default config.", file=sys.stderr)
        config_path = bundled
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_modified_files(base):
    """Returns a list of files modified between current HEAD and base branch/commit."""
    try:
        # Get list of changed files
        result = subprocess.run(
            ["git", "diff", "--name-only", base],
            capture_output=True,
            text=True,
            check=True
        )
        files = [f.strip() for f in result.stdout.splitlines() if f.strip()]
        # Filter out deleted files
        return [f for f in files if os.path.exists(f)]
    except Exception as e:
        print(f"Error getting git diff: {e}", file=sys.stderr)
        return None


def main():
    parser = argparse.ArgumentParser(prog="nikui")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Smell command
    smell_parser = subparsers.add_parser("smell")
    smell_parser.add_argument("repo_path")
    smell_parser.add_argument("--config", default=".nikui/config.json")
    smell_parser.add_argument("--output", default="analysis_report.json")
    smell_parser.add_argument("--diff", help="Only scan files changed since this branch/commit (e.g. origin/main)")
    smell_parser.add_argument(
        "--stages",
        nargs="+",
        choices=["ollama", "semgrep", "metrics", "duplication", "dependency"],
        default=["ollama", "semgrep", "metrics", "duplication", "dependency"],
    )

    # Report command
    report_parser = subparsers.add_parser("report")
    report_parser.add_argument("repo_path")
    report_parser.add_argument("--json")
    report_parser.add_argument("--html", default=None)
    report_parser.add_argument("--markdown", default=None)
    report_parser.add_argument("--config", default=".nikui/config.json")

    args = parser.parse_args()

    if args.command == "report":
        from nikui.generate_report import generate_reports
        generate_reports(args.repo_path, json_path=args.json, html_path=args.html, config_path=args.config, markdown_path=args.markdown)
        return

    # 'smell' command logic
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    
    if not os.path.isdir(args.repo_path):
        print(f"Error: {args.repo_path} is not a directory.")
        sys.exit(1)
        
    os.chdir(args.repo_path)
    config = load_config(args.config)
    
    temp_dir = os.path.join(os.getcwd(), ".nikui_tmp")
    os.makedirs(temp_dir, exist_ok=True)

    # Handle --diff
    modified_files = None
    if args.diff:
        modified_files = get_modified_files(args.diff)
        if modified_files is not None:
            print(f"Diff Mode: Only analyzing {len(modified_files)} modified files.", file=sys.stderr)

    print(
        f"Nikui Analysis Plan:\n"
        f"1. Deep Semantic Analysis (Ollama)\n"
        f"2. Security & Best Practices (Semgrep)\n"
        f"3. Objective Metrics (Flake8/Regex)\n"
        f"4. Code Duplication (Simhash)\n"
        f"5. Dependency & Coupling (Graph)\n"
        f"Target: {args.repo_path}"
    )

    eligible_files = []
    valid_exts = (".py", ".js", ".ts", ".tsx", ".go", ".yml", ".yaml", ".tf", ".sh")
    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if not is_excluded(os.path.join(root, d), config)]
        for f in files:
            path = os.path.join(root, f)
            if not is_excluded(path, config) and (path.endswith(valid_exts) or f == "Dockerfile"):
                eligible_files.append(path)

    # In diff mode, for Stage 1, 2, 3 we only scan modified files
    files_to_scan = [f for f in eligible_files if f in modified_files] if modified_files is not None else eligible_files

    all_findings = []

    # Stage 1: Ollama
    ollama = None
    if "ollama" in args.stages:
        print("\n--- [Stage 1/5] Deep Semantic Analysis (LLM) ---", file=sys.stderr)
        ollama = OllamaEngine(config, script_dir, project_root)
        all_findings.extend(ollama.run_stage(files_to_scan))
    elif "duplication" in args.stages:
        ollama = OllamaEngine(config, script_dir, project_root)

    # Stage 2: Semgrep
    if "semgrep" in args.stages:
        # Note: SemgrepEngine currently scans the whole dir. 
        # We'll pass the files_to_scan to it if possible.
        semgrep = SemgrepEngine(config, script_dir)
        all_findings.extend(semgrep.run_stage(temp_dir, files_to_scan if modified_files else None))

    # Stage 3: Metrics
    if "metrics" in args.stages:
        metrics = MetricsEngine(config)
        all_findings.extend(metrics.run_stage(files_to_scan))

    # Stage 4: Duplication
    if "duplication" in args.stages:
        duplication = DuplicationEngine(config)
        all_findings.extend(duplication.run_stage(eligible_files, ollama=ollama, modified_files=modified_files))

    # Stage 5: Dependency
    if "dependency" in args.stages:
        dependency = DependencyEngine(config)
        # Dependency usually needs all files to build the graph, 
        # but we might want to filter results to modified files only.
        results = dependency.run_stage(eligible_files)
        if modified_files is not None:
            results = [r for r in results if r["file_path"] in modified_files]
        all_findings.extend(results)

    # Ensure nikui_results directory exists
    nikui_results_dir = os.path.join(os.getcwd(), "nikui_results")
    os.makedirs(nikui_results_dir, exist_ok=True)

    repo_name = os.path.basename(os.path.abspath(args.repo_path)) or "repo"
    timestamp = time.strftime("%Y%m%d_%H%M")

    # Determine final output path
    if args.output == "analysis_report.json":
        final_output_path = os.path.join(
            nikui_results_dir, f"{repo_name}_{timestamp}.json"
        )
    else:
        # If output path is provided, ensure it's relative to the project root or absolute
        if os.path.isabs(args.output):
            final_output_path = args.output
        else:
            final_output_path = os.path.abspath(os.path.join(project_root, args.output))

    # Ensure parent directory of final_output_path exists
    os.makedirs(os.path.dirname(final_output_path), exist_ok=True)

    with open(final_output_path, "w", encoding="utf-8") as f:
        json.dump(all_findings, f, indent=2)

    print(f"\n✅ Analysis complete. Results saved to {final_output_path}")


if __name__ == "__main__":
    main()
