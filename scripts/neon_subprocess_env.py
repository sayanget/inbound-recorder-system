"""Windows: set PYTHONHOME to the real stdlib prefix so child interpreters avoid
'Could not find platform independent libraries'. Derive from encodings (not pyvenv.cfg home)."""
from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path


def _stdlib_prefix_from_encodings() -> str | None:
    try:
        import encodings

        root = Path(encodings.__file__).resolve().parent.parent.parent
        if (root / "Lib" / "os.py").is_file():
            return str(root)
    except Exception:
        return None
    return None


def child_python_env(base: Mapping[str, str] | None = None) -> dict[str, str]:
    env = dict(base if base is not None else os.environ)
    env.pop("PYTHONEXECUTABLE", None)

    prefix = _stdlib_prefix_from_encodings()
    if prefix:
        env["PYTHONHOME"] = prefix
    else:
        env.pop("PYTHONHOME", None)

    env.setdefault("PYTHONIOENCODING", "utf-8")
    return env
