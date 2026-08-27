import unittest
from unittest.mock import Mock, patch

import pandas as pd

from app.capabilities.data_agent import _normalize_generated_code, agent_answer


class ChartPathNormalizationTests(unittest.TestCase):
    def test_rewrites_literal_savefig_path(self):
        code = _normalize_generated_code("plt.plot([1, 2])\nplt.savefig('result.png')")

        self.assertIn("plt.savefig(chart_path)", code)
        self.assertNotIn("result.png", code)

    def test_rewrites_literal_fname_keyword(self):
        code = _normalize_generated_code("plt.savefig(fname='result.png', dpi=120)")

        self.assertIn("fname=chart_path", code)

    def test_keeps_dynamic_path_for_safe_executor_to_reject(self):
        original = "plt.savefig(user_supplied_path)"

        self.assertEqual(_normalize_generated_code(original), original)

    def test_removes_imports_for_injected_libraries(self):
        code = _normalize_generated_code(
            "import matplotlib.pyplot as plt\nimport pandas as pd\nimport numpy as np\nprint(df)"
        )

        self.assertNotIn("import", code)
        self.assertIn("print(df)", code)

    def test_keeps_unsafe_import_for_safe_executor_to_reject(self):
        code = _normalize_generated_code(
            "import matplotlib.pyplot as plt\nimport os\nplt.plot([1, 2])"
        )

        self.assertNotIn("matplotlib", code)
        self.assertIn("import os", code)

    @patch("app.capabilities.data_agent.execute_dataframe_code")
    @patch("app.capabilities.data_agent.create_chat_model")
    def test_agent_executes_normalized_code(self, create_chat_model, execute_dataframe_code):
        llm = Mock()
        llm.invoke.return_value = Mock(
            content=(
                "import matplotlib.pyplot as plt\n"
                "plt.plot(df['price'])\n"
                "plt.savefig('price_distribution.png')"
            )
        )
        create_chat_model.return_value = llm
        execute_dataframe_code.return_value = {
            "success": True,
            "output": "完成",
            "error": None,
            "chart": b"png",
        }

        statuses = []
        result = agent_answer(
            pd.DataFrame({"price": [1, 2]}),
            "绘制价格分布",
            statuses.append,
        )

        executed_code = execute_dataframe_code.call_args.args[0]
        self.assertNotIn("import", executed_code)
        self.assertIn("plt.savefig(chart_path)", executed_code)
        self.assertEqual(result["code"], executed_code)
        self.assertEqual(result["chart"], b"png")
        self.assertEqual(statuses, [
            "正在生成数据分析代码...",
            "正在校验并执行分析代码...",
        ])


if __name__ == "__main__":
    unittest.main()
