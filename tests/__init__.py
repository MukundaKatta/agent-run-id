"""Test package for agent_run_id.

Make the ``src`` layout importable when the test suite is run directly
(``python3 -m unittest discover -s tests``) without first installing the
package. When the package *is* installed, the import below is a harmless
no-op because the path is only appended.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
