import sys
import os
import argparse
import requests

MODEL = "qwen2.5-coder:7b"
URL = "http://localhost:11434/api/generate"

def load_prompt(prompt_path, filename, code):
    if not os.path.exists(prompt_path):
        print(f"Error: Prompt file {prompt_path} not found.", file=sys.stderr)
        sys.exit(1)
    with open(prompt_path, "r", encoding="utf-8") as f:
        template = f.read()
    return template.format(filename=filename, code=code)

def analyze_code(prompt):
    try:
        response = requests.post(URL, json={"model": MODEL, "prompt": prompt, "stream": False}, timeout=120)
        response.raise_for_status()
        return response.json().get("response", "")
    except requests.exceptions.RequestException as e:
        print(f"Error during Ollama API request: {e}", file=sys.stderr)
        return ""
    except Exception as e:
        print(f"Unexpected error analyzing code: {e}", file=sys.stderr)
        return ""

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file-path", required=True)
    parser.add_argument("--prompt-path", default="prompt.md")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    
    if not os.path.exists(args.file_path):
        print(f"Error: File {args.file_path} not found.", file=sys.stderr)
        sys.exit(1)
        
    try:
        with open(args.file_path, "r", encoding="utf-8") as f:
            code = f.read()
    except Exception as e:
        print(f"Error: Could not read file {args.file_path}: {e}", file=sys.stderr)
        sys.exit(1)
        
    prompt = load_prompt(args.prompt_path, args.file_path, code)
    result = analyze_code(prompt)
    if not result:
        print("Warning: Analysis failed or returned empty result.", file=sys.stderr)
    print(result)

if __name__ == "__main__": main()
