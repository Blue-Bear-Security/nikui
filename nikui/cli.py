import argparse
import sys
import os
from nikui.nikui import main as smell_run
from nikui.generate_report import generate_reports

def main():
    parser = argparse.ArgumentParser(prog="nikui", description="Nikui: Code smell and technical debt analyzer.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Smell command
    smell_parser = subparsers.add_parser("smell", help="Run the code smell analysis")
    smell_parser.add_argument("repo_path", help="Path to the repository to analyze")
    smell_parser.add_argument("--config", default=".nikui/config.json", help="Path to config file")
    smell_parser.add_argument("--output", default="analysis_report.json", help="Output JSON file")
    smell_parser.add_argument("--diff", help="Only scan files changed since this branch/commit")
    smell_parser.add_argument(
        "--stages",
        nargs="+",
        choices=["ollama", "semgrep", "metrics", "duplication", "dependency"],
        default=["ollama", "semgrep", "metrics", "duplication", "dependency"],
        help="Specific stages to run"
    )

    # Report command
    report_parser = subparsers.add_parser("report", help="Generate reports from analysis results")
    report_parser.add_argument("repo_path", help="Path to the repository")
    report_parser.add_argument("--json", help="Path to the JSON findings file")
    report_parser.add_argument("--html", default=None, help="Output HTML report path")
    report_parser.add_argument("--markdown", default=None, help="Output Markdown summary path")
    report_parser.add_argument("--config", default=".nikui/config.json", help="Path to config file")

    args = parser.parse_args()

    if args.command == "smell":
        # Call the orchestrator in nikui.py
        smell_run(args)
    elif args.command == "report":
        # Search for latest JSON if not provided
        json_input = args.json
        if not json_input:
            import glob
            results_dir = os.path.join(args.repo_path, "nikui_results")
            if os.path.exists(results_dir):
                files = glob.glob(os.path.join(results_dir, "*.json"))
                if files:
                    json_input = max(files, key=os.path.getmtime)
        
        if not json_input:
            print("Error: No JSON findings file found. Run 'nikui smell' first or provide --json.")
            sys.exit(1)

        generate_reports(
            args.repo_path,
            json_path=os.path.abspath(json_input),
            html_path=os.path.abspath(args.html) if args.html else None,
            config_path=os.path.abspath(args.config),
            markdown_path=os.path.abspath(args.markdown) if args.markdown else None
        )

if __name__ == "__main__":
    main()
