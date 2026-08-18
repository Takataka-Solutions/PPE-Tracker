# Copyright (c) 2024, Takataka Solutions and contributors
# For license information, please see license.txt

"""Unit tests for MRF User role and permissions.

Tests cover:
- MRF User role existence as a fixture (Requirements 7.1, 7.5)
- MRF User read/write access to Wornout PPE Warehouse (Requirements 7.2, 14.6)
- MRF User can create Material Issue Stock Entry (Requirements 7.2, 14.6)
- MRF User cannot access other warehouses (Requirements 7.2)
"""

import sys
import unittest
from unittest.mock import MagicMock, patch


# Mock frappe and frappe.permissions at the module level before importing install
_mock_frappe = MagicMock()
_mock_permissions = MagicMock()
_mock_frappe.permissions = _mock_permissions


def _import_install_module():
    """Import install module with frappe mocked in sys.modules."""
    # Ensure frappe modules are mocked before import
    original_modules = {}
    modules_to_mock = {
        "frappe": _mock_frappe,
        "frappe.permissions": _mock_permissions,
    }

    for mod_name, mock_mod in modules_to_mock.items():
        if mod_name in sys.modules:
            original_modules[mod_name] = sys.modules[mod_name]
        sys.modules[mod_name] = mock_mod

    # Remove cached install module to force re-import with mocks
    install_module_name = "ppe_tracker.ppe_tracker.install"
    if install_module_name in sys.modules:
        del sys.modules[install_module_name]

    try:
        import importlib
        install = importlib.import_module("install")
        return install
    finally:
        # Restore original modules
        for mod_name in modules_to_mock:
            if mod_name in original_modules:
                sys.modules[mod_name] = original_modules[mod_name]


class TestMRFUserRoleExists(unittest.TestCase):
    """Test that the MRF User role is properly defined as a fixture.

    Validates: Requirements 7.1, 7.5
    """

    def test_mrf_user_role_exists_in_fixture(self):
        """MRF User role should be defined in fixtures/role.json with correct properties.

        The role fixture defines MRF User as a custom role with desk access,
        making it exportable via bench export-fixtures.

        Validates: Requirements 7.5
        """
        import json
        import os

        fixture_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "fixtures",
            "role.json",
        )

        with open(fixture_path, "r") as f:
            roles = json.load(f)

        mrf_roles = [r for r in roles if r.get("role_name") == "MRF User"]
        self.assertEqual(len(mrf_roles), 1, "MRF User role should exist in fixtures")

        mrf_role = mrf_roles[0]
        self.assertEqual(mrf_role["doctype"], "Role")
        self.assertEqual(mrf_role["is_custom"], 1)
        self.assertEqual(mrf_role["desk_access"], 1)

    def test_role_fixture_listed_in_hooks(self):
        """hooks.py should include 'Role' in the fixtures list so MRF User is exported.

        Validates: Requirements 7.5
        """
        import importlib
        import os

        # Load hooks.py directly to read the fixtures variable
        hooks_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "hooks.py"
        )
        spec = importlib.util.spec_from_file_location("hooks", hooks_path)
        hooks_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(hooks_module)

        self.assertIn("Role", hooks_module.fixtures)


