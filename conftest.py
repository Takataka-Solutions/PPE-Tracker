"""
Root conftest.py for standalone pytest execution of ppe_tracker tests.

In a Frappe bench environment, the bench's apps/ directory is on sys.path,
which makes `import ppe_tracker.ppe_tracker.*` work (the outer ppe_tracker/
is a namespace package containing the inner ppe_tracker/ package).

For standalone testing (e.g., `python -m pytest` from this directory), we
replicate that by registering a shim so that `ppe_tracker.ppe_tracker` resolves
to the inner package, which is already importable as just `ppe_tracker`.
"""
import sys
import os
from unittest.mock import MagicMock
from types import ModuleType

_this_dir = os.path.dirname(os.path.abspath(__file__))
_inner_pkg_dir = os.path.join(_this_dir, "ppe_tracker")


# ---------------------------------------------------------------------------
# Build a frappe mock that provides real exception classes and a real Document
# base class so that controllers can be imported and tested without the full
# Frappe framework.
# ---------------------------------------------------------------------------

class _ValidationError(Exception):
    """Stand-in for frappe.exceptions.ValidationError."""
    pass


class _Document:
    """Minimal stand-in for frappe.model.document.Document."""
    pass


if "frappe.utils" not in sys.modules:
    _frappe_mock = MagicMock()

    # Make ValidationError a real exception class
    _frappe_mock.ValidationError = _ValidationError
    _frappe_mock.exceptions.ValidationError = _ValidationError

    # Make Document a real class so that subclassing works
    _frappe_mock.model.document.Document = _Document

    # Provide frappe._() as a pass-through for translation strings
    _frappe_mock._ = lambda s: s
    _frappe_mock.__call__ = lambda self, s: s

    # Make frappe.whitelist() a passthrough decorator so decorated functions
    # retain their original implementation when imported during testing
    _frappe_mock.whitelist = lambda *args, **kwargs: (lambda fn: fn) if not args or callable(args[0]) else (lambda fn: fn)

    sys.modules.setdefault("frappe", _frappe_mock)
    sys.modules.setdefault("frappe.utils", _frappe_mock.utils)
    sys.modules.setdefault("frappe.model", _frappe_mock.model)
    sys.modules.setdefault("frappe.model.document", _frappe_mock.model.document)

    # Create a real module for frappe.exceptions so `from frappe.exceptions import ...` works
    _exceptions_mod = ModuleType("frappe.exceptions")
    _exceptions_mod.ValidationError = _ValidationError
    sys.modules["frappe.exceptions"] = _exceptions_mod

# Import the inner ppe_tracker package (which is what pip install -e gives us)
import ppe_tracker as _inner_pkg

# Now make `ppe_tracker.ppe_tracker` resolve to the same inner package.
# This simulates the Frappe bench environment where the outer dir is a namespace pkg.
if "ppe_tracker.ppe_tracker" not in sys.modules:
    sys.modules["ppe_tracker.ppe_tracker"] = _inner_pkg

