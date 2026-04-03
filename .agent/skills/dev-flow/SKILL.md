# Skill: Dev-Flow (Lightweight)

Implements a cost-effective engineering workflow that balances quality with token conservation.

## Core Workflow

### 1. Planning Phase (Mandatory for complex tasks)
- **Proposed Logic**: Before editing code, verbalize the logic.
- **Spec**: If the change involves multiple files, update/create `implementation_plan.md`.
- **Constraint**: Avoid quoting large blocks of existing code in the plan. Use line ranges instead.

### 2. Execution Phase
- **Atomic Edits**: Focus on one component at a time.
- **Safety**: Verify `backup_project.bat` was run if modifying core files like `single_app.py`.
- **Linting**: Check for basic syntax errors after writing.

### 3. Verification Phase
- **Evidence-Based**: Use `run_command` or browser tools to prove the fix works.
- **Minimal Logs**: When reading terminal output, use `tail` or `grep` to only capture relevant lines.

## Token Conservation Patterns
- **Targeted Reads**: Use `view_file` with specific `StartLine`/`EndLine`.
- **Outline First**: Use `view_file_outline` for large files like `single_app.py`.
- **Silent Mode**: For trivial fixes, skip the heavy planning steps and just notify the user.
