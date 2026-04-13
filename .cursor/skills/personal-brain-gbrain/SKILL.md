---
name: personal-brain-gbrain
description: >-
  Personal notes workflow — local Markdown brain at E:\Project\gbrain (repo
  sayanget/gbrain-notes), gbrain keyword-only index, Notion as backup, no OpenClaw,
  no vector/embed unless user asks. Use when the user mentions brain notes, gbrain,
  gbrain-notes, technical notes repo, or syncing notes.
---

# Personal brain (gbrain)

## Truth source

- Local: `E:\Project\gbrain`
- Remote: https://github.com/sayanget/gbrain-notes.git
- **Notion**: backup mirror only; local wins on conflict. **Hub**: [gbrain 备份](https://www.notion.so/gbrain-34119bf04d1680b4a5c2c31ffa07a986) (parent: **工作**). Use `page_id` `34119bf0-4d16-80b4-a5c2-c31ffa07a986` as `parent` for MCP imports.

## gbrain usage (this user)

- **Search**: keyword / full-text only — **no** `gbrain embed`, **no** `OPENAI_API_KEY` unless they explicitly want vectors again.
- After they edit notes: sync index with repo script from this project:
  - `.\scripts\brain_gbrain_sync.ps1` (uses `brain_gbrain_sync.local.ps1` for `GBRAIN_REPO` if present).
- Do **not** suggest OpenClaw for this stack.

## When answering

- Facts in notes: prefer **gbrain MCP** or reading paths under `E:\Project\gbrain` if the user attaches or names files.
- Notion is not canonical for note text.
