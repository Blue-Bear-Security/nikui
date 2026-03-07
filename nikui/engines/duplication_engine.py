import os
import sys
import re
import ast
import copy
from dataclasses import dataclass, field
from itertools import combinations
from simhash import Simhash
from nikui.utils import is_excluded

class UniversalNormalizer:
    """Normalizes code text for any language using regex."""
    
    @staticmethod
    def clean_code(text, extension):
        # 1. Remove comments
        if extension in ['.py']:
            text = re.sub(r'#.*', '', text)
        else: # Go, JS, TS
            text = re.sub(r'//.*', '', text)
            text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
        
        # 2. Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        return text

class DuplicationEngine:
    def __init__(self, config):
        self.config = config
        self.threshold = config.get("duplication", {}).get("threshold", 0.85)
        self.min_lines = config.get("duplication", {}).get("min_lines", 6)
        self.supported_exts = [".py", ".go", ".ts", ".tsx", ".js"]

    def _get_fingerprint(self, text):
        shingle_size = 4
        grams = [text[i:i + shingle_size] for i in range(max(1, len(text) - shingle_size + 1))]
        return Simhash(grams)

    def extract_blocks(self, file_path):
        """Extracts significant code blocks (functions/classes) from a file."""
        ext = os.path.splitext(file_path)[1]
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except: return []

        # For Python, use AST
        if ext == ".py":
            return self._extract_python_ast(file_path, content)
        
        # For Go/TS/JS, split by common "block" markers (basic heuristic)
        return self._extract_generic_blocks(file_path, content, ext)

    def _extract_python_ast(self, file_path, source):
        try:
            tree = ast.parse(source)
            records = []
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    end = getattr(node, "end_lineno", node.lineno)
                    lines = end - node.lineno + 1
                    if lines < self.min_lines: continue
                    
                    norm = ast.dump(node) 
                    records.append({
                        "name": node.name,
                        "file": file_path,
                        "lineno": node.lineno,
                        "source_lines": lines,
                        "hash": self._get_fingerprint(norm)
                    })
            return records
        except: return []

    def _extract_generic_blocks(self, file_path, source, ext):
        # Split by what looks like a function/method declaration
        # This is a heuristic but better than whole-file hashing
        if ext == ".go":
            pattern = r'(?m)^func\s+.*\{'
        else: # TS/JS
            pattern = r'(?m)^(?:export\s+)?(?:async\s+)?(?:function|const|let|class)\s+.*[={]'
            
        parts = re.split(pattern, source)
        records = []
        # Find matches to get names and line numbers
        matches = list(re.finditer(pattern, source))
        
        for i, match in enumerate(matches):
            if i + 1 < len(parts):
                block_content = parts[i+1]
                line_count = block_content.count('\n')
                if line_count < self.min_lines: continue
                
                lineno = source[:match.start()].count('\n') + 1
                normalized = UniversalNormalizer.clean_code(block_content, ext)
                
                records.append({
                    "name": match.group(0).strip()[:40] + "...",
                    "file": file_path,
                    "lineno": lineno,
                    "source_lines": line_count,
                    "hash": self._get_fingerprint(normalized)
                })
        
        # If no blocks found but file is large, hash the whole file
        if not records and source.count('\n') >= self.min_lines:
            normalized = UniversalNormalizer.clean_code(source, ext)
            records.append({
                "name": os.path.basename(file_path),
                "file": file_path,
                "lineno": 1,
                "source_lines": source.count('\n'),
                "hash": self._get_fingerprint(normalized)
            })
            
        return records

    def run_stage(self, eligible_files):
        print("\n--- [Stage 4/4] Multi-Language Duplication Analysis ---", file=sys.stderr)
        all_blocks = []
        
        total = len(eligible_files)
        print(f"Scanning {total} files for duplicates...", file=sys.stderr)
        
        for i, path in enumerate(eligible_files):
            if i % 50 == 0 or i == total - 1:
                sys.stderr.write(f"\rProgress: [{i+1}/{total}] files indexed...")
                sys.stderr.flush()
            
            all_blocks.extend(self.extract_blocks(path))
        
        print(f"\nIndexed {len(all_blocks)} code blocks. Finding duplicates...", file=sys.stderr)

        groups = []
        seen = set()
        
        # Similarity search
        for i, j in combinations(range(len(all_blocks)), 2):
            if i in seen and j in seen: continue
            a, b = all_blocks[i], all_blocks[j]
            
            if a['file'] == b['file'] and abs(a['lineno'] - b['lineno']) < 5: continue
            
            dist = a['hash'].distance(b['hash'])
            sim = 1.0 - dist / 64
            
            if sim >= self.threshold:
                existing = next((g for g in groups if any(id(blk) == id(a) or id(blk) == id(b) for blk in g['blocks'])), None)
                if existing:
                    for blk in (a, b):
                        if not any(id(x) == id(blk) for x in existing['blocks']):
                            existing['blocks'].append(blk)
                    existing['similarity'] = min(existing['similarity'], sim)
                else:
                    groups.append({"similarity": sim, "blocks": [a, b]})
                seen.add(i); seen.add(j)

        findings = []
        for group in groups:
            sim_pct = group['similarity'] * 100
            paths = [f"{b['file']}:{b['lineno']}" for b in group['blocks']]
            for blk in group['blocks']:
                others = [p for p in paths if p != f"{blk['file']}:{blk['lineno']}"]
                findings.append({
                    "tool": "Duplication",
                    "file_path": blk['file'],
                    "line": blk['lineno'],
                    "category": "Architectural & Design Flaw",
                    "severity": "High" if sim_pct > 98 else "Medium",
                    "description": f"Code block '{blk['name']}' is {sim_pct:.1f}% similar to code at: {', '.join(others[:3])}"
                })
        
        print(f"Found {len(groups)} duplication groups.", file=sys.stderr)
        return findings