class TestMRFUserWarehouseAccess(unittest.TestCase):
    """Test MRF User has read/write access to Warehouse DocType.

    Validates: Requirements 7.1, 7.2, 14.6
    """

    def setUp(self):
        """Set up mock objects and import install module."""
        self.mock_add_permission = MagicMock()
        self.mock_update_permission_property = MagicMock()
        self.mock_frappe = MagicMock()

        # Patch sys.modules to mock frappe before importing install
        self._original_modules = {}
        mock_frappe_module = self.mock_frappe
        mock_frappe_module.permissions = MagicMock()
        mock_frappe_module.permissions.add_permission = self.mock_add_permission
        mock_frappe_module.permissions.update_permission_property = self.mock_update_permission_property

        for mod in ["frappe", "frappe.permissions"]:
            if mod in sys.modules:
                self._original_modules[mod] = sys.modules[mod]

        sys.modules["frappe"] = mock_frappe_module
        sys.modules["frappe.permissions"] = mock_frappe_module.permissions

        # Force reimport of install module
        if "install" in sys.modules:
            del sys.modules["install"]

        import importlib
        import os

        install_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "install.py"
        )
        spec = importlib.util.spec_from_file_location("install", install_path)
        self.install_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.install_module)

    def tearDown(self):
        """Restore original sys.modules."""
        for mod, original in self._original_modules.items():
            sys.modules[mod] = original
        for mod in ["frappe", "frappe.permissions"]:
            if mod not in self._original_modules and mod in sys.modules:
                del sys.modules[mod]

    def test_mrf_user_can_read_wornout_warehouse(self):
        """MRF User role gets read permission on Warehouse DocType.

        The setup function grants read access to Warehouse at permlevel 0,
        which combined with User Permission filtering restricts access to
        the Wornout PPE Warehouse at runtime.

        Validates: Requirements 7.1, 7.2, 14.6
        """
        # Mock: role does not already have permission
        self.mock_frappe.db.exists.return_value = False

        self.install_module._setup_warehouse_permissions()

        # Verify read permission is set to 1
        self.mock_update_permission_property.assert_any_call(
            "Warehouse", "MRF User", permlevel=0, ptype="read", value=1
        )

    def test_mrf_user_can_write_wornout_warehouse(self):
        """MRF User role gets write permission on Warehouse DocType.

        Validates: Requirements 7.2, 14.6
        """
        self.mock_frappe.db.exists.return_value = False

        self.install_module._setup_warehouse_permissions()

        # Verify write permission is set to 1
        self.mock_update_permission_property.assert_any_call(
            "Warehouse", "MRF User", permlevel=0, ptype="write", value=1
        )

    def test_mrf_user_cannot_create_or_delete_warehouses(self):
        """MRF User should NOT have create or delete permissions on Warehouse.

        MRF User only reads/writes existing warehouses — they cannot create
        new warehouses or delete existing ones.

        Validates: Requirements 7.2
        """
        self.mock_frappe.db.exists.return_value = False

        self.install_module._setup_warehouse_permissions()

        # Verify create permission is explicitly set to 0
        self.mock_update_permission_property.assert_any_call(
            "Warehouse", "MRF User", permlevel=0, ptype="create", value=0
        )

        # Verify delete permission is explicitly set to 0
        self.mock_update_permission_property.assert_any_call(
            "Warehouse", "MRF User", permlevel=0, ptype="delete", value=0
        )


