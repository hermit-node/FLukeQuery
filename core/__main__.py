"""FLukeQuery entry point: supports both direct script and module launches."""
from pathlib import Path
import sys

if not __package__:
    # IDEs often run this exact file, which has no parent package context.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from core.gui import main
else:
    from .gui import main

if __name__ == "__main__":
    raise SystemExit(main())
