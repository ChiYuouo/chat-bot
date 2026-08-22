import unittest

import pandas as pd

from app.safe_executor import UnsafeCodeError, execute_dataframe_code, validate_code


class SafeExecutorValidationTests(unittest.TestCase):
    def test_allows_normal_dataframe_analysis(self):
        validate_code("result = df.groupby('category').size()\nprint(result)")

    def test_allows_chart_only_at_controlled_path(self):
        validate_code("df.plot(kind='bar')\nplt.savefig(chart_path)")

    def test_rejects_import(self):
        with self.assertRaisesRegex(UnsafeCodeError, "import"):
            validate_code("import os\nprint(os.environ)")

    def test_rejects_file_access(self):
        with self.assertRaisesRegex(UnsafeCodeError, "open"):
            validate_code("print(open('secret.txt').read())")

    def test_rejects_magic_attribute_escape(self):
        with self.assertRaisesRegex(UnsafeCodeError, "魔术属性"):
            validate_code("print(df.__class__)")

    def test_rejects_library_escape_to_operating_system(self):
        with self.assertRaises(UnsafeCodeError):
            validate_code("pd.io.common.os.system('whoami')")

    def test_rejects_arbitrary_chart_path(self):
        with self.assertRaisesRegex(UnsafeCodeError, "chart_path"):
            validate_code("plt.savefig('other.png')")

    def test_rejects_overwriting_chart_path(self):
        with self.assertRaisesRegex(UnsafeCodeError, "受保护变量"):
            validate_code("chart_path = 'other.png'")

    def test_executes_safe_code_in_worker_process(self):
        result = execute_dataframe_code(
            "print(df['value'].sum())",
            pd.DataFrame({"value": [1, 2, 3]}),
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["output"].strip(), "6")
        self.assertIsNone(result["chart"])

    def test_returns_chart_as_png_bytes(self):
        result = execute_dataframe_code(
            "df.plot(kind='bar')\nplt.savefig(chart_path)",
            pd.DataFrame({"value": [1, 2, 3]}),
        )
        self.assertTrue(result["success"])
        self.assertTrue(result["chart"].startswith(b"\x89PNG"))

    def test_stops_code_after_timeout(self):
        result = execute_dataframe_code(
            "while True:\n    pass",
            pd.DataFrame({"value": [1]}),
            timeout_seconds=0.2,
        )
        self.assertFalse(result["success"])
        self.assertIn("已终止", result["error"])


if __name__ == "__main__":
    unittest.main()