class TestMRFUserStockEntryAccess(unittest.TestCase):
    """Test MRF User can create Material Issue Stock Entry.

    Validates: Requirements 7.2, 14.6
    """

    def setUp(self):
        """Set up mock objects and import install module."""
        self.mock_add_permission = MagicMock()
        self.mock_update_permission_property = MagicMock()
        self.mock_frappe = MagicMock()

        mock_frappe_module = self.mock_frappe
        mock_frappe_module.permissions = MagicMock()
        mock_frappe_module.permissions.add_permission = self.mock_add_permission
        mock_frappe_module.permissions.update_permission_property = self.mock_update_permission_property

        self._original_modules = {}
        for mod in ["frappe", "frappe.permissions"]:
            if mod in sys.modules:
                self._original_modules[mod] = sys.modules[mod]

        sys.modules["frappe"] = mock_frappe_module
        sys.modules["frappe.permissions"] = mock_frappe_module.permissions

        import importlib
        import os

        install_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "install.py"
        )
        spec = importlib.util.spec_from_file_location("install", install_path)
        self.install_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.install_module)

    def tearDown(self):
        """Restore original sys.modules."""
        for mod, original in self._original_modules.items():
            sys.modules[mod] = original
        for mod in ["frappe", "frappe.permissions"]:
            if mod not in self._original_modules and mod in sys.modules:
                del sys.modules[mod]

    def test_mrf_user_can_create_material_issue_stock_entry(self):
        """MRF User gets create and submit permissions on Stock Entry DocType.

        This enables MRF User to create Material Issue Stock Entries for
        disposal or sale from the Wornout PPE Warehouse.

        Validates: Requirements 7.2, 14.6
        """
        # Mock: role does not already have permission
        self.mock_frappe.db.exists.return_value = False

        self.install_module._setup_stock_entry_permissions()

        # Verify add_permission was called for Stock Entry + MRF User
        self.mock_add_permission.assert_called_once_with(
            "Stock Entry", "MRF User", permlevel=0
        )

        # Verify create permission is set to 1
        self.mock_update_permission_property.assert_any_call(
            "Stock Entry", "MRF User", permlevel=0, ptype="create", value=1
        )

        # Verify submit permission is set to 1 (Stock Entry is submittable)
        self.mock_update_permission_property.assert_any_call(
            "Stock Entry", "MRF User", permlevel=0, ptype="submit", value=1
        )

    def test_mrf_user_can_read_and_write_stock_entries(self):
        """MRF User gets read and write permissions on Stock Entry.

        Validates: Requirements 14.6
        """
        self.mock_frappe.db.exists.return_value = False

        self.install_module._setup_stock_entry_permissions()

        self.mock_update_permission_property.assert_any_call(
            "Stock Entry", "MRF User", permlevel=0, ptype="read", value=1
        )
        self.mock_update_permission_property.assert_any_call(
            "Stock Entry", "MRF User", permlevel=0, ptype="write", value=1
        )

    def test_mrf_user_cannot_delete_stock_entries(self):
        """MRF User should NOT have delete permission on Stock Entry.

        Validates: Requirements 7.2
        """
        self.mock_frappe.db.exists.return_value = False

        self.install_module._setup_stock_entry_permissions()

        self.mock_update_permission_property.assert_any_call(
            "Stock Entry", "MRF User", permlevel=0, ptype="delete", value=0
        )


class TestMRFUserCannotAccessOtherWarehouses(unittest.TestCase):
    """Test MRF User access is limited (no create/delete on warehouses).

    The MRF User role is configured with User Permission filtering so that
    at runtime, the admin assigns a User Permission restricting the MRF User
    to only the Wornout PPE Warehouse. The install script ensures the role
    does not have create/delete access on warehouses, limiting its scope.

    Validates: Requirements 7.2
    """

    def setUp(self):
        """Set up mock objects and import install module."""
        self.mock_add_permission = MagicMock()
        self.mock_update_permission_property = MagicMock()
        self.mock_frappe = MagicMock()

        mock_frappe_module = self.mock_frappe
        mock_frappe_module.permissions = MagicMock()
        mock_frappe_module.permissions.add_permission = self.mock_add_permission
        mock_frappe_module.permissions.update_permission_property = self.mock_update_permission_property

        self._original_modules = {}
        for mod in ["frappe", "frappe.permissions"]:
            if mod in sys.modules:
                self._original_modules[mod] = sys.modules[mod]

        sys.modules["frappe"] = mock_frappe_module
        sys.modules["frappe.permissions"] = mock_frappe_module.permissions

        import importlib
        import os

        install_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "install.py"
        )
        spec = importlib.util.spec_from_file_location("install", install_path)
        self.install_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.install_module)

    def tearDown(self):
        """Restore original sys.modules."""
        for mod, original in self._original_modules.items():
            sys.modules[mod] = original
        for mod in ["frappe", "frappe.permissions"]:
            if mod not in self._original_modules and mod in sys.modules:
                del sys.modules[mod]

    def test_mrf_user_warehouse_permissions_are_restricted(self):
        """MRF User warehouse permissions only grant read/write — no create/delete.

        This ensures MRF User cannot access arbitrary warehouses beyond what
        is explicitly allowed via User Permission. The base permissions are
        limited to read/write which, combined with User Permission filtering,
        restricts access to the Wornout PPE Warehouse only.

        Validates: Requirements 7.2
        """
        self.mock_frappe.db.exists.return_value = False

        self.install_module._setup_warehouse_permissions()

        # Collect all update_permission_property calls for Warehouse
        warehouse_calls = [
            c for c in self.mock_update_permission_property.call_args_list
            if c[0][0] == "Warehouse"
        ]

        # Extract the permission types and values using positional args
        perm_values = {}
        for c in warehouse_calls:
            args = c[0]  # positional args
            kwargs = c[1]  # keyword args
            ptype = kwargs.get("ptype", args[3] if len(args) > 3 else None)
            value = kwargs.get("value", args[4] if len(args) > 4 else None)
            if ptype is not None:
                perm_values[ptype] = value

        # Read and write should be granted
        self.assertEqual(perm_values.get("read"), 1)
        self.assertEqual(perm_values.get("write"), 1)

        # Create and delete should be denied
        self.assertEqual(perm_values.get("create"), 0)
        self.assertEqual(perm_values.get("delete"), 0)

    def test_existing_role_permission_is_not_duplicated(self):
        """If MRF User already has a permission entry, add_permission is not called again.

        This tests the idempotency of the setup function — running it multiple
        times does not create duplicate permission entries.

        Validates: Requirements 7.2
        """
        # Mock: role already has permission entry (first exists returns True)
        self.mock_frappe.db.exists.return_value = True

        self.install_module._setup_warehouse_permissions()

        # add_permission should NOT be called since entry already exists
        self.mock_add_permission.assert_not_called()

        # update_permission_property should still be called to ensure correct values
        self.assertTrue(self.mock_update_permission_property.called)


