Act as an expert Senior Software Engineer and Architect. Analyze the provided code for technical debt and "code smells" based on the following rubric:

1. **Deep Nesting**: Logic nested more than 3 levels deep (e.g., nested loops, complex if/else chains).
2. **Poor Naming**: Variables, functions, or classes with non-descriptive names (e.g., "data", "temp", "x", or abbreviations like "proc_msg").
3. **Violations of SOLID principles**: 
   - Single Responsibility (classes/functions doing too much).
   - Open/Closed (lack of extensibility).
   - Dependency Inversion (tight coupling to concrete implementations).
4. **God Objects / Shotgun Surgery**: 
   - Classes that know too much or do too much.
   - Logic that, if changed, would require modifying many unrelated files/classes.
5. **Improper Error Handling & Silent Failures**:
   - Swallowed exceptions (empty except/catch blocks or "pass" without logging).
   - Silent fails (error paths that return default values without logging or alerting).
   - Incomplete error propagation.

Output Rules:
- Return ONLY a raw JSON array of objects.
- Do NOT include markdown code blocks, preambles, or explanations.
- If no issues are found, return exactly: []
- Structure each object as: {{ "category": "Category Name", "severity": "High|Medium|Low", "description": "Specific detail with line numbers" }}

FILE: {filename}
CODE:
{code}
