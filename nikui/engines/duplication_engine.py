import os
import sys
import re
import ast
import json
import warnings
from itertools import combinations
from simhash import Simhash


class UniversalNormalizer:
    """Normalizes code text for any language using regex."""

    @staticmethod
    def clean_code(text, extension):
        # 1. Remove comments
        if extension in [".py"]:
            text = re.sub(r"#.*", "", text)
        else:  # Go, JS, TS
            text = re.sub(r"//.*", "", text)
            text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)

        # 2. Normalize whitespace
        text = re.sub(r"\s+", " ", text).strip()
        return text


class DuplicationEngine:
    def __init__(self, config):
        self.config = config
        self.threshold = config.get("duplication", {}).get("threshold", 0.85)
        self.min_lines = config.get("duplication", {}).get("min_lines", 6)
        self.supported_exts = [".py", ".go", ".ts", ".tsx", ".js"]
        self.db_path = config.get("duplication", {}).get("db_path") or os.path.join(".nikui", "fingerprints.json")

    def _get_fingerprint(self, text):
        shingle_size = 4
        grams = [
            text[i : i + shingle_size]
            for i in range(max(1, len(text) - shingle_size + 1))
        ]
        return Simhash(grams)

    def load_fingerprints(self):
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Convert hex strings back to Simhash objects
                    for block in data.get("blocks", []):
                        block["hash"] = Simhash(int(block["hash"], 16))
                    return data.get("blocks", [])
            except Exception as e:
                print(f"Warning: Could not load fingerprints: {e}", file=sys.stderr)
        return []

    def save_fingerprints(self, blocks):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        # Convert Simhash objects to hex strings for JSON
        serializable = []
        for b in blocks:
            # Create a shallow copy to avoid modifying the in-memory object needed for verification
            b_copy = b.copy()
            b_copy["hash"] = hex(b["hash"].value)
            # Remove content from persistent DB to keep it small
            b_copy.pop("content", None)
            serializable.append(b_copy)

        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump({"version": "1.0", "blocks": serializable}, f, indent=2)

    def extract_blocks(self, file_path):
        """Extracts significant code blocks (functions/classes) from a file."""
        ext = os.path.splitext(file_path)[1]
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception as e:
            print(f"Warning: Could not read {file_path}: {e}", file=sys.stderr)
            return []

        if content.count("\n") < self.min_lines:
            return []

        # Suppress SyntaxWarnings from scanned code (e.g. invalid escape sequences in strings)
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=SyntaxWarning)
            # For Python, use AST
            if ext == ".py":
                return self._extract_python_ast(file_path, content)

        # For Go/TS/JS, split by common "block" markers (basic heuristic)
        return self._extract_generic_blocks(file_path, content, ext)

    def _extract_python_ast(self, file_path, source):
        try:
            tree = ast.parse(source)
            records = []
            source_lines = source.splitlines()
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    end = getattr(node, "end_lineno", node.lineno)
                    lines = end - node.lineno + 1
                    if lines < self.min_lines:
                        continue

                    # Dump AST as a proxy for normalized text
                    norm = ast.dump(node)
                    # Extract raw code block
                    block_code = "\n".join(source_lines[node.lineno - 1 : end])

                    records.append(
                        {
                            "name": node.name,
                            "file": file_path,
                            "lineno": node.lineno,
                            "source_lines": lines,
                            "hash": self._get_fingerprint(norm),
                            "content": block_code,
                        }
                    )
            return records
        except Exception as e:
            print(f"Warning: Could not parse {file_path}: {e}", file=sys.stderr)
            return []

    def _extract_generic_blocks(self, file_path, source, ext):
        if ext == ".go":
            pattern = r"(?m)^func\s+.*\{"
        else:  # TS/JS
            pattern = (
                r"(?m)^(?:export\s+)?(?:async\s+)?(?:function|const|let|class)\s+.*[={]"
            )

        parts = re.split(pattern, source)
        records = []
        matches = list(re.finditer(pattern, source))

        for i, match in enumerate(matches):
            if i + 1 < len(parts):
                block_content = parts[i + 1]
                line_count = block_content.count("\n")
                if line_count < self.min_lines:
                    continue

                lineno = source[: match.start()].count("\n") + 1
                normalized = UniversalNormalizer.clean_code(block_content, ext)

                # Heuristic to find the end of block by matching braces would be better,
                # but for simplicity we use the split parts.
                full_block = match.group(0) + block_content

                records.append(
                    {
                        "name": match.group(0).strip()[:40] + "...",
                        "file": file_path,
                        "lineno": lineno,
                        "source_lines": line_count,
                        "hash": self._get_fingerprint(normalized),
                        "content": full_block,
                    }
                )

        if not records and source.count("\n") >= self.min_lines:
            normalized = UniversalNormalizer.clean_code(source, ext)
            records.append(
                {
                    "name": os.path.basename(file_path),
                    "file": file_path,
                    "lineno": 1,
                    "source_lines": source.count("\n"),
                    "hash": self._get_fingerprint(normalized),
                    "content": source,
                }
            )

        return records

    def _get_block_content_from_file(self, block):
        """Lazy loads content for a block from its source file."""
        try:
            with open(block["file"], "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                # Use 0-based indexing for lines
                start = block["lineno"] - 1
                end = start + block["source_lines"]
                return "".join(lines[start:end])
        except Exception as e:
            print(f"Warning: Could not lazy-load content for {block['file']}: {e}", file=sys.stderr)
            return ""

    def run_stage(self, eligible_files, ollama=None, modified_files=None):
        print(
            "\n--- [Stage 4/5] Multi-Language Duplication Analysis ---", file=sys.stderr
        )
        
        # 1. Load existing fingerprints
        existing_blocks = self.load_fingerprints()
        
        # 2. Determine which files need re-indexing
        # If modified_files is provided, we only index those. 
        # Otherwise, index all eligible_files (standard full scan).
        files_to_index = modified_files if modified_files is not None else eligible_files
        
        # Remove old blocks for files we are about to re-index
        if files_to_index:
            existing_blocks = [b for b in existing_blocks if b["file"] not in files_to_index]

        # 3. Index new/modified files
        all_blocks = existing_blocks
        new_blocks = []
        total = len(files_to_index)
        if total > 0:
            print(f"Indexing {total} modified files...", file=sys.stderr)
            for i, path in enumerate(files_to_index):
                if i % 50 == 0 or i == total - 1:
                    sys.stderr.write(f"\rProgress: [{i+1}/{total}] files indexed...")
                    sys.stderr.flush()
                new_blocks.extend(self.extract_blocks(path))
            print("", file=sys.stderr)

        all_blocks.extend(new_blocks)
        
        # 4. Save updated fingerprints for next time
        self.save_fingerprints(all_blocks)

        print(
            f"Comparing {len(new_blocks) if modified_files else len(all_blocks)} blocks against {len(all_blocks)} total index...",
            file=sys.stderr,
        )

        candidates = []
        seen = set()

        # If we have modified_files, we only need to compare new_blocks vs all_blocks
        # If not, it's a full O(N^2) of all_blocks vs all_blocks
        if modified_files is not None:
            # Incremental Compare: New Blocks vs Everything
            for i, a in enumerate(new_blocks):
                for j, b in enumerate(all_blocks):
                    # Skip same block or very close blocks in same file
                    if a["file"] == b["file"] and abs(a["lineno"] - b["lineno"]) < 5:
                        continue
                    
                    dist = a["hash"].distance(b["hash"])
                    sim = 1.0 - dist / 64

                    if sim >= self.threshold:
                        existing = next((g for g in candidates if any(id(blk) == id(a) or id(blk) == id(b) for blk in g["blocks"])), None)
                        if existing:
                            for blk in (a, b):
                                if not any(id(x) == id(blk) for x in existing["blocks"]):
                                    existing["blocks"].append(blk)
                            existing["similarity"] = min(existing["similarity"], sim)
                        else:
                            candidates.append({"similarity": sim, "blocks": [a, b]})
        else:
            # Standard Full Compare: O(N^2)
            for i, j in combinations(range(len(all_blocks)), 2):
                a, b = all_blocks[i], all_blocks[j]
                if a["file"] == b["file"] and abs(a["lineno"] - b["lineno"]) < 5:
                    continue
                dist = a["hash"].distance(b["hash"])
                sim = 1.0 - dist / 64
                if sim >= self.threshold:
                    candidates.append({"similarity": sim, "blocks": [a, b]})

        if not candidates:
            return []

        print(
            f"Found {len(candidates)} candidate groups. Verifying with LLM...",
            file=sys.stderr,
        )

        final_groups = []
        # Check LLM status once before the loop
        llm_active = ollama.client.is_running() if ollama else False
        
        for idx, group in enumerate(candidates):
            sys.stderr.write(f"\rVerifying: [{idx+1}/{len(candidates)}] groups...")
            sys.stderr.flush()

            if llm_active:
                # Pick first two blocks to verify
                blk_a = group["blocks"][0]
                blk_b = group["blocks"][1]
                
                # Lazy load content if missing (happens for cached blocks)
                content_a = blk_a.get("content") or self._get_block_content_from_file(blk_a)
                content_b = blk_b.get("content") or self._get_block_content_from_file(blk_b)

                if content_a and content_b:
                    is_duplicate, reason = ollama.verify_duplication(
                        blk_a["file"], content_a, blk_b["file"], content_b
                    )
                    if is_duplicate:
                        group["reason"] = reason
                        final_groups.append(group)
                else:
                    # If file is missing locally, it's stale cache data. Skip it.
                    continue
            else:
                # No LLM, trust Simhash
                final_groups.append(group)

        print("", file=sys.stderr)

        findings = []
        for group in final_groups:
            sim_pct = group["similarity"] * 100
            reason = group.get("reason", "Structural similarity detected.")
            paths = [f"{b['file']}:{b['lineno']}" for b in group["blocks"]]
            for blk in group["blocks"]:
                others = [p for p in paths if p != f"{blk['file']}:{blk['lineno']}"]
                findings.append(
                    {
                        "tool": "Duplication",
                        "file_path": blk["file"],
                        "line": blk["lineno"],
                        "category": "Architectural & Design Flaw",
                        "severity": "High" if sim_pct > 98 else "Medium",
                        "description": f"[{sim_pct:.1f}% Match] {reason} (See: {', '.join(others[:2])})",
                    }
                )

        print(f"Verified {len(final_groups)} duplication groups.", file=sys.stderr)
        return findings