class TestSetupMRFUserPermissionsIntegration(unittest.TestCase):
    """Integration test for the full setup_mrf_user_permissions function.

    Validates: Requirements 7.1, 7.2, 14.6
    """

    def setUp(self):
        """Set up mock objects and import install module."""
        self.mock_add_permission = MagicMock()
        self.mock_update_permission_property = MagicMock()
        self.mock_frappe = MagicMock()

        mock_frappe_module = self.mock_frappe
        mock_frappe_module.permissions = MagicMock()
        mock_frappe_module.permissions.add_permission = self.mock_add_permission
        mock_frappe_module.permissions.update_permission_property = self.mock_update_permission_property

        self._original_modules = {}
        for mod in ["frappe", "frappe.permissions"]:
            if mod in sys.modules:
                self._original_modules[mod] = sys.modules[mod]

        sys.modules["frappe"] = mock_frappe_module
        sys.modules["frappe.permissions"] = mock_frappe_module.permissions

        import importlib
        import os

        install_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "install.py"
        )
        spec = importlib.util.spec_from_file_location("install", install_path)
        self.install_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.install_module)

    def tearDown(self):
        """Restore original sys.modules."""
        for mod, original in self._original_modules.items():
            sys.modules[mod] = original
        for mod in ["frappe", "frappe.permissions"]:
            if mod not in self._original_modules and mod in sys.modules:
                del sys.modules[mod]

    def test_setup_mrf_user_permissions_configures_both_doctypes(self):
        """setup_mrf_user_permissions() sets up permissions for both Warehouse and Stock Entry.

        Validates: Requirements 7.1, 7.2, 14.6
        """
        self.mock_frappe.db.exists.return_value = False

        self.install_module.setup_mrf_user_permissions()

        # Should have called add_permission twice (Warehouse + Stock Entry)
        self.assertEqual(self.mock_add_permission.call_count, 2)

        # Verify both DocTypes were configured
        add_perm_doctypes = [c[0][0] for c in self.mock_add_permission.call_args_list]
        self.assertIn("Warehouse", add_perm_doctypes)
        self.assertIn("Stock Entry", add_perm_doctypes)

        # Verify update_permission_property was called for both DocTypes
        update_doctypes = set(
            c[0][0] for c in self.mock_update_permission_property.call_args_list
        )
        self.assertIn("Warehouse", update_doctypes)
        self.assertIn("Stock Entry", update_doctypes)


if __name__ == "__main__":
    unittest.main()
