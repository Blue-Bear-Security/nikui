import argparse
import sys
import os
from nikui.nikui import main as smell_main
from nikui.generate_report import main as report_main


def main():
    parser = argparse.ArgumentParser(
        prog="nikui", description="Nikui: Bear-powered technical debt analyzer."
    )
    subparsers = parser.add_subparsers(dest="command", help="Subcommands")

    # Smell subcommand
    smell_parser = subparsers.add_parser("smell", help="Execute the code smell scan")
    smell_parser.add_argument("repo_path", help="Path to the repository to analyze")
    smell_parser.add_argument(
        "--config", default="config.json", help="Path to config file"
    )
    smell_parser.add_argument(
        "--output",
        default=None,
        help="Output JSON file (defaults to nikui_results/ folder)",
    )
    smell_parser.add_argument(
        "--stages",
        nargs="+",
        choices=["ollama", "semgrep", "metrics", "duplication", "dependency"],
        help="Specific stages to run (default: all)",
    )

    # Report subcommand
    report_parser = subparsers.add_parser(
        "report", help="Generate the prioritized report"
    )
    report_parser.add_argument("repo_path", help="Path to the repository to analyze")
    report_parser.add_argument(
        "--json",
        default=None,
        help="Input JSON findings (defaults to latest in nikui_results/)",
    )
    report_parser.add_argument("--html", default=None, help="Output HTML report file")
    report_parser.add_argument(
        "--config", default="config.json", help="Path to config file"
    )

    args = parser.parse_args()

    if args.command == "smell":
        output_arg = args.output if args.output else "analysis_report.json"
        sys.argv = [
            sys.argv[0],
            args.repo_path,
            "--config",
            args.config,
            "--output",
            output_arg,
        ]
        if args.stages:
            sys.argv.extend(["--stages"] + args.stages)
        smell_main()
    elif args.command == "report":
        json_input = args.json
        if not json_input:
            import glob

            # Search in the target repository's results folder
            repo_results_pattern = os.path.join(
                args.repo_path, "nikui_results", "*.json"
            )
            results = glob.glob(repo_results_pattern)
            if results:
                json_input = max(results, key=os.path.getmtime)
            else:
                # Fallback to local if repo-specific results aren't found
                json_input = "analysis_report.json"

        html_output = args.html if args.html else "analysis_report.html"
        sys.argv = [
            sys.argv[0],
            args.repo_path,
            "--json",
            json_input,
            "--html",
            html_output,
            "--config",
            args.config,
        ]
        report_main()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
