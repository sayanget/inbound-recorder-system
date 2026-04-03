"""Print filesystem prefix of the running interpreter's standard library (Lib parent). Used by set_venv_pythonhome.bat."""
from __future__ import annotations

import encodings
from pathlib import Path

print(Path(encodings.__file__).resolve().parent.parent.parent)
