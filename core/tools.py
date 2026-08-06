import os
import json
import hashlib
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime

import pdfplumber
import chromadb
from chromadb.config import Settings
from fastembed import TextEmbedding
from loguru import logger

from .schemas import ExtractedPolicy, EnterpriseNeed, MatchResult, SubsidyStandard
from .models import ModelClient, build_messages

# ═══════════════════════════════════════════════════════════
# 1. PDF 解析器
# ═══════════════════════════════════════════════════════════

class PDFParser:
    CHUNK_SIZE = 512
    CHUNK_OVERLAP = 128

    @staticmethod
    def list_pdfs(pdf_dir: str = "policy_docs") -> List[Path]:
        p = Path(pdf_dir)
        p.mkdir(parents=True, exist_ok=True)
        return sorted(p.glob("*.pdf"))

    @staticmethod
    def extract_text(pdf_path: Path) -> str:
        text = ""
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                    tables = page.extract_tables()
                    if tables:
                        for table in tables:
                            for row in table:
                                cells = [cell or "" for cell in row]
                                if any(c.strip() for c in cells):
                                    text += " | ".join(cells) + "\n"
        except Exception as e:
            logger.error(f"PDF解析失败 {pdf_path.name}: {e}")
        return text.strip()

    @classmethod
    def chunk_text(cls, text: str) -> List[str]:
        chunks = []
        start = 0
        total = len(text)
        while start < total:
            end = min(start + cls.CHUNK_SIZE, total)
            if end < total:
                cut = text.rfind("。", start, end)
                if cut > start + cls.CHUNK_SIZE // 2:
                    end = cut + 1
            chunk = text[start:end].strip()
            if len(chunk) > 20:
                chunks.append(chunk)
            if end >= total:
                break
            start = max(start + 1, end - cls.CHUNK_OVERLAP)
        return chunks

    @staticmethod
    def file_hash(path: Path) -> str:
        return hashlib.md5(path.read_bytes()).hexdigest()

    @classmethod
    def process_pdf(cls, path: Path) -> Tuple[str, List[str]]:
        text = cls.extract_text(path)
        chunks = cls.chunk_text(text) if text else []
        return text, chunks


# ═══════════════════════════════════════════════════════════
# 2. 政策要素提取器
# ═══════════════════════════════════════════════════════════

