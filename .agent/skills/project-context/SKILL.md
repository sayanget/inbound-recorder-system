# Skill: Project Context

Captures essential project-specific metadata to minimize token consumption and prevent hallucinations.

## Project Overview
- **Name**: Inbound Recorder System
- **Stack**: Python (Flask), SQLite/PostgreSQL, HTML/JS.
- **Timezone**: `America/Los_Angeles` (LA_TZ).
- **Core Files**:
    - [single_app.py](file:///d:/project/inbound_python_source/single_app.py): Main application logic (8000+ lines).
    - [database.py](file:///d:/project/inbound_python_source/database.py): Database abstraction layer.
    - [calc_outsource_finance.py](file:///d:/project/inbound_python_source/calc_outsource_finance.py): Labor sync logic.

## Business Logic
- **Accounting Cycle**: Usually 06:00 (Today) to 06:00 (Tomorrow).
- **Sync Logic**: 
    - Gofo: Hourly at `:01`. Targets center `596`.
    - Feishu: Daily at noon. Excludes `ATL.G`.

## Database Schema (inbound.db)
- `inbound_records`: Dock operations and vehicle loads.
- `sorting_records`: Sorting throughput data.
- `gofo_sync_history`: Logs of auto/manual Gofo syncs.
- `cost_main`: Aggregated cost accounting records.
- `config_labor_hourly/piece`: Labor cost configurations.
- `feishu_raw_data`: Waybill data from Feishu.

## Development Rules
- **Safety**: Run `.\backup_project.bat` before major file edits.
- **Port**: Default is 8080.
- **Environment**: Use `WERKZEUG_RUN_MAIN` check to safeguard background threads.
