import type { KnowledgeSource } from "./types";

export const starterSources: KnowledgeSource[] = [
  {
    id: "policy",
    name: "员工差旅管理制度.pdf",
    kind: "pdf",
    meta: "26 页 · 42 个片段",
    status: "ready",
  },
  {
    id: "sales",
    name: "2026_Q2_销售数据.csv",
    kind: "csv",
    meta: "1,284 行",
    status: "ready",
  },
  {
    id: "meeting-source",
    name: "产品周会录音.m4a",
    kind: "audio",
    meta: "18:32 · 已转写",
    status: "ready",
  },
];
