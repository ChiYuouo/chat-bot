"""CSV 数据分析能力。"""

import re
from typing import Any, Dict

import pandas as pd

from app.config import Config
from app.llm import create_chat_model
from app.safe_executor import execute_dataframe_code


def agent_answer(df: pd.DataFrame, question: str) -> Dict[str, Any]:
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
4. 如果需要画图，直接使用 plt，并且必须调用 plt.savefig(chart_path) 保存图片。
5. 不要使用 import、open、eval、exec，也不要读取或写入任何外部文件。
"""
    response = create_chat_model(Config.LLM_MODEL, temperature=0).invoke(prompt)
    code = response.content.strip()
    code = re.sub(r"^```(?:python)?\s*", "", code, flags=re.IGNORECASE)
    code = re.sub(r"\s*```$", "", code)

    execution = execute_dataframe_code(code, df)
    if execution["success"]:
        output = execution["output"] or "代码执行成功，但没有打印结果。"
    else:
        output = f"执行被拒绝或失败：{execution['error']}"

    return {"answer": output, "code": code, "chart": execution["chart"]}

