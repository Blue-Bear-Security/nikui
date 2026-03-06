import os
import requests
import argparse
import fnmatch # For filename matching with wildcards
import sys # For flushing stdout
import json # Import json module

# Configuration
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5-coder:7b"

# List of directories to scan for code files.
# These paths are relative to the project root.
CODE_DIRS_TO_SCAN = [
    "./bluebear-backend/",
    "./console/src/",
    "./handler/internal/",
    "./ops-agent/src/",
    "./research/", # Contains Python scripts, some are code, some are analysis
    "./scripts/",  # Contains utility scripts
    "./tools/",    # Contains helper tools
]

# File extensions to consider for scanning
FILE_EXTENSIONS = (".py", ".js", ".ts", ".tsx", ".go")

# Patterns to exclude test files/directories
# fnmatch supports Unix shell-style wildcards: *, ?, []
TEST_FILE_PATTERNS_TO_EXCLUDE = [
    "*/tests/*",         # Exclude any file within a 'tests' directory
    "*/test/*",          # Exclude any file within a 'test' directory
    "test_*.py",         # Python test files (e.g., pytest convention)
    "*.test.js",         # JavaScript/TypeScript test files
    "*.test.ts",         # JavaScript/TypeScript test files
    "*_test.go",         # Go test files
]

# Exact file paths to ignore regardless of other rules
IGNORED_FILES_EXACT = [
    # Console/Frontend specific files
    "console/tailwind.config.js",
    "commitlint.config.js",
    "console/jest.config.js",
    "console/jest.setup.js",
    "console/next.config.js",
    "console/postcss.config.js",
    "console/vitest.config.ts",
    "console/next-env.d.ts",

    # Backend/Infrastructure specific files
    "bluebear-backend/sst.config.ts",
    # Database migration files (not application logic to be scanned for smells)
    "bluebear-backend/services/shared/migrations/versions/",
    "bluebear-backend/services/shared/migrations/env.py",
    "bluebear-backend/services/shared/migrations/migration_utils.py",
    # Specific test-related files within handler/homebrew/test/
    "handler/homebrew/test/local-test/stub_server.py",
    "handler/homebrew/test/stub_server.py",
    "handler/homebrew/test/test_oauth_flow.py",
]


PROMPT_TEMPLATE = """
Act as an expert Senior Software Engineer and Architect. Analyze the provided code for technical debt and "code smells" based on the following rubric:

1. **Deep Nesting**: Logic nested more than 3 levels deep (e.g., nested loops, complex if/else chains).
2. **Poor Naming**: Variables, functions, or classes with non-descriptive names (e.g., 'data', 'temp', 'x', or abbreviations like 'proc_msg').
3. **Violations of SOLID principles**: 
   - Single Responsibility (classes/functions doing too much).
   - Open/Closed (lack of extensibility).
   - Dependency Inversion (tight coupling to concrete implementations).
4. **God Objects / Shotgun Surgery**: 
   - Classes that know too much or do too much.
   - Logic that, if changed, would require modifying many unrelated files/classes.
5. **Improper Error Handling & Silent Failures**:
   - Swallowed exceptions (empty except/catch blocks or 'pass' without logging).
   - Silent fails (error paths that return default values without logging or alerting).
   - Incomplete error propagation.

Output Rules:
- Return ONLY a raw JSON array of objects.
- Do NOT include markdown code blocks, preambles, or explanations.
- If no issues are found, return exactly: []
- Structure each object as: {{"category": "Category Name", "severity": "High|Medium|Low", "description": "Specific detail with line numbers"}}

FILE: {filename}
CODE:
{code}
"""

def is_excluded(filepath):
    """
    Checks if a given filepath should be excluded based on defined patterns.
    """
    # Check for exact file path exclusions
    for ignored_path in IGNORED_FILES_EXACT:
        # Normalize paths for comparison
        normalized_filepath = os.path.normpath(filepath)
        normalized_ignored_path = os.path.normpath(ignored_path)

        if normalized_ignored_path.endswith(os.sep) and normalized_filepath.startswith(normalized_ignored_path):
            return True # Exclude entire directory
        elif normalized_filepath == normalized_ignored_path:
            return True

    # Check for test file patterns
    filename = os.path.basename(filepath)
    for pattern in TEST_FILE_PATTERNS_TO_EXCLUDE:
        if fnmatch.fnmatch(filepath, pattern) or fnmatch.fnmatch(filename, pattern):
            return True
    return False

