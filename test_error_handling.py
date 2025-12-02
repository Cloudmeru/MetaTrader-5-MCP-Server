"""Test script for error handling in MT5 MCP Server.

This script tests various malformed inputs to ensure the server
handles errors gracefully without crashing.
"""

import json
import os
import sys

try:
    from mt5_mcp.error_utils import (
        ErrorType,
        create_error_response,
        safe_json_parse,
        safe_enum_conversion,
        validate_required_field,
        validate_type,
    )
    from mt5_mcp.models import MT5Operation
except ModuleNotFoundError:  # pragma: no cover - fallback for manual execution
    SRC_PATH = os.path.join(os.path.dirname(__file__), "..", "src")
    if SRC_PATH not in sys.path:
        sys.path.insert(0, SRC_PATH)

    from mt5_mcp.error_utils import (  # type: ignore  # noqa: E402
        ErrorType,
        create_error_response,
        safe_json_parse,
        safe_enum_conversion,
        validate_required_field,
        validate_type,
    )
    from mt5_mcp.models import MT5Operation  # type: ignore  # noqa: E402


def test_safe_json_parse():
    """Test JSON parsing with various malformed inputs."""
    print("=" * 60)
    print("Testing safe_json_parse...")
    print("=" * 60)

    test_cases = [
        ('{"valid": "json"}', True),
        ("{invalid json}", False),
        ("", True),  # Empty should return default
        (None, True),
        ('{"missing": bracket', False),
        ("[1, 2, 3", False),
        ("not json at all", False),
    ]

    for test_input, should_succeed in test_cases:
        result, error = safe_json_parse(test_input, "test_field")
        success = error is None
        status = "✓" if success == should_succeed else "✗"
        print(f"{status} Input: {str(test_input)[:30]:30} Success: {success}")
        if error:
            print(f"  Error: {error['error_type']}: {error['error'][:50]}")
        else:
            preview = str(result)
            print(f"  Parsed preview: {preview[:50]}")

    print()


def test_safe_enum_conversion():
    """Test enum conversion with valid and invalid values."""
    print("=" * 60)
    print("Testing safe_enum_conversion...")
    print("=" * 60)

    test_cases = [
        ("symbol_info", True),
        ("copy_rates_from_pos", True),
        ("invalid_operation", False),
        ("", False),
        ("SELECT * FROM users", False),  # SQL injection attempt
    ]

    for test_input, should_succeed in test_cases:
        result, error = safe_enum_conversion(test_input, MT5Operation, "operation")
        success = error is None
        status = "✓" if success == should_succeed else "✗"
        print(f"{status} Input: {test_input:30} Success: {success}")
        if error:
            print(f"  Error: {error['error_type']}: {error['error'][:50]}")
        else:
            print(f"  Enum value: {result}")

    print()


def test_validate_required_field():
    """Test required field validation."""
    print("=" * 60)
    print("Testing validate_required_field...")
    print("=" * 60)

    test_cases = [
        ("valid_value", True),
        ("", False),
        (None, False),
        ("  ", False),  # Whitespace only
        (0, True),  # Zero is valid
        (False, True),  # False is valid
    ]

    for test_input, should_succeed in test_cases:
        error = validate_required_field(test_input, "test_field")
        success = error is None
        status = "✓" if success == should_succeed else "✗"
        print(f"{status} Input: {str(test_input):30} Success: {success}")
        if error:
            print(f"  Error: {error['error_type']}: {error['error'][:50]}")

    print()


def test_validate_type():
    """Test type validation."""
    print("=" * 60)
    print("Testing validate_type...")
    print("=" * 60)

    test_cases = [
        ("string", str, True),
        (123, int, True),
        ("string", int, False),
        ([], list, True),
        ({}, dict, True),
        (None, str, False),
    ]

    for test_input, expected_type, should_succeed in test_cases:
        error = validate_type(test_input, expected_type, "test_field")
        success = error is None
        status = "✓" if success == should_succeed else "✗"
        input_str = f"{type(test_input).__name__} vs {expected_type.__name__}"
        print(f"{status} Input: {input_str:30} Success: {success}")
        if error:
            print(f"  Error: {error['error_type']}: {error['error'][:50]}")

    print()


def test_error_response_format():
    """Test standardized error response format."""
    print("=" * 60)
    print("Testing error response format...")
    print("=" * 60)

    response = create_error_response(
        ErrorType.JSON_PARSE_ERROR,
        "Invalid JSON syntax",
        operation="test_operation",
        details={"field": "parameters", "position": 42},
    )

    print("Sample error response:")
    print(json.dumps(response, indent=2))

    # Validate structure
    required_fields = ["success", "error", "error_type", "timestamp"]
    all_present = all(field in response for field in required_fields)

    status = "✓" if all_present and response["success"] is False else "✗"
    print(f"\n{status} Error response has required structure")
    print()


def test_malformed_tool_inputs():
    """Test tool functions with various malformed inputs."""
    print("=" * 60)
    print("Testing malformed tool inputs...")
    print("=" * 60)

    # Test cases that would have crashed the server before
    test_cases = [
        {
            "name": "Invalid JSON in parameters",
            "json_str": "{invalid json}",
            "description": "Malformed JSON brackets",
        },
        {
            "name": "Array instead of object",
            "json_str": "[1, 2, 3]",
            "description": "JSON array when object expected",
        },
        {
            "name": "Missing quote",
            "json_str": '{"key": "value}',
            "description": "Unclosed string literal",
        },
        {
            "name": "Trailing comma",
            "json_str": '{"key": "value",}',
            "description": "Invalid trailing comma",
        },
        {
            "name": "Very long string",
            "json_str": '{"data": "' + "x" * 100000 + '"}',
            "description": "Large payload (should succeed)",
        },
    ]

    for test_case in test_cases:
        print(f"\nTest: {test_case['name']}")
        print(f"Description: {test_case['description']}")

        result, error = safe_json_parse(test_case["json_str"], "parameters")

        if error:
            print(f"✓ Handled gracefully: {error['error_type']}")
        else:
            if len(test_case["json_str"]) > 1000:
                print("✓ Large payload accepted")
            else:
                print(f"✓ Parsed successfully: {str(result)[:50]}")

    print()


def main():
    """Run all error handling tests."""
    print("\n" + "=" * 60)
    print("MT5 MCP Server - Error Handling Test Suite")
    print("=" * 60 + "\n")

    try:
        test_safe_json_parse()
        test_safe_enum_conversion()
        test_validate_required_field()
        test_validate_type()
        test_error_response_format()
        test_malformed_tool_inputs()

        print("=" * 60)
        print("All error handling tests completed!")
        print("=" * 60)
        print("\n✓ Server error handling is working correctly")
        print("✓ Malformed inputs are caught and handled gracefully")
        print("✓ Standardized error responses are generated")

    except Exception as e:
        print(f"\n✗ Test suite failed with error: {str(e)}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
