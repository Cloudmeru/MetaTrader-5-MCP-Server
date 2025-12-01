"""
Unit tests for executor.py - Python code execution.
"""

import unittest
from unittest.mock import Mock, patch
import sys

# Mock MT5
import sys
from unittest.mock import MagicMock
mock_mt5 = MagicMock()
mock_mt5.initialize.return_value = True
sys.modules['MetaTrader5'] = mock_mt5


class TestExecutor(unittest.TestCase):
    """Test code execution functionality."""
    
    def setUp(self):
        """Set up test namespace."""
        self.namespace = {
            'x': 10,
            'y': 20,
            'data': [1, 2, 3, 4, 5],
        }
    
    def test_execute_simple_expression(self):
        """Test executing simple expression."""
        from mt5_mcp.executor import execute_command
        
        result = execute_command("x + y", self.namespace)
        
        self.assertIn("30", result)
    
    def test_execute_assignment(self):
        """Test executing assignment."""
        from mt5_mcp.executor import execute_command
        
        result = execute_command("z = x * y", self.namespace)
        
        self.assertEqual(self.namespace['z'], 200)
    
    def test_execute_with_result_variable(self):
        """Test executing code with result variable."""
        from mt5_mcp.executor import execute_command
        
        result = execute_command("result = x + y", self.namespace)
        
        self.assertIn("30", result)
    
    def test_execute_multiline(self):
        """Test executing multiline code."""
        from mt5_mcp.executor import execute_command
        
        code = """
total = 0
for i in data:
    total += i
result = total
"""
        result = execute_command(code, self.namespace)
        
        self.assertIn("15", result)
    
    def test_execute_with_print(self):
        """Test code execution with print statements."""
        from mt5_mcp.executor import execute_command
        
        result = execute_command("print('Hello World')", self.namespace)
        
        self.assertIn("Hello World", result)
    
    def test_execute_syntax_error(self):
        """Test handling syntax errors."""
        from mt5_mcp.executor import execute_command
        
        result = execute_command("x +* y", self.namespace, show_traceback=True)
        
        self.assertIn("Error", result)
        self.assertIn("Syntax", result)
    
    def test_execute_runtime_error(self):
        """Test handling runtime errors."""
        from mt5_mcp.executor import execute_command
        
        result = execute_command("1/0", self.namespace, show_traceback=False)
        
        self.assertIn("Error", result)
        self.assertIn("ZeroDivisionError", result)
    
    def test_execute_with_pandas(self):
        """Test execution with pandas operations."""
        from mt5_mcp.executor import execute_command
        import pandas as pd
        
        self.namespace['pd'] = pd
        
        code = """
import pandas as pd
df = pd.DataFrame({'a': [1, 2, 3], 'b': [4, 5, 6]})
result = df
"""
        result = execute_command(code, self.namespace)
        
        # Should format as markdown table
        self.assertIn("a", result)
        self.assertIn("b", result)


class TestFormatResult(unittest.TestCase):
    """Test result formatting."""
    
    def test_format_none(self):
        """Test formatting None."""
        from mt5_mcp.executor import format_result
        
        result = format_result(None)
        
        self.assertEqual(result, "")
    
    def test_format_dict(self):
        """Test formatting dictionary."""
        from mt5_mcp.executor import format_result
        
        data = {"key1": "value1", "key2": 42}
        result = format_result(data)
        
        self.assertIn("key1", result)
        self.assertIn("value1", result)
        self.assertIn("42", result)
    
    def test_format_list(self):
        """Test formatting list."""
        from mt5_mcp.executor import format_result
        
        data = [1, 2, 3, 4, 5]
        result = format_result(data)
        
        self.assertIn("1", result)
        self.assertIn("5", result)
    
    def test_format_dataframe(self):
        """Test formatting pandas DataFrame."""
        from mt5_mcp.executor import format_result
        import pandas as pd
        
        df = pd.DataFrame({'a': [1, 2], 'b': [3, 4]})
        result = format_result(df)
        
        # Should be markdown table
        self.assertIn("a", result)
        self.assertIn("b", result)
        self.assertIn("|", result)  # Markdown table separator
    
    def test_format_list_of_dicts(self):
        """Test formatting list of dictionaries."""
        from mt5_mcp.executor import format_result
        
        data = [
            {"name": "Alice", "age": 30},
            {"name": "Bob", "age": 25},
        ]
        result = format_result(data)
        
        # Should be formatted as table
        self.assertIn("Alice", result)
        self.assertIn("Bob", result)


if __name__ == '__main__':
    unittest.main()
