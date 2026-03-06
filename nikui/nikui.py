import argparse
import json
import subprocess
import sys
import os
import re
import random
import fnmatch
import shlex
import requests
import time

def is_ollama_running():
    try:
        response = requests.get("http://localhost:11434", timeout=2)
        return response.status_code == 200
    except requests.exceptions.ConnectionError:
        print("Warning: Ollama service is not reachable (connection refused).", file=sys.stderr)
        return False
    except Exception as e:
        print(f"Warning: Unexpected error checking Ollama: {e}", file=sys.stderr)
        return False

def load_config(config_path):
    if not os.path.exists(config_path): print(f"Error: {config_path} not found."); sys.exit(1)
    with open(config_path, "r", encoding="utf-8") as f: return json.load(f)

def is_excluded(filepath, config):
    norm_path = os.path.normpath(filepath)
    parts = norm_path.split(os.sep)
    for d in config["exclusions"]["directories"]:
        if d in parts: return True
    for p in config["exclusions"]["patterns"]:
        if fnmatch.fnmatch(norm_path, p) or fnmatch.fnmatch(os.path.basename(norm_path), p): return True
    return False

def run_command(command, description, capture_output=True, check=True, silent=False):
    if not silent: print(f"Running: {description}...", file=sys.stderr)
    try:
        result = subprocess.run(command, shell=True, stdout=subprocess.PIPE if capture_output else None, stderr=None, text=True, check=check, cwd=os.getcwd(), encoding="utf-8")
        return result.stdout if capture_output else ""
    except: return ""

def _process_ollama_file_output(file_path, raw_output_block, all_findings_list):
    json_array_regex = r"\[\s*(?:\{.*?\}(?:,\s*\{.*?\})*)?\s*\]"
    matches = re.finditer(json_array_regex, raw_output_block, re.DOTALL)
    for match in matches:
        try:
            file_findings = json.loads(match.group(0))
            if isinstance(file_findings, list):
                for finding in file_findings:
                    category_map = {
                        "Deep Nesting": "Code Quality & Maintainability",
                        "Poor Naming": "Best Practices & Conventions",
                        "Violations of SOLID principles": "Architectural & Design Flaw",
                        "God Objects / Shotgun Surgery": "Architectural & Design Flaw",
                        "Improper Error Handling & Silent Failures": "Improper Error Handling & Silent Failures"
                    }
                    all_findings_list.append({
                        "tool": "Ollama",
                        "file_path": file_path,
                        "line": None,
                        "category": category_map.get(finding.get("category"), "Code Quality & Maintainability"),
                        "severity": finding.get("severity", "Medium"),
                        "description": finding.get("description", "")
                    })
                return True
        except: continue
    return False

def get_ollama_findings(config, script_dir, project_root):
    print("\n--- [Stage 1/3] Deep Semantic Analysis (LLM) ---", file=sys.stderr)
    if not is_ollama_running():
        print("⚠️  Ollama not running. Skipping stage.", file=sys.stderr)
        return []
    eligible = []
    for root, _, files in os.walk("."):
        for f in files:
            path = os.path.join(root, f)
            if not is_excluded(path, config) and path.endswith((".py", ".js", ".ts", ".tsx", ".go")): eligible.append(path)
    sample_size = max(1, int(len(eligible) * config["ollama"]["sampling_rate"])) if eligible else 0
    sampled_files = random.sample(eligible, sample_size)
    print(f"Analyzing {sample_size} files ({config["ollama"]["sampling_rate"]*100}% sample of {len(eligible)} total)...", file=sys.stderr)
    all_ollama_findings = []
    for i, p in enumerate(sampled_files):
        sys.stderr.write(f"\rProgress: [{i+1}/{sample_size}] files analyzed...")
        sys.stderr.flush()
        detector_script = os.path.join(script_dir, "code_smell_detector.py")
        prompt_path = os.path.join(project_root, "prompt.md")
        stdout = run_command(f"{shlex.quote(sys.executable)} {shlex.quote(detector_script)} --quiet --prompt-path {shlex.quote(prompt_path)} --file-path {shlex.quote(p)}", f"Ollama: {p}", silent=True)
        _process_ollama_file_output(p, stdout, all_ollama_findings)
    print("", file=sys.stderr)
    return all_ollama_findings

def get_semgrep_findings(config, script_dir, output_file):
    print("\n--- [Stage 2/3] Security & Best Practices Scan (Semgrep) ---", file=sys.stderr)
    configs = " ".join([f"--config {c}" for c in config["semgrep"]["configs"]])
    excludes = " ".join([f"--exclude {d}/" for d in config["exclusions"]["directories"]])
    run_command(f"semgrep scan {configs} {excludes} --json > {shlex.quote(output_file)}", "Full Repository Scan", capture_output=False, check=False)
    parser_script = os.path.join(script_dir, "semgrep_parser.py")
    stdout = run_command(f"{shlex.quote(sys.executable)} {shlex.quote(parser_script)} {shlex.quote(output_file)}", "Processing Results", silent=True)
    try: return json.loads(stdout)
    except: return []

def get_basic_findings(config, script_dir, output_file):
    print("\n--- [Stage 3/3] Objective Metrics & Linting (Static) ---", file=sys.stderr)
    detector_script = os.path.join(script_dir, "basic_smell_detector.py")
    run_command(f"{shlex.quote(sys.executable)} {shlex.quote(detector_script)} --output-file {shlex.quote(output_file)} --scan-dirs .", "Full Repository Metrics", capture_output=False, check=False)
    try:
        with open(output_file, "r", encoding="utf-8") as f:
            findings = json.load(f)
            return [fnd for fnd in findings if not is_excluded(fnd.get("file_path", ""), config)]
    except: return []

def main():
    parser = argparse.ArgumentParser(prog="nikui")
    parser.add_argument("repo_path")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--output", default="analysis_report.json")
    args = parser.parse_args()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    if not os.path.isdir(args.repo_path): print(f"Error: {args.repo_path} is not a directory."); sys.exit(1)
    os.chdir(args.repo_path)
    config = load_config(os.path.abspath(os.path.join(project_root, args.config)))
    temp_dir = os.path.join(os.getcwd(), ".nikui_tmp")
    os.makedirs(temp_dir, exist_ok=True)
    print(f"Nikui Analysis Plan:\n1. Deep Semantic Analysis (Ollama)\n2. Security & Best Practices (Semgrep)\n3. Objective Metrics (Flake8/GoVet/Regex)\nTarget: {args.repo_path}")
    all_findings = []
    all_findings.extend(get_ollama_findings(config, script_dir, project_root))
    all_findings.extend(get_semgrep_findings(config, script_dir, os.path.join(temp_dir, "semgrep.json")))
    all_findings.extend(get_basic_findings(config, script_dir, os.path.join(temp_dir, "basic.json")))
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

if __name__ == "__main__": main()
