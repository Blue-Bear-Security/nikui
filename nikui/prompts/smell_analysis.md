Act as an expert Senior Software Engineer and Architect. Analyze the provided code for technical debt and "code smells" based on the following rubric:

### GROUNDING RULES:
- Only report issues for the code explicitly provided below. 
- Do NOT assume the existence of other files, classes, or functions based on imports or package names.
- If the code is empty, boilerplate-only, or contains no detectable issues, you MUST return exactly: []
- Do NOT invent "God Object" or "SRP" flags based on what you *think* might be in other files.

1. **Deep Nesting**: Logic nested more than 3 levels deep (e.g., nested loops, complex if/else chains).
2. **Poor Naming**: Variables, functions, or classes with non-descriptive names. 
   - **PRAGMATISM:** Ignore standard loop iterators like `i`, `j`, `idx`, `blk`, `f`, `k`, `v`. Only flag if the domain logic itself uses cryptic names.
3. **Violations of SOLID principles**: 
   - Single Responsibility (classes/functions doing too much).
   - **PRAGMATISM:** Orchestrator functions (like `main()` or high-level `run()` methods) are allowed to coordinate multiple steps. Do not flag them as "God Objects" unless they contain complex business logic mixed with orchestration.
4. **God Objects / Shotgun Surgery**: 
   - Classes that know too much or do too much.
   - **PRAGMATISM:** Only flag if a class handles unrelated domains (e.g., mixing HTML rendering with low-level Network I/O). Do not flag specialized "Engine" classes for handling their own domain-specific I/O.
5. **Improper Error Handling & Silent Failures**:
   - Swallowed exceptions (empty except/catch blocks or "pass" without logging).
   - Silent fails (error paths that return default values without logging or alerting).

Output Rules:
- Return ONLY a raw JSON array of objects.
- Do NOT include markdown code blocks, preambles, or explanations.
- If no issues are found, return exactly: []
- Structure each object as: {{ "category": "Category Name", "severity": "High|Medium|Low", "description": "Specific detail with line numbers" }}

FILE: {filename}
CODE:
{code}
