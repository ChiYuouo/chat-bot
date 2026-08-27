"""CSV 数据分析能力。"""

import ast
import re
from collections.abc import Callable
from typing import Any, Dict

import pandas as pd

from app.config import Config
from app.llm import create_chat_model
from app.safe_executor import execute_dataframe_code


_INJECTED_IMPORTS = {
    ("matplotlib.pyplot", "plt"),
    ("numpy", "np"),
    ("pandas", "pd"),
}


class _GeneratedCodeNormalizer(ast.NodeTransformer):
    """清理系统已提供的导入，并控制图表输出路径。"""

    def __init__(self) -> None:
        self.changed = False

    def visit_Import(self, node: ast.Import) -> ast.AST | None:
        remaining_names = [
            value
            for value in node.names
            if (value.name, value.asname) not in _INJECTED_IMPORTS
        ]
        if len(remaining_names) != len(node.names):
            self.changed = True
        if not remaining_names:
            return None
        node.names = remaining_names
        return node

    def visit_ImportFrom(self, node: ast.ImportFrom) -> ast.AST | None:
        # 同时兼容模型偶尔生成的 ``from matplotlib import pyplot as plt``。
        if node.module != "matplotlib" or node.level != 0:
            return node
        remaining_names = [
            value
            for value in node.names
            if not (value.name == "pyplot" and value.asname == "plt")
        ]
        if len(remaining_names) != len(node.names):
            self.changed = True
        if not remaining_names:
            return None
        node.names = remaining_names
        return node

    def visit_Call(self, node: ast.Call) -> ast.AST:
        self.generic_visit(node)
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "savefig":
            return node

        if (
            node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            node.args[0] = ast.Name(id="chart_path", ctx=ast.Load())
            self.changed = True

        for keyword in node.keywords:
            if (
                keyword.arg == "fname"
                and isinstance(keyword.value, ast.Constant)
                and isinstance(keyword.value.value, str)
            ):
                keyword.value = ast.Name(id="chart_path", ctx=ast.Load())
                self.changed = True
        return node


def _normalize_generated_code(code: str) -> str:
    """修正常见的冗余导入和固定图片路径，其他危险代码仍由执行器拒绝。"""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code

    normalizer = _GeneratedCodeNormalizer()
    tree = normalizer.visit(tree)
    if not normalizer.changed:
        return code
    ast.fix_missing_locations(tree)
    return ast.unparse(tree)


def agent_answer(
    df: pd.DataFrame,
    question: str,
    status_callback: Callable[[str], None] | None = None,
) -> Dict[str, Any]:
    df_meta = {
        "shape": df.shape,
        "columns": list(df.columns),
        "dtypes": df.dtypes.astype(str).to_dict(),
        "sample": df.sample(n=min(5, len(df)), random_state=42).to_string(index=False),
    }

    prompt = f"""你是数据分析专家。根据以下 DataFrame 元信息和用户问题，生成 Pandas 代码。

DataFrame 元信息：
- shape: {df_meta['shape']}
- columns: {df_meta['columns']}
- dtypes: {df_meta['dtypes']}
- sample:
{df_meta['sample']}

用户问题：{question}

要求：
1. 只输出 Python 代码，不要解释。
2. 代码中使用 df 表示 DataFrame。
3. 最后使用 print() 输出结果。
4. 系统已经提供 df、pd、np、plt 和 chart_path，禁止使用任何 import。
5. 如果需要画图，直接使用 plt，并且必须调用 plt.savefig(chart_path) 保存图片；chart_path 是系统提供的变量，禁止写成字符串文件名。
6. 不要使用 open、eval、exec，也不要读取或写入任何外部文件。
"""
    if status_callback:
        status_callback("正在生成数据分析代码...")
    response = create_chat_model(Config.LLM_MODEL, temperature=0).invoke(prompt)
    code = response.content.strip()
    code = re.sub(r"^```(?:python)?\s*", "", code, flags=re.IGNORECASE)
    code = re.sub(r"\s*```$", "", code)
    code = _normalize_generated_code(code)

    if status_callback:
        status_callback("正在校验并执行分析代码...")
    execution = execute_dataframe_code(code, df)
    if execution["success"]:
        output = execution["output"] or "代码执行成功，但没有打印结果。"
    else:
        output = f"执行被拒绝或失败：{execution['error']}"

    return {"answer": output, "code": code, "chart": execution["chart"]}

