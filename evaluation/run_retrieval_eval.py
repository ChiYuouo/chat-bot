"""对比纯向量、混合检索和完整检索链路的轻量评测脚本。"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import Config
from app.ingestion import ingest_pdf, ingest_text_file
from app.knowledge_base import ensure_indexes
from app.rag import hybrid_retrieve, llm_rerank, rewrite_query
from app.source_utils import document_content


DEFAULT_QUESTIONS = ROOT / "evaluation" / "questions.json"
DEFAULT_OUTPUT_DIR = ROOT / "evaluation" / "results"


def _normalize(value: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", value.lower())


def _load_questions(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as file:
        questions = json.load(file)
    if not isinstance(questions, list) or not questions:
        raise ValueError("评测集必须是非空 JSON 数组")
    return questions


def _load_chunks() -> list[Any]:
    sources = [
        ROOT / "data" / "STL.md",
        ROOT / "data" / "2.Java基础面试篇-4.16.pdf",
        ROOT / "data" / "sample_document.pdf",
    ]
    chunks: list[Any] = []
    for path in sources:
        if not path.exists():
            raise FileNotFoundError(f"缺少评测资料：{path}")
        if path.suffix.lower() == ".pdf":
            _, source_chunks = ingest_pdf(path.read_bytes(), source_name=path.name)
        else:
            _, source_chunks = ingest_text_file(path.read_bytes(), source_name=path.name)
        chunks.extend(source_chunks)
    return chunks


def _is_relevant(document: Any, question: dict[str, Any]) -> bool:
    if not question["answerable"]:
        return False
    if document.metadata.get("source") != question["expected_source"]:
        return False
    content = _normalize(document_content(document))
    return all(_normalize(term) in content for term in question["evidence_terms"])


def _validate_ground_truth(chunks: list[Any], questions: list[dict[str, Any]]) -> None:
    invalid = []
    for question in questions:
        if question["answerable"] and not any(
            _is_relevant(chunk, question) for chunk in chunks
        ):
            invalid.append(question["id"])
    if invalid:
        raise ValueError(
            "以下题目的证据词没有同时出现在同一 Chunk 中：" + ", ".join(invalid)
        )


def _rank(documents: list[Any], question: dict[str, Any]) -> int | None:
    for index, document in enumerate(documents, start=1):
        if _is_relevant(document, question):
            return index
    return None


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[position]


def _evaluate_mode(
    mode: str,
    questions: list[dict[str, Any]],
    vector_store: Any,
    keyword_index: Any,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = []
    for index, question in enumerate(questions, start=1):
        started = time.perf_counter()
        rewrite_applied = False
        rerank_applied = False
        fallback_reason = None

        if mode == "vector":
            documents = vector_store.similarity_search(
                question["question"],
                k=Config.FINAL_CONTEXT_K,
            )
        elif mode == "hybrid":
            candidates, _ = hybrid_retrieve(
                question["question"],
                vector_store,
                keyword_index,
                per_route_k=Config.RETRIEVAL_K,
                fusion_k=Config.FINAL_CONTEXT_K,
            )
            documents = [candidate.document for candidate in candidates]
        elif mode == "full":
            rewritten, rewrite_debug = rewrite_query(
                question["question"],
                question.get("history", []),
            )
            rewrite_applied = bool(rewrite_debug.get("applied"))
            candidates, _ = hybrid_retrieve(
                rewritten,
                vector_store,
                keyword_index,
                per_route_k=Config.RETRIEVAL_K,
                fusion_k=Config.FUSION_K,
                original_query=question["question"],
            )
            reranked, rerank_debug = llm_rerank(rewritten, candidates)
            rerank_applied = bool(rerank_debug.get("applied"))
            fallback_reason = rerank_debug.get("reason")
            documents = [
                candidate.document
                for candidate in reranked[: Config.FINAL_CONTEXT_K]
            ]
        else:
            raise ValueError(f"未知评测模式：{mode}")

        latency_ms = round((time.perf_counter() - started) * 1000, 1)
        relevant_rank = _rank(documents, question)
        abstained = not documents
        if question["answerable"]:
            correct = relevant_rank is not None
        else:
            correct = abstained

        rows.append({
            "mode": mode,
            "id": question["id"],
            "category": question["category"],
            "question": question["question"],
            "answerable": question["answerable"],
            "expected_source": question["expected_source"],
            "relevant_rank": relevant_rank,
            "hit_at_4": relevant_rank is not None,
            "abstained": abstained,
            "correct_decision": correct,
            "latency_ms": latency_ms,
            "rewrite_applied": rewrite_applied,
            "rerank_applied": rerank_applied,
            "fallback_reason": fallback_reason,
            "returned_sources": " | ".join(
                str(document.metadata.get("source", "")) for document in documents
            ),
        })
        print(
            f"[{mode} {index:02d}/{len(questions)}] {question['id']}: "
            f"{'OK' if correct else 'MISS'} ({latency_ms:.1f} ms)",
            flush=True,
        )

    answerable = [row for row in rows if row["answerable"]]
    unanswerable = [row for row in rows if not row["answerable"]]
    reciprocal_ranks = [
        1 / row["relevant_rank"] if row["relevant_rank"] else 0
        for row in answerable
    ]
    latencies = [float(row["latency_ms"]) for row in rows]
    category_hits: dict[str, list[bool]] = defaultdict(list)
    for row in answerable:
        category_hits[row["category"]].append(bool(row["hit_at_4"]))

    summary = {
        "mode": mode,
        "question_count": len(rows),
        "answerable_count": len(answerable),
        "unanswerable_count": len(unanswerable),
        "hit_at_4": round(
            sum(row["hit_at_4"] for row in answerable) / len(answerable), 4
        ),
        "mrr_at_4": round(statistics.fmean(reciprocal_ranks), 4),
        "abstention_accuracy": round(
            sum(row["abstained"] for row in unanswerable) / len(unanswerable), 4
        ),
        "overall_decision_accuracy": round(
            sum(row["correct_decision"] for row in rows) / len(rows), 4
        ),
        "average_latency_ms": round(statistics.fmean(latencies), 1),
        "p95_latency_ms": round(_percentile(latencies, 0.95), 1),
        "rewrite_applied_count": sum(row["rewrite_applied"] for row in rows),
        "rerank_applied_count": sum(row["rerank_applied"] for row in rows),
        "fallback_count": sum(bool(row["fallback_reason"]) for row in rows),
        "category_hit_at_4": {
            category: round(sum(values) / len(values), 4)
            for category, values in sorted(category_hits.items())
        },
    }
    return rows, summary


def _write_results(
    output_dir: Path,
    rows: list[dict[str, Any]],
    summaries: list[dict[str, Any]],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "retrieval_details.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    summary_path = output_dir / "summary.json"
    summary_path.write_text(
        json.dumps(summaries, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    by_mode = {item["mode"]: item for item in summaries}
    vector_hit = by_mode["vector"]["hit_at_4"]
    full_hit = by_mode["full"]["hit_at_4"]
    improvement_points = round((full_hit - vector_hit) * 100, 1)
    vector_mrr = by_mode["vector"]["mrr_at_4"]
    full_mrr = by_mode["full"]["mrr_at_4"]
    mrr_improvement = round(full_mrr - vector_mrr, 3)
    full_abstention = by_mode["full"]["abstention_accuracy"]
    report_lines = [
        "# RAG 检索量化报告",
        "",
        f"> 评测集：{summaries[0]['question_count']} 道题，其中 "
        f"{summaries[0]['answerable_count']} 道有答案、"
        f"{summaries[0]['unanswerable_count']} 道无答案。",
        "",
        "## 总体结果",
        "",
        "| 方案 | Top-4 命中率 | MRR@4 | 无答案拒答率 | 平均延迟 | P95 延迟 |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    labels = {
        "vector": "纯向量检索",
        "hybrid": "向量 + BM25 + RRF",
        "full": "Rewrite + 混合检索 + 精排",
    }
    for summary in summaries:
        report_lines.append(
            f"| {labels[summary['mode']]} "
            f"| {summary['hit_at_4']:.1%} "
            f"| {summary['mrr_at_4']:.3f} "
            f"| {summary['abstention_accuracy']:.1%} "
            f"| {summary['average_latency_ms']:.1f} ms "
            f"| {summary['p95_latency_ms']:.1f} ms |"
        )
    report_lines.extend([
        "",
        "## 结论",
        "",
        f"- 完整链路相较纯向量检索的 Top-4 命中率变化：{improvement_points:+.1f} 个百分点。",
        f"- 完整链路将 MRR@4 从 {vector_mrr:.3f} 提升至 {full_mrr:.3f}，提升 {mrr_improvement:.3f}。",
        f"- 完整链路的无答案拒答率为 {full_abstention:.1%}。",
        "- Top-4 命中率只统计 25 道有答案题；无答案拒答率只统计 5 道无答案题。",
        "- 延迟只覆盖检索链路，不包含最终答案生成时间。",
        "- 这是基于项目内 3 份资料的小规模离线评测，不能外推为生产环境指标。",
        "",
        "## 简历表述模板",
        "",
        f"> 基于自建 {summaries[0]['question_count']} 题测试集对 RAG 链路进行对比评测；"
        f"完整方案在保持 {full_hit:.1%} Top-4 命中率的同时，"
        f"将 MRR@4 从 {vector_mrr:.3f} 提升至 {full_mrr:.3f}，"
        f"无答案拒答率达到 {full_abstention:.1%}。",
        "",
        "逐题结果见 `retrieval_details.csv`，原始汇总见 `summary.json`。",
        "",
    ])
    (output_dir / "report.md").write_text(
        "\n".join(report_lines),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    questions = _load_questions(args.questions)
    chunks = _load_chunks()
    _validate_ground_truth(chunks, questions)
    print(f"已加载 {len(chunks)} 个 Chunk，评测题 {len(questions)} 道。", flush=True)

    files = {
        "knowledge_chunks": chunks,
        "knowledge_store": None,
        "knowledge_keyword_index": None,
    }
    vector_store = None
    all_rows: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    try:
        vector_store, keyword_index = ensure_indexes(files)
        for mode in ("vector", "hybrid", "full"):
            rows, summary = _evaluate_mode(
                mode,
                questions,
                vector_store,
                keyword_index,
            )
            all_rows.extend(rows)
            summaries.append(summary)
        _write_results(args.output_dir, all_rows, summaries)
    finally:
        if vector_store is not None:
            try:
                vector_store.delete_collection()
            except Exception:
                pass

    print(json.dumps(summaries, ensure_ascii=False, indent=2))
    print(f"结果已写入：{args.output_dir}")


if __name__ == "__main__":
    main()
