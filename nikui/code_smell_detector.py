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
        if response.status_code == 200:
            return response.json().get("response", "")
        else:
            print(f"Error: {response.status_code} - {response.text}", file=sys.stderr)
            return ""
    except Exception as e:
        print(f"Connection error: {e}", file=sys.stderr)
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
        
    with open(args.file_path, "r", encoding="utf-8") as f:
        code = f.read()
        
    prompt = load_prompt(args.prompt_path, args.file_path, code)
    result = analyze_code(prompt)
    print(result)

if __name__ == "__main__": main()
