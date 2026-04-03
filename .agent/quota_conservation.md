# Quota Conservation Rule (额度节省规则)

## Core Principle
Minimize token consumption while maintaining code quality.

## File Operations
- **View outline first**: Use `view_file_outline` before `view_file` for code files
- **Targeted reads**: Specify `StartLine`/`EndLine` to read only relevant sections
- **No re-reads**: Don't view files already seen in conversation
- **Code items**: Use `view_code_item` for specific functions/classes

## Command Execution
- **Auto-run safe commands**: Set `SafeToAutoRun=true` for read-only operations (ls, grep, cat)
- **Batch operations**: Combine related commands into single scripts
- **Limit output**: Use `head -n 20`, `tail -n 50`, grep filters
- **Appropriate waits**: Set `WaitDurationSeconds` correctly, avoid polling

## Search & Discovery
- **Precise patterns**: Use specific globs with `MaxDepth` and `Excludes`
- **Grep before view**: Search file contents before reading entire files
- **Case sensitivity**: Use `CaseInsensitive=false` for exact matches

## Tool Call Optimization
- **Parallel by default**: Use `waitForPreviousTools=false` for independent operations
- **Sequential only when needed**: Dependencies require `waitForPreviousTools=true`
- **Batch file operations**: Move/copy multiple files in one command

## Workspace Hygiene
- **Root directory target**: Keep <150 files in project root
- **Archive regularly**: Move test/debug/backup scripts to `archive/`
- **Backup retention**: Keep only last 7 days of database backups in root
- **Compress archives**: Use zip for infrequently accessed files

## Artifact Management
- **Concise content**: Keep task.md, implementation_plan.md brief
- **Update, don't recreate**: Edit existing artifacts instead of creating new versions
- **Minimal metadata**: Avoid verbose summaries

## Communication
- **No filler**: Zero conversational pleasantries
- **Code-first**: Show code blocks directly
- **Bullet points**: Use lists instead of paragraphs
- **Batch questions**: Ask all clarifications in one message

## Anti-Patterns (禁止)
- ❌ Reading entire large files when only section needed
- ❌ Viewing same file multiple times
- ❌ Running commands synchronously when parallel is safe
- ❌ Searching without depth/pattern limits
- ❌ Keeping 200+ test scripts in workspace
- ❌ Storing all historical backups in root
