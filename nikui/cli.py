import argparse
import sys
from nikui.nikui import main as smell_main
from nikui.generate_report import main as report_main

def main():
    parser = argparse.ArgumentParser(prog="nikui", description="Nikui: Bear-powered technical debt analyzer.")
    subparsers = parser.add_subparsers(dest="command", help="Subcommands")
    
    # Smell subcommand
    smell_parser = subparsers.add_parser("smell", help="Execute the code smell scan")
    smell_parser.add_argument("repo_path", help="Path to the repository to analyze")
    smell_parser.add_argument("--config", default="config.json", help="Path to config file")
    smell_parser.add_argument("--output", default="analysis_report.json", help="Output JSON file")
    
    # Report subcommand
    report_parser = subparsers.add_parser("report", help="Generate the prioritized report")
    report_parser.add_argument("repo_path", help="Path to the repository to analyze")
    report_parser.add_argument("--json", default="analysis_report.json", help="Input JSON findings file")
    report_parser.add_argument("--html", default="analysis_report.html", help="Output HTML report file")
    report_parser.add_argument("--config", default="config.json", help="Path to config file")
    
    args = parser.parse_args()
    
    if args.command == "smell":
        # Patch sys.argv to emulate nikui.py main() expectations
        sys.argv = [sys.argv[0], args.repo_path, "--config", args.config, "--output", args.output]
        smell_main()
    elif args.command == "report":
        # Patch sys.argv to emulate generate_report.py main() expectations
        sys.argv = [sys.argv[0], args.repo_path, "--json", args.json, "--html", args.html, "--config", args.config]
        report_main()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