def scan_file(filepath):
    """
    Scans a single file for code smells using the Ollama API.
    """
    print(f"DEBUG: Reading file {filepath}", file=sys.stderr) # Debug output
    sys.stderr.flush()

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            code = f.read()
    except Exception as e:
        print(f"Error reading file {filepath}: {e}", file=sys.stderr)
        sys.stderr.flush()
        return

    print(f"DEBUG: Sending {filepath} to Ollama...", file=sys.stderr) # Debug output
    sys.stderr.flush()

    filename = os.path.basename(filepath)

    try:
        response = requests.post(OLLAMA_URL, json={
            "model": MODEL,
            "prompt": PROMPT_TEMPLATE.format(filename=filename, code=code),
            "stream": False
        }, timeout=60) # Reduced timeout to 60 seconds to prevent command timeout
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        try:
            # Attempt to parse the 'response' field as JSON
            ollama_response_text = response.json()['response']
            findings = json.loads(ollama_response_text)
            print(f"\n## Results for {filepath}\n{json.dumps(findings, indent=2)}")
        except json.JSONDecodeError:
            # If Ollama didn't return valid JSON, print the raw text response
            print(f"\n## Results for {filepath} (Raw Response - JSON Decode Error)\n{ollama_response_text}")
        except KeyError:
            # Handle cases where 'response' key might be missing
            print(f"\n## Results for {filepath} (Raw Response - 'response' Key Missing)\n{response.text}")
    except requests.exceptions.RequestException as e:
        print(f"Error communicating with Ollama for {filepath}: {e}", file=sys.stderr)
        sys.stderr.flush()
    except KeyError:
        print(f"Unexpected response from Ollama for {filepath}: {response.text}", file=sys.stderr)
        sys.stderr.flush()
    except Exception as e:
        print(f"An unexpected error occurred during scan for {filepath}: {e}", file=sys.stderr)
        sys.stderr.flush()

def main():
    parser = argparse.ArgumentParser(description="Scan code for smells using Ollama.")
    parser.add_argument("--file-path", help="Path to a single file to scan.")
    parser.add_argument("--quiet", action="store_true", help="Suppress header and metadata logs.")
    args = parser.parse_args()

    if not args.quiet:
        print(f"Scanning project for code smells using model: {MODEL}", file=sys.stderr)
        print("Excluded patterns:", file=sys.stderr)
        for p in TEST_FILE_PATTERNS_TO_EXCLUDE + IGNORED_FILES_EXACT:
            print(f"- {p}", file=sys.stderr)
        print("-" * 30, file=sys.stderr)

    scanned_files_count = 0
    excluded_files_count = 0

    if args.file_path:
        filepath = args.file_path
        if not os.path.exists(filepath):
            print(f"Error: File '{filepath}' not found.", file=sys.stderr)
            sys.exit(1)
        
        # Check if the file has a supported extension and is not excluded
        file_extension_supported = False
        for ext in FILE_EXTENSIONS:
            if filepath.endswith(ext):
                file_extension_supported = True
                break
        
        if not file_extension_supported:
            print(f"Skipping (unsupported extension): {filepath}", file=sys.stderr)
            sys.exit(0)
            
        if is_excluded(filepath):
            print(f"Excluding: {filepath}", file=sys.stderr)
            sys.exit(0)
        
        print(f"Processing single file: {filepath}", file=sys.stderr)
        scan_file(filepath)
        scanned_files_count = 1
    else:
        for code_dir in CODE_DIRS_TO_SCAN:
            if not os.path.isdir(code_dir):
                print(f"Warning: Code directory '{code_dir}' not found. Skipping.", file=sys.stderr)
                sys.stderr.flush()
                continue

            for root, _, files in os.walk(code_dir):
                for file in files:
                    filepath = os.path.join(root, file)
                    if is_excluded(filepath):
                        print(f"Excluding: {filepath}", file=sys.stderr)
                        sys.stderr.flush()
                        excluded_files_count += 1
                        continue
                    
                    if file.endswith(FILE_EXTENSIONS):
                        print(f"Processing: {filepath}", file=sys.stderr)
                        sys.stderr.flush()
                        scan_file(filepath)
                        scanned_files_count += 1
                    else:
                        print(f"Skipping (unsupported extension): {filepath}", file=sys.stderr)
                        sys.stderr.flush()
    
    print("-" * 30, file=sys.stderr)
    print(f"Scan complete. Scanned {scanned_files_count} files, excluded {excluded_files_count} files.", file=sys.stderr)
    sys.stderr.flush()


if __name__ == "__main__":
    main()
