"""受限执行大模型生成的数据分析代码。

该模块用于降低本地演示时直接执行模型代码的风险，但不能替代生产环境中的
容器沙箱、网络隔离和操作系统级资源限制。
"""

from __future__ import annotations

import ast
import io
import multiprocessing as mp
import os
import tempfile
from contextlib import redirect_stdout
from queue import Empty
from typing import Any, Dict, Optional

import pandas as pd


MAX_OUTPUT_CHARS = 20_000
PROTECTED_NAMES = {"__builtins__", "chart_path", "pd", "np", "plt"}
FORBIDDEN_CALLS = {
    "breakpoint",
    "compile",
    "delattr",
    "dir",
    "eval",
    "exec",
    "getattr",
    "globals",
    "help",
    "input",
    "locals",
    "memoryview",
    "open",
    "setattr",
    "vars",
    "__import__",
}
FORBIDDEN_METHODS = {
    "ctypeslib",
    "eval",
    "fromfile",
    "genfromtxt",
    "getenv",
    "imread",
    "load",
    "loadtxt",
    "makedirs",
    "memmap",
    "mkdir",
    "popen",
    "query",
    "read_clipboard",
    "read_csv",
    "read_excel",
    "read_feather",
    "read_fwf",
    "read_gbq",
    "read_hdf",
    "read_html",
    "read_json",
    "read_orc",
    "read_parquet",
    "read_pickle",
    "read_sas",
    "read_spss",
    "read_sql",
    "read_sql_query",
    "read_sql_table",
    "read_stata",
    "read_table",
    "read_xml",
    "save",
    "savetxt",
    "system",
    "to_clipboard",
    "to_csv",
    "to_excel",
    "to_feather",
    "to_gbq",
    "to_hdf",
    "to_html",
    "to_json",
    "to_latex",
    "to_markdown",
    "to_orc",
    "to_parquet",
    "to_pickle",
    "to_sql",
    "to_stata",
    "to_xml",
    "unlink",
}
FORBIDDEN_ATTRIBUTES = {
    "ctypes",
    "ctypeslib",
    "environ",
    "io",
    "os",
    "pathlib",
    "socket",
    "subprocess",
    "sys",
}


class UnsafeCodeError(ValueError):
    """模型代码未通过安全检查。"""


class _CodeValidator(ast.NodeVisitor):
    def visit_Import(self, node: ast.Import) -> None:
        raise UnsafeCodeError("不允许使用 import")

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        raise UnsafeCodeError("不允许使用 import")

    def visit_Global(self, node: ast.Global) -> None:
        raise UnsafeCodeError("不允许使用 global")

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        raise UnsafeCodeError("不允许使用 nonlocal")

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        raise UnsafeCodeError("不允许定义类")

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        raise UnsafeCodeError("不允许定义函数")

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        raise UnsafeCodeError("不允许定义异步函数")

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr.startswith("_"):
            raise UnsafeCodeError("不允许访问私有或魔术属性")
        if node.attr in FORBIDDEN_ATTRIBUTES:
            raise UnsafeCodeError(f"不允许访问属性 {node.attr}")
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id.startswith("__"):
            raise UnsafeCodeError("不允许访问魔术名称")
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            self._check_assignment_target(target)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self._check_assignment_target(node.target)
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self._check_assignment_target(node.target)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        name = self._call_name(node.func)
        method = name.rsplit(".", 1)[-1]
        if name in FORBIDDEN_CALLS or method in FORBIDDEN_METHODS:
            raise UnsafeCodeError(f"不允许调用 {name}")
        if method == "savefig" and not self._uses_controlled_chart_path(node):
            raise UnsafeCodeError("savefig 必须保存到系统提供的 chart_path")
        self.generic_visit(node)

    @staticmethod
    def _call_name(node: ast.expr) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            prefix = _CodeValidator._call_name(node.value)
            return f"{prefix}.{node.attr}" if prefix else node.attr
        return "<动态调用>"

    @staticmethod
    def _uses_controlled_chart_path(node: ast.Call) -> bool:
        if node.args:
            return isinstance(node.args[0], ast.Name) and node.args[0].id == "chart_path"
        for keyword in node.keywords:
            if keyword.arg == "fname":
                return isinstance(keyword.value, ast.Name) and keyword.value.id == "chart_path"
        return False

    @staticmethod
    def _check_assignment_target(target: ast.expr) -> None:
        if isinstance(target, ast.Name) and target.id in PROTECTED_NAMES:
            raise UnsafeCodeError(f"不允许覆盖受保护变量 {target.id}")
        if isinstance(target, (ast.Tuple, ast.List)):
            for item in target.elts:
                _CodeValidator._check_assignment_target(item)


