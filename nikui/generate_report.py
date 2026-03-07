import json
import os
import sys
import subprocess
import time
import shlex
import argparse
from collections import defaultdict
from nikui.utils import is_excluded


def get_git_metadata(file_path):
    """Fetches commit count and last modification time from Git."""
    try:
        quoted_path = shlex.quote(file_path)
        commit_count_cmd = f"git rev-list --count HEAD -- {quoted_path}"
        last_mod_cmd = f"git log -1 --format=%ct -- {quoted_path}"

        commit_count = int(
            subprocess.check_output(commit_count_cmd, shell=True).decode().strip()
        )
        last_mod = int(
            subprocess.check_output(last_mod_cmd, shell=True).decode().strip()
        )
        return commit_count, last_mod
    except Exception as e:
        print(
            f"Warning: Could not fetch git metadata for {file_path}: {e}",
            file=sys.stderr,
        )
        return 1, int(time.time())


class HotspotCalculator:
    """Pure logic class for calculating hotspot scores."""

    def __init__(self, config):
        self.weights = config.get("stench_weights", {})
        self.multipliers = {"High": 3.0, "Medium": 2.0, "Low": 1.0, "N/A": 1.5}

    def calculate_stench(self, findings):
        """Calculates total stench per file."""
        file_stench = defaultdict(float)
        file_counts = defaultdict(int)

        for f in findings:
            path = f.get("file_path", "Unknown")
            category = f.get("category")
            severity = f.get("severity", "N/A")

            score = self.weights.get(category, 1) * self.multipliers.get(severity, 1.5)
            file_stench[path] += score
            file_counts[path] += 1

        return file_stench, file_counts

    def score_hotspots(self, file_stench, file_counts, git_metadata):
        """Combines stench and churn into a prioritized list with economic quadrants."""
        scored_files = []
        for path, stench in file_stench.items():
            churn, last_mod = git_metadata.get(path, (1, int(time.time())))
            hotspot_score = stench * churn
            scored_files.append(
                {
                    "path": path,
                    "stench": stench,
                    "findings": file_counts[path],
                    "churn": churn,
                    "last_mod": last_mod,
                    "hotspot_score": hotspot_score,
                }
            )

        if not scored_files:
            return []

        # Calculate Averages for Quadrant mapping
        avg_stench = sum(f["stench"] for f in scored_files) / len(scored_files)
        avg_churn = sum(f["churn"] for f in scored_files) / len(scored_files)

        for f in scored_files:
            high_stench = f["stench"] > avg_stench
            high_churn = f["churn"] > avg_churn

            if high_stench and high_churn:
                f["debt_type"] = "🔥 Toxic"
            elif high_stench and not high_churn:
                f["debt_type"] = "❄️ Frozen"
            elif not high_stench and high_churn:
                f["debt_type"] = "⚡ Quick Win"
            else:
                f["debt_type"] = "✅ Healthy"

        # Return as list of tuples (path, stats) to maintain existing interface
        sorted_stats = sorted(scored_files, key=lambda x: x["hotspot_score"], reverse=True)
        return [(f["path"], f) for f in sorted_stats]