class PolicyExtractor:
    EXTRACT_PROMPT = """你是一位专业的政务政策分析专家。从以下政策文本中提取结构化信息。

政策标题：{title}

政策文本：
{text}

请按严格JSON格式提取以下字段：
{{
  "eligibility_criteria": ["申报门槛列表：注册年限、营收要求、资质要求等"],
  "applicable_entities": ["适用主体类型：如高新技术企业、中小微企业等"],
  "policy_thresholds": {{"量化指标名": "具体阈值数值"}},
  "constraint_clauses": ["限制性条款：不重复申报、配套资金要求等"],
  "support_scope": "资金支持/政策优惠的范围说明",
  "subsidy_standards": [
    {{"subsidy_type": "补贴类型（研发补贴/贷款贴息/人才奖励等）", "amount_or_ratio": "金额或比例", "conditions": ["享受条件"]}}
  ],
  "issuing_body": "发文单位名称",
  "publish_date": "发布日期（YYYY-MM-DD格式）",
  "document_type": "政策类型：通知/办法/条例/细则等",
  "application_process": "申报流程说明"
}}

要求：
- 每个字段必须忠实于原文，不编造
- 补贴标准要逐条拆解为对象+金额+条件
- 无法获取的字段设为空字符串或空列表
- 只输出JSON，不要任何额外文字"""

    def __init__(self, model_client: ModelClient):
        self.model = model_client

    def extract(self, text: str, title: str = "", model_key: str = "tongyi") -> ExtractedPolicy:
        if len(text) > 6000:
            text = text[:6000]
        prompt = self.EXTRACT_PROMPT.format(title=title or "未命名政策", text=text)
        try:
            response = self.model.chat(
                model_key,
                build_messages("你是一个精确的政策分析助手，只输出有效JSON。", prompt),
                temperature=0.1,
                max_tokens=2000,
            )
            data = self._parse_json(response)
            if not data:
                raise json.JSONDecodeError("无有效JSON", response, 0)
            raw_subsidies = data.get("subsidy_standards", []) or []
            subsidies = [
                SubsidyStandard(
                    subsidy_type=s.get("subsidy_type", ""),
                    amount_or_ratio=s.get("amount_or_ratio", ""),
                    conditions=s.get("conditions", []) or [],
                )
                for s in raw_subsidies
            ]
            return ExtractedPolicy(
                title=title,
                eligibility_criteria=data.get("eligibility_criteria", []),
                applicable_entities=data.get("applicable_entities", []),
                policy_thresholds=data.get("policy_thresholds", {}),
                constraint_clauses=data.get("constraint_clauses", []),
                support_scope=data.get("support_scope", ""),
                subsidy_standards=subsidies,
                issuing_body=data.get("issuing_body", ""),
                publish_date=data.get("publish_date", ""),
                document_type=data.get("document_type", ""),
                application_process=data.get("application_process", ""),
                raw_text_snippet=text[:500],
            )
        except Exception as e:
            logger.warning(f"政策提取失败 {title}: {e}")
            return ExtractedPolicy(title=title, raw_text_snippet=text[:500])

    @staticmethod
    def _parse_json(response: str) -> Optional[Dict[str, Any]]:
        """从模型输出中稳健解析 JSON：剥离 Markdown 代码块、截取首个 { 到末个 }。"""
        if not response:
            return None
        r = response.strip()
        if r.startswith("```"):
            r = r.split("\n", 1)[-1]
            r = r.rsplit("```", 1)[0].strip()
        start, end = r.find("{"), r.rfind("}")
        if start == -1 or end <= start:
            return None
        try:
            return json.loads(r[start:end + 1])
        except json.JSONDecodeError:
            return None

    def extract_multi(self, policies: List[Tuple[str, str]], model_key: str = "tongyi") -> List[ExtractedPolicy]:
        return [self.extract(text, title, model_key) for text, title in policies]


# ═══════════════════════════════════════════════════════════
# 3. RAG 检索器
# ═══════════════════════════════════════════════════════════

class _FallbackEmbedding:
    """Zero-dependency character n-gram embedding for Chinese text.
    Used when no model-based embedder is available (offline fallback).
    """
    def __init__(self, dim: int = 256):
        self.dim = dim

    def embed(self, texts: List[str]) -> List[List[float]]:
        results = []
        for text in texts:
            vec = [0.0] * self.dim
            for c in text.strip():
                idx = hash(c) % self.dim
                vec[idx] += 1.0
            norm = sum(v * v for v in vec) ** 0.5
            if norm > 1e-8:
                vec = [v / norm for v in vec]
            results.append(vec)
        return results


