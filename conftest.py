"""Root conftest.py for standalone pytest execution of ppe_tracker tests.

Module resolution
-----------------
Run from the repository root, `import ppe_tracker` resolves to the app package
(`./ppe_tracker/`), and `ppe_tracker.ppe_tracker` resolves to the module
directory (`./ppe_tracker/ppe_tracker/`). That is exactly how a Frappe bench
resolves it, because `pip install -e apps/ppe_tracker` puts the repository root
on `sys.path`.

No sys.modules aliasing is done here, deliberately. An earlier version of this
file registered `sys.modules["ppe_tracker.ppe_tracker"]` as the app package,
which shifted every import by one level. Broken paths resolved under pytest and
failed on a real bench, so the test suite passed while `bench migrate` could not
run. See docs/01_Audit_Findings.md section 2a and BLOCK-001.

The canonical import prefix is three levels: `ppe_tracker.ppe_tracker.<thing>`.
If a test needs a shim to import something, the layout is wrong -- fix the
layout, not the conftest.

What this file does provide
---------------------------
A `frappe` stand-in so controllers can be imported and unit-tested without a
bench. Real exception and Document classes, everything else a MagicMock.

This means the standalone suite exercises logic against a fake framework. It has
no database, no document lifecycle, and no permission model. A green run here is
NOT evidence that the app works on a bench -- for that, use
`bench --site <site> run-tests --app ppe_tracker` plus a functional walkthrough.
"""
import sys
from types import ModuleType
from unittest.mock import MagicMock


class _ValidationError(Exception):
    """Stand-in for frappe.exceptions.ValidationError."""


class _Document:
    """Minimal stand-in for frappe.model.document.Document."""


if "frappe.utils" not in sys.modules:
    _frappe_mock = MagicMock()

    # Real exception class so `assertRaises` and `except` behave normally
    _frappe_mock.ValidationError = _ValidationError
    _frappe_mock.exceptions.ValidationError = _ValidationError

    # Real class so subclassing in controllers works
    _frappe_mock.model.document.Document = _Document

    # frappe._() as a pass-through for translation strings
    _frappe_mock._ = lambda s: s
    _frappe_mock.__call__ = lambda self, s: s

    # frappe.whitelist() as a passthrough decorator, so decorated functions keep
    # their original implementation when imported during testing
    _frappe_mock.whitelist = lambda *args, **kwargs: (
        (lambda fn: fn) if not args or callable(args[0]) else (lambda fn: fn)
    )

    sys.modules.setdefault("frappe", _frappe_mock)
    sys.modules.setdefault("frappe.utils", _frappe_mock.utils)
    sys.modules.setdefault("frappe.model", _frappe_mock.model)
    sys.modules.setdefault("frappe.model.document", _frappe_mock.model.document)

    # Real module objects for the submodules that are imported by name, so that
    # `from frappe.X import Y` resolves. A MagicMock attribute is not importable.
    _exceptions_mod = ModuleType("frappe.exceptions")
    _exceptions_mod.ValidationError = _ValidationError
    sys.modules["frappe.exceptions"] = _exceptions_mod

    # install.py does `from frappe.permissions import add_permission, ...`.
    # Without this the permission-seeding code cannot be imported or tested.
    _permissions_mod = ModuleType("frappe.permissions")
    _permissions_mod.add_permission = MagicMock(name="add_permission")
    _permissions_mod.update_permission_property = MagicMock(
        name="update_permission_property"
    )
    sys.modules["frappe.permissions"] = _permissions_mod