class HtmlReporter:
    """Handles only the rendering of the HTML report."""

    def __init__(self, config):
        self.config = config

    def render(self, sorted_files, findings, html_path):
        findings_by_file = defaultdict(list)
        for f in findings:
            findings_by_file[f.get("file_path", "Unknown")].append(f)

        template_path = os.path.join(os.path.dirname(__file__), "report_template.html")
        if not os.path.exists(template_path):
            print(f"Error: Template not found at {template_path}")
            return

        with open(template_path, "r", encoding="utf-8") as f:
            template = f.read()

        table_rows = []
        chart_data = []
        for idx, (path, stats) in enumerate(sorted_files):
            chart_data.append(
                {
                    "x": stats["churn"],
                    "y": stats["stench"],
                    "score": int(stats["hotspot_score"]),
                    "name": path,
                    "debt_type": stats.get("debt_type", "Unknown")
                }
            )

            table_rows.append(
                f'<tr onclick="toggleFindings({idx})" class="file-row">'
                f"<td>{path}</td><td><strong>{int(stats['hotspot_score'])}</strong></td>"
                f"<td>{int(stats['stench'])}</td><td>{stats['findings']}</td>"
                f"<td>{stats['churn']}</td><td>{stats.get('debt_type', 'Unknown')}</td></tr>"
            )

            table_rows.append(
                f'<tr id="findings-{idx}" class="findings-row"><td colspan="6"><div class="findings-content">'
            )
            for f in sorted(
                findings_by_file[path], key=lambda x: x.get("severity", "N/A")
            ):
                sev = f.get("severity", "N/A")
                tool = f.get("tool", "Unknown")
                table_rows.append(
                    f'<div class="finding-item">'
                    f'<span class="badge badge-{sev.lower()}">{sev}</span> '
                    f'<span class="badge badge-tool">{tool}</span> '
                    f'<strong>{f.get("category")}</strong>: {f.get("description")}</div>'
                )
            table_rows.append("</div></td></tr>")

        replacements = {
            "{{timestamp}}": time.strftime("%Y-%m-%d %H:%M:%S"),
            "{{total_files}}": str(len(sorted_files)),
            "{{total_findings}}": str(len(findings)),
            "{{max_hotspot}}": (
                str(int(sorted_files[0][1]["hotspot_score"])) if sorted_files else "0"
            ),
            "{{avg_churn}}": (
                f"{sum(s[1]['churn'] for s in sorted_files) / len(sorted_files):.1f}"
                if sorted_files
                else "0"
            ),
            "{{chart_data_json}}": json.dumps(chart_data),
            "{{table_rows}}": "".join(table_rows),
        }

        html_content = template
        for key, value in replacements.items():
            html_content = html_content.replace(key, value)

        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)


def generate_reports(repo_path, json_path, html_path, config_path):
    if not os.path.exists(config_path):
        print(f"Error: {config_path} missing")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    print(f"Reading findings from: {json_path}", file=sys.stderr)
    with open(json_path, "r", encoding="utf-8") as f:
        raw_findings = json.load(f)

    findings = [
        f for f in raw_findings if not is_excluded(f.get("file_path", ""), config)
    ]

    orig_cwd = os.getcwd()
    os.chdir(repo_path)

    calculator = HotspotCalculator(config)
    file_stench, file_counts = calculator.calculate_stench(findings)

    # SRP: Fetch metadata separately
    git_metadata = {}
    for path in file_stench:
        git_metadata[path] = get_git_metadata(path)

    sorted_files = calculator.score_hotspots(file_stench, file_counts, git_metadata)

    results_dir = os.path.join(os.path.abspath(repo_path), "nikui_results")
    os.makedirs(results_dir, exist_ok=True)

    if os.path.basename(html_path) == "analysis_report.html":
        if "nikui_results" in json_path:
            json_base = os.path.splitext(os.path.basename(json_path))[0]
            final_html_path = os.path.join(results_dir, f"{json_base}.html")
        else:
            repo_name = os.path.basename(os.path.abspath(repo_path)) or "repo"
            timestamp = time.strftime("%Y%m%d_%H%M")
            final_html_path = os.path.join(results_dir, f"{repo_name}_{timestamp}.html")
    else:
        final_html_path = html_path

    reporter = HtmlReporter(config)
    reporter.render(sorted_files, findings, final_html_path)

    print(f"Report generated: {final_html_path} ({len(findings)} total findings)")
    os.chdir(orig_cwd)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("repo_path")
    parser.add_argument("--json", default="analysis_report.json")
    parser.add_argument("--html", default="analysis_report.html")
    parser.add_argument("--config", default="config.json")
    args = parser.parse_args()
    generate_reports(
        args.repo_path,
        os.path.abspath(args.json),
        os.path.abspath(args.html),
        os.path.abspath(args.config),
    )


if __name__ == "__main__":
    main()