class RAGRetriever:
    CACHE_MAX = 32                       # 查询结果缓存容量（成本控制：重复问题不重复检索）

    def __init__(self, persist_dir: str = "data/chroma_db"):
        self.persist_dir = persist_dir
        self.embedder = self._init_embedder()
        self.client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(
            name="policies",
            metadata={"hnsw:space": "cosine"},
        )
        self._cache: "OrderedDict[Tuple[str, int], List[Dict[str, Any]]]" = OrderedDict()
        total = self.collection.count()
        embedder_name = getattr(self.embedder, "__class__", None).__name__ or "unknown"
        logger.info(f"RAG就绪 | Embedding: {embedder_name} | 向量库片段数: {total}")

    @staticmethod
    def _init_embedder():
        import os

        def fastembed_cached():
            cache_dir = os.path.expanduser("~/.cache/fastembed")
            model_name = "BAAI/bge-small-zh-v1.5"
            model_dir = os.path.join(cache_dir, model_name.replace("/", "_"))
            if not os.path.isdir(model_dir):
                return None
            return TextEmbedding(model_name=model_name, cache_dir=cache_dir)

        candidates = [
            ("fastembed (BAAI/bge-small-zh-v1.5) [cached]", lambda: fastembed_cached()),
        ]
        for name, factory in candidates:
            try:
                emb = factory()
                if emb is None:
                    continue
                logger.info(f"使用 {name}")
                return emb
            except Exception as e:
                logger.warning(f"{name} 加载失败: {e}")
        logger.info("使用零依赖 FallbackEmbedding（字符n-gram，离线可用）")
        return _FallbackEmbedding()

    def _embed(self, texts: List[str]) -> List[List[float]]:
        if hasattr(self.embedder, "embed"):
            if isinstance(self.embedder, TextEmbedding):
                return [e.tolist() for e in self.embedder.embed(texts)]
            return list(self.embedder.embed(texts))
        return self.embedder(texts)

    def add_documents(self, doc_id: str, texts: List[str]) -> int:
        if not texts:
            return 0
        existing = self.collection.get(ids=[f"{doc_id}_chunk_0"])
        if existing["ids"]:
            logger.info(f"文档 {doc_id} 已在向量库中，跳过")
            return 0
        embeddings = self._embed(texts)
        ids = [f"{doc_id}_chunk_{i}" for i in range(len(texts))]
        metadatas = [{"doc_id": doc_id}] * len(texts)
        self.collection.add(
            embeddings=embeddings,
            documents=texts,
            ids=ids,
            metadatas=metadatas,
        )
        self._cache.clear()             # 数据变更后清空查询缓存
        logger.info(f"已添加 {len(texts)} 个向量片段 (doc_id={doc_id})")
        return len(texts)

    def search(self, query: str, top_k: int = 5, min_score: float = 0.0) -> List[Dict[str, Any]]:
        """向量检索。min_score 为相似度下限，低于阈值的低相关片段不返回（防幻觉）。
        结果按 doc_id 去重并附加 score 供上层溯源排序。"""
        count = self.collection.count()
        if count == 0:
            return []
        key = (query, top_k)
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]

        query_emb = self._embed([query])
        n = min(top_k, count)
        results = self.collection.query(query_embeddings=query_emb, n_results=n)
        items = []
        if results["documents"]:
            for i in range(len(results["documents"][0])):
                items.append({
                    "text": results["documents"][0][i],
                    "score": 1 - results["distances"][0][i] if results["distances"] else 0,
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                })
        items = sorted(items, key=lambda x: x["score"], reverse=True)
        # 相似度阈值过滤：低相关片段不参与上下文（至少保留 1 条避免空结果）
        if min_score > 0 and len(items) > 1:
            kept = [it for it in items if it["score"] >= min_score]
            items = kept or items[:1]

        self._cache[key] = items
        self._cache = OrderedDict(self._cache)
        while len(self._cache) > self.CACHE_MAX:
            self._cache.popitem(last=False)
        return items

    def get_stats(self) -> Dict[str, int]:
        return {"total_chunks": self.collection.count()}

    def get_by_doc_id(self, doc_id: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """按 doc_id 直查全部片段（用于申报材料标准化等无需语义检索的场景）"""
        if self.collection.count() == 0:
            return []
        results = self.collection.get(where={"doc_id": doc_id}, limit=top_k)
        return [
            {"text": results["documents"][i], "metadata": results["metadatas"][i]}
            for i in range(len(results["documents"]))
        ] if results.get("documents") else []


# ═══════════════════════════════════════════════════════════
# 4. 政策匹配器
# ═══════════════════════════════════════════════════════════

class PolicyMatcher:
    MATCH_PROMPT = """你是企业政策匹配分析专家。分析某企业与政策的匹配程度，并给出申报优先级建议。

【企业信息】
名称：{name}
行业：{industry}
规模：{size}
注册资金：{registered_capital}
年营收：{revenue}
员工数：{employee_count}
研发占比：{rnd_ratio}
专利数：{patent_count}
企业需求：{needs}

【政策信息】
标题：{title}
申报门槛：{criteria}
适用主体：{entities}
量化阈值：{thresholds}
约束条款：{constraints}
资助范围：{support_scope}
补贴标准：{subsidies}

分析该企业与政策的匹配程度。返回JSON：
{{
  "match_score": "0-100的整数分数",
  "priority_level": "申报优先级：高/中/低（结合匹配度与补贴价值综合判断）",
  "priority_reason": "给出优先级判定的理由",
  "matched_criteria": ["已满足的条件，逐条列出"],
  "unmatched_criteria": ["未满足或不确定的条件，逐条列出"],
  "summary": "用一段话总结匹配分析结果"
}}"""

    def __init__(self, model_client: ModelClient):
        self.model = model_client

    def match(self, enterprise: EnterpriseNeed, policy: ExtractedPolicy, model_key: str = "tongyi") -> MatchResult:
        subsidy_lines = "\n".join(
            f"- {s.subsidy_type}: {s.amount_or_ratio}（条件：{'；'.join(s.conditions) if s.conditions else '无' }）"
            for s in policy.subsidy_standards
        ) if policy.subsidy_standards else "无明确补贴标准"

        prompt = self.MATCH_PROMPT.format(
            name=enterprise.name or "未知企业",
            industry=enterprise.industry or "未知",
            size=enterprise.size or "未知",
            registered_capital=enterprise.registered_capital or "未知",
            revenue=enterprise.revenue or "未知",
            employee_count=enterprise.employee_count or "未知",
            rnd_ratio=enterprise.rnd_ratio or "未知",
            patent_count=enterprise.patent_count or "未知",
            needs=", ".join(enterprise.needs) if enterprise.needs else "未填写",
            title=policy.title or "未命名政策",
            criteria="; ".join(policy.eligibility_criteria) if policy.eligibility_criteria else "无明确门槛",
            entities="; ".join(policy.applicable_entities) if policy.applicable_entities else "无明确限制",
            thresholds=json.dumps(policy.policy_thresholds, ensure_ascii=False) if policy.policy_thresholds else "无量化阈值",
            constraints="; ".join(policy.constraint_clauses) if policy.constraint_clauses else "无约束条款",
            support_scope=policy.support_scope or "未说明",
            subsidies=subsidy_lines,
        )
        try:
            response = self.model.chat(
                model_key,
                build_messages("你是政策匹配专家，只输出JSON。", prompt),
                temperature=0.1,
            )
            data = PolicyExtractor._parse_json(response)
            if not data:
                raise json.JSONDecodeError("无有效JSON", response, 0)
            return MatchResult(
                policy_title=policy.title,
                policy_id=policy.id,
                match_score=float(data.get("match_score", 0)),
                priority_level=data.get("priority_level", ""),
                priority_reason=data.get("priority_reason", ""),
                matched_criteria=data.get("matched_criteria", []),
                unmatched_criteria=data.get("unmatched_criteria", []),
                summary=data.get("summary", ""),
            )
        except Exception as e:
            logger.error(f"匹配失败: {e}")
            return MatchResult(policy_title=policy.title, match_score=0, summary=f"匹配分析出错: {e}")

    def batch_match(self, enterprise: EnterpriseNeed, policies: List[ExtractedPolicy], model_key: str = "tongyi") -> List[MatchResult]:
        """并行批量匹配（成本/延迟优化：N 个政策并发，而非串行 N 次调用）。
        max_workers 限制并发数，防止瞬时打出过多计费请求。"""
        if not policies:
            return []
        results = []
        with ThreadPoolExecutor(max_workers=min(3, len(policies))) as pool:
            futures = {pool.submit(self.match, enterprise, p, model_key): p for p in policies}
            for fut, p in futures.items():
                try:
                    results.append(fut.result())
                except Exception as e:
                    logger.error(f"匹配 {p.title} 失败: {e}")
                    results.append(MatchResult(policy_title=p.title, match_score=0, summary=f"匹配出错: {e}"))
        return sorted(results, key=lambda x: x.match_score, reverse=True)


# ═══════════════════════════════════════════════════════════
# 5. 报告生成器
# ═══════════════════════════════════════════════════════════

class ReportGenerator:

    @staticmethod
    def save_assessment_report(
        policy: ExtractedPolicy,
        assessment: str,
        output_dir: str = "output/assessment",
    ) -> str:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        safe = policy.title.replace("/", "_").replace(" ", "_")[:50] or "未命名"
        filename = f"{safe}_评估报告_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        path = Path(output_dir) / filename

        criteria = "\n".join(f"  - {c}" for c in policy.eligibility_criteria) if policy.eligibility_criteria else "  无明确门槛"
        entities = "\n".join(f"  - {e}" for e in policy.applicable_entities) if policy.applicable_entities else "  无明确限制"
        thresholds = "\n".join(f"| {k} | {v} |" for k, v in policy.policy_thresholds.items()) if policy.policy_thresholds else "| - | 无量化阈值 |"
        constraints = "\n".join(f"  - {c}" for c in policy.constraint_clauses) if policy.constraint_clauses else "  无约束条款"

        report = f"""# 政策落地评估报告

**生成时间**：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

---

## 政策基本信息

| 字段 | 内容 |
|------|------|
| 政策名称 | {policy.title} |
| 发文单位 | {policy.issuing_body or '未知'} |
| 发布日期 | {policy.publish_date or '未知'} |
| 政策类型 | {policy.document_type or '未知'} |

## 申报门槛

{criteria}

## 适用主体

{entities}

## 量化阈值

| 指标 | 阈值 |
|------|------|
{thresholds}

## 约束条款

{constraints}

## 落地评估分析

{assessment}

---
*报告由政务政策智能分析Agent自动生成*
"""
        path.write_text(report, encoding="utf-8")
        logger.info(f"评估报告已保存: {path}")
        return str(path)

    @staticmethod
    def save_matching_report(
        matches: List[MatchResult],
        enterprise: EnterpriseNeed,
        output_dir: str = "output/matching",
    ) -> str:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        safe = enterprise.name.replace("/", "_").replace(" ", "_")[:50] or "未知企业"
        filename = f"{safe}_匹配报告_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        path = Path(output_dir) / filename

        sorted_m = sorted(matches, key=lambda x: x.match_score, reverse=True)
        overview = "\n".join(f"| {m.policy_title} | {m.match_score:.0f}% |" for m in sorted_m) if sorted_m else "暂无匹配结果"

        detail_parts = []
        for m in sorted_m:
            matched = "\n".join(f"  - {c}" for c in m.matched_criteria) if m.matched_criteria else "  暂无"
            unmatched = "\n".join(f"  - {c}" for c in m.unmatched_criteria) if m.unmatched_criteria else "  暂无"
            detail_parts.append(f"""
## {m.policy_title} — 匹配度: {m.match_score:.0f}%

**已满足条件**：
{matched}

**未满足条件**：
{unmatched}

**分析总结**：{m.summary}

---
""")
        details = "".join(detail_parts)

        report = f"""# 企业需求匹配报告

**生成时间**：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## 企业信息

| 字段 | 内容 |
|------|------|
| 企业名称 | {enterprise.name} |
| 行业 | {enterprise.industry} |
| 规模 | {enterprise.size} |
| 营收 | {enterprise.revenue or '未知'} |
| 研发占比 | {enterprise.rnd_ratio or '未知'} |
| 专利数 | {enterprise.patent_count or '未知'} |
| 主要需求 | {', '.join(enterprise.needs) if enterprise.needs else '未填写'} |

## 匹配结果概览

| 政策名称 | 匹配度 |
|----------|--------|
{overview}

{details}
---
*报告由政务政策智能分析Agent自动生成*
"""
        path.write_text(report, encoding="utf-8")
        logger.info(f"匹配报告已保存: {path}")
        return str(path)
