"""CSV 数据分析能力。"""

import io
import os
import re
import sys
from typing import Any, Dict

import pandas as pd

from app.config import Config
from app.llm import create_chat_model


def agent_answer(df: pd.DataFrame, question: str) -> Dict[str, Any]:
    import numpy as np

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
4. 如果需要画图，使用 matplotlib 并保存到 chart.png。
"""
    response = create_chat_model(Config.LLM_MODEL, temperature=0).invoke(prompt)
    code = response.content.strip()
    code = re.sub(r"^```(?:python)?\s*", "", code, flags=re.IGNORECASE)
    code = re.sub(r"\s*```$", "", code)

    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        exec_globals = {"df": df, "pd": pd, "np": np}
        if "plt" in code or "matplotlib" in code:
            try:
                import matplotlib
                matplotlib.use("Agg")
                import matplotlib.pyplot as plt
                exec_globals["plt"] = plt
                exec_globals["matplotlib"] = matplotlib
            except ImportError:
                code = re.sub(r".*plt\..*\n?", "", code)
                code = re.sub(r".*matplotlib.*\n?", "", code)
                print("注意：matplotlib 未安装，已跳过绘图代码\n")

        exec(code, exec_globals)
        output = sys.stdout.getvalue()
    except Exception as exc:
        output = f"执行出错: {exc}"
    finally:
        sys.stdout = old_stdout

    chart_path = "chart.png" if os.path.exists("chart.png") else None
    return {"answer": output, "code": code, "chart": chart_path}

