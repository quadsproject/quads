import json
from unittest.mock import MagicMock, patch, Mock

import pytest


class TestJsonLoadsSafety:
    """Unit tests verifying json.loads is used instead of eval() for array parsing."""

    def test_json_loads_parses_valid_array(self):
        """
        | GIVEN: A valid JSON array string
        | WHEN: json.loads is called
        | THEN: The array is parsed correctly
        """
        value = '["em1", "em2"]'
        result = json.loads(value)
        assert result == ["em1", "em2"]

    def test_json_loads_rejects_malicious_payload(self):
        """
        | GIVEN: A malicious payload that starts with [ and ends with ]
        | WHEN: json.loads is called
        | THEN: JSONDecodeError is raised, preventing code execution
        """
        malicious = "[__import__('os').system('id')]"
        with pytest.raises(json.JSONDecodeError):
            json.loads(malicious)

    def test_json_loads_rejects_python_builtin_access(self):
        """
        | GIVEN: A payload attempting to access Python builtins
        | WHEN: json.loads is called
        | THEN: JSONDecodeError is raised
        """
        malicious = "[__builtins__]"
        with pytest.raises(json.JSONDecodeError):
            json.loads(malicious)

    def test_json_loads_rejects_eval_traversal(self):
        """
        | GIVEN: A payload attempting eval traversal
        | WHEN: json.loads is called
        | THEN: JSONDecodeError is raised
        """
        malicious = "[eval('1+1')]"
        with pytest.raises(json.JSONDecodeError):
            json.loads(malicious)


class TestHostDaoFilterHostsDict:
    """Unit tests for HostDao.filter_hosts_dict() json.loads behavior."""

    def test_filter_uses_json_loads_not_eval(self):
        """
        | GIVEN: The host.py module uses json.loads for array parsing
        | WHEN: We inspect the source code
        | THEN: eval() is not present in the array parsing logic
        """
        import inspect

        from quads.server.dao.host import HostDao

        source = inspect.getsource(HostDao.filter_hosts_dict)
        assert "eval(" not in source, "filter_hosts_dict should not use eval()"
        assert "json.loads" in source, "filter_hosts_dict should use json.loads"

    def test_filter_catches_json_decode_error(self):
        """
        | GIVEN: The host.py module catches JSONDecodeError
        | WHEN: We inspect the source code
        | THEN: json.JSONDecodeError is in the except clause
        """
        import inspect

        from quads.server.dao.host import HostDao

        source = inspect.getsource(HostDao.filter_hosts_dict)
        assert "JSONDecodeError" in source, "filter_hosts_dict should catch JSONDecodeError"


class TestSelfAssignmentOwner:
    """Unit tests for owner derivation in create_self_assignment()."""

    def test_owner_sourced_from_current_user(self):
        """
        | GIVEN: The create_self_assignment function
        | WHEN: We inspect its source code
        | THEN: Owner is derived from g.current_user, not data.get('owner')
        """
        import inspect

        from quads.server.blueprints.assignments import create_self_assignment

        source = inspect.getsource(create_self_assignment)
        assert "g.current_user.email" in source, "Owner should be derived from g.current_user"

    def test_owner_not_from_request_body(self):
        """
        | GIVEN: The create_self_assignment function
        | WHEN: We inspect its source code
        | THEN: owner is not obtained from data.get('owner')
        """
        import inspect

        from quads.server.blueprints.assignments import create_self_assignment

        source = inspect.getsource(create_self_assignment)
        assert 'data.get("owner")' not in source, "Owner should not come from request body"
        assert "data.get('owner')" not in source, "Owner should not come from request body"

    def test_owner_not_in_required_fields(self):
        """
        | GIVEN: The create_self_assignment function
        | WHEN: We inspect its source code
        | THEN: 'owner' is not in required_fields
        """
        import inspect

        from quads.server.blueprints.assignments import create_self_assignment

        source = inspect.getsource(create_self_assignment)

        required_start = source.find("required_fields = [")
        required_end = source.find("]", required_start)
        required_block = source[required_start:required_end + 1]
        assert '"owner"' not in required_block, "owner should not be in required_fields"
        assert "'owner'" not in required_block, "owner should not be in required_fields"


class TestAssignmentPatchBooleanEval:
    """Unit tests for eval() usage in assignment PATCH endpoint."""

    def test_assignment_patch_uses_eval_for_booleans(self):
        """
        | GIVEN: The update_assignment function uses eval() for boolean conversion
        | WHEN: We inspect its source code
        | THEN: eval() is still present for boolean conversion (admin-only, guarded)
        """
        import inspect

        from quads.server.blueprints.assignments import update_assignment

        source = inspect.getsource(update_assignment)

        boolean_eval_present = "eval(_value.lower().capitalize())" in source
        boolean_guard_present = 'in ["true", "false"]' in source
        assert boolean_eval_present and boolean_guard_present, (
            "Boolean eval should remain guarded by whitelist check (admin-only endpoint)"
        )