def validate_code(code: str) -> None:
    """检查代码是否包含明显的文件、网络或动态执行行为。"""
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise UnsafeCodeError(f"代码语法错误：{exc.msg}") from exc
    _CodeValidator().visit(tree)


SAFE_BUILTINS = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "enumerate": enumerate,
    "float": float,
    "int": int,
    "len": len,
    "list": list,
    "max": max,
    "min": min,
    "print": print,
    "range": range,
    "round": round,
    "set": set,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "zip": zip,
}


def _execute_worker(
    code: str,
    df: pd.DataFrame,
    chart_path: str,
    result_queue: Any,
) -> None:
    """在子进程中执行已通过静态检查的代码。"""
    import numpy as np

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    output = io.StringIO()
    namespace = {
        "__builtins__": SAFE_BUILTINS,
        "chart_path": chart_path,
        "df": df,
        "np": np,
        "pd": pd,
        "plt": plt,
    }
    try:
        with redirect_stdout(output):
            exec(compile(code, "<generated-analysis>", "exec"), namespace, namespace)
        text = output.getvalue()
        if len(text) > MAX_OUTPUT_CHARS:
            text = text[:MAX_OUTPUT_CHARS] + "\n...输出已截断"
        result_queue.put({"success": True, "output": text, "error": None})
    except Exception as exc:
        result_queue.put({
            "success": False,
            "output": output.getvalue()[:MAX_OUTPUT_CHARS],
            "error": f"{type(exc).__name__}: {exc}",
        })
    finally:
        plt.close("all")


def execute_dataframe_code(
    code: str,
    df: pd.DataFrame,
    timeout_seconds: float = 8.0,
) -> Dict[str, Any]:
    """校验并限时执行代码，返回文本输出和可选的 PNG 字节。"""
    try:
        validate_code(code)
    except UnsafeCodeError as exc:
        return {"success": False, "output": "", "error": str(exc), "chart": None}

    descriptor, chart_path = tempfile.mkstemp(suffix=".png")
    os.close(descriptor)
    os.unlink(chart_path)

    context = mp.get_context("spawn")
    result_queue = context.Queue()
    process = context.Process(
        target=_execute_worker,
        args=(code, df, chart_path, result_queue),
        daemon=True,
    )

    chart: Optional[bytes] = None
    try:
        process.start()
        process.join(timeout_seconds)
        if process.is_alive():
            process.terminate()
            process.join(1)
            return {
                "success": False,
                "output": "",
                "error": f"执行超过 {timeout_seconds:g} 秒，已终止",
                "chart": None,
            }

        try:
            result = result_queue.get(timeout=1)
        except Empty:
            result = {
                "success": False,
                "output": "",
                "error": f"执行进程异常退出（退出码 {process.exitcode}）",
            }

        if result["success"] and os.path.exists(chart_path):
            with open(chart_path, "rb") as chart_file:
                chart = chart_file.read()
        result["chart"] = chart
        return result
    finally:
        result_queue.close()
        result_queue.join_thread()
        if os.path.exists(chart_path):
            os.unlink(chart_path)
