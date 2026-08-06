import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typing import TypedDict, List, Literal, Dict, Any, Optional

from langgraph.graph import StateGraph, END
from loguru import logger

from .schemas import ExtractedPolicy, EnterpriseNeed, MatchResult, ABComparison
from .tools import RAGRetriever, PolicyExtractor, PolicyMatcher, ReportGenerator
from .models import ModelClient, build_messages

MAX_ROUNDS = 4            # Agent 工具循环最大轮次（兜底阈值）
DEFAULT_MODEL = "tongyi"
CHAT_TIMEOUT = 90.0       # Agent 问答单次模型调用超时


class AgentState(TypedDict):
    messages: List[Dict[str, str]]
    current_round: int
    max_rounds: int
    intent: Optional[str]
    tool_results: Dict[str, Any]
    final_answer: Optional[str]
    continue_retrieval: Optional[bool]      # 多轮追问开关（未来扩展）


class PolicyAgent:
    def __init__(
        self,
        model_client: ModelClient,
        retriever: RAGRetriever,
        extractor: PolicyExtractor,
        matcher: PolicyMatcher,
    ):
        self.model = model_client
        self.retriever = retriever
        self.extractor = extractor
        self.matcher = matcher
        self.graph = self._build()

    def _build(self):
        g = StateGraph(AgentState)
        g.add_node("intent", self._intent)
        g.add_node("retrieve", self._retrieve)
        g.add_node("final", self._final)

        g.set_entry_point("intent")
        g.add_conditional_edges("intent", self._route_after_intent, {"retrieve": "retrieve", "final": "final"})
        g.add_conditional_edges("retrieve", self._route_after_tool, {"retrieve": "retrieve", "final": "final"})
        g.add_edge("final", END)
        return g.compile()

    # ─────────────────────────────────────────────────────
    # 轮次兜底：任何路由点只要 current_round >= max_rounds 即强制结束
    # ─────────────────────────────────────────────────────
    def _exceeded(self, state: AgentState) -> bool:
        return state.get("current_round", 0) >= state.get("max_rounds", MAX_ROUNDS)

    def _intent(self, state: AgentState) -> dict:
        if self._exceeded(state):
            return {"intent": "retrieve", "current_round": state["current_round"]}
        q = state["messages"][-1]["content"] if state["messages"] else ""
        p = f"""分析用户问题意图，只返回一个词：retrieve（政策问答）、match（需求匹配）、report（生成报告）。

用户问题：{q}"""
        try:
            r = self.model.chat(DEFAULT_MODEL, [
                {"role": "system", "content": "你是意图分类器，只返回一个词。"},
                {"role": "user", "content": p},
            ], temperature=0, max_tokens=10, timeout=CHAT_TIMEOUT)
            intent = r.strip().lower()
            if intent not in ("retrieve", "match", "report"):
                intent = "retrieve"
        except Exception as e:
            logger.warning(f"意图分类失败({e})，按 retrieve 兜底")
            intent = "retrieve"
        logger.info(f"意图: {intent}")
        return {"intent": intent, "current_round": state["current_round"] + 1}

    def _route_after_intent(self, state: AgentState) -> Literal["retrieve", "final"]:
        if self._exceeded(state):
            return "final"
        return "retrieve" if state.get("intent") == "retrieve" else "final"

    def _doc_id_to_title(self) -> Dict[str, str]:
        """从 data/processed/*.json 构建 doc_id→政策标题 映射，用于引用溯源。"""
        mapping = {}
        for fp in Path("data/processed").glob("*.json"):
            try:
                d = json.loads(fp.read_text(encoding="utf-8"))
                if d.get("id"):
                    mapping[d["id"]] = d.get("title") or fp.stem
            except Exception:
                continue
        return mapping

    def _retrieve(self, state: AgentState) -> dict:
        q = state["messages"][-1]["content"] if state["messages"] else ""
        results = self.retriever.search(q, 3)

        title_map = self._doc_id_to_title()
        sources = []
        if results:
            # 带来源标注与相似度得分的上下文。
            # n-gram 兜底嵌入区分度有限，分数低不代表完全无关，故不硬删，
            # 而是把得分一并交给模型并强约束：只依据相关内容作答，低相关须如实说明。
            max_score = max((r.get("score") or 0.0) for r in results)
            low_relevance = max_score < 0.15
            ctx_lines = []
            for i, r in enumerate(results, 1):
                meta = r.get("metadata", {})
                doc_id = meta.get("doc_id", "")
                title = title_map.get(doc_id) or meta.get("title") or f"政策{doc_id[:8]}"
                src = f"{title}(doc_id={doc_id})"
                ctx_lines.append(f"[来源{i}：{src} | 相似度{r.get('score', 0):.3f}]\n{r['text']}")
                sources.append(src)
            ctx = "\n\n".join(ctx_lines)
            if low_relevance:
                ctx += ("\n\n【重要提示】上述检索片段与问题相关性较低（最高相似度不足阈值）。"
                        "若据此无法可靠作答，请明确告知用户知识库中暂无匹配文档，不要强行引用或臆测。")
            system = (
                "你是政务政策分析专家。回答必须遵守：\n"
                "1. 只依据【检索到的政策上下文】作答，不得使用上下文之外的信息；\n"
                "2. 每条关键结论末尾标注出处，格式[来源N]；\n"
                "3. 如果检索结果不足以回答问题，明确说明缺少哪些信息，不要臆测。"
            )
            user = f"【检索到的政策上下文】\n{ctx}\n\n【用户问题】\n{q}"
        else:
            system = (
                "你是政务政策分析专家。当前未检索到相关政策原文，"
                "请如实告知用户知识库中暂无相关文档，并给出后续建议（如上传对应政策PDF），"
                "严禁编造政策条款。"
            )
            user = q

        answer = self.model.chat(DEFAULT_MODEL, [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ], temperature=0.2, timeout=CHAT_TIMEOUT)

        # 附加可追溯来源清单（无论模型是否遗漏，来源都随答案返回）
        answer += "\n\n---\n**参考来源**：\n" + "\n".join(f"- {s}" for s in sources) if sources else answer
        return {
            "tool_results": {"retrieval": results, "sources": sources, "answer": answer},
            "current_round": state["current_round"] + 1,
        }

    def _route_after_tool(self, state: AgentState) -> Literal["retrieve", "final"]:
        # 当前为单轮检索即结束；若未来扩展多轮追问（retrieve→retrieve 循环边），
        # 此路由必须依据 _exceeded(state) 判定，否则将被 MAX_ROUNDS 硬性终止。
        if not self._exceeded(state) and state.get("intent") == "retrieve" and state.get("continue_retrieval"):
            return "retrieve"
        return "final"

    def _final(self, state: AgentState) -> dict:
        tr = state.get("tool_results", {})
        answer = tr.get("answer", "抱歉，未能生成有效回答。")
        return {"final_answer": answer, "current_round": state["current_round"] + 1}

    def run(self, messages: List[Dict[str, str]]) -> str:
        state: AgentState = {
            "messages": messages,
            "current_round": 0,
            "max_rounds": MAX_ROUNDS,
            "intent": None,
            "tool_results": {},
            "final_answer": None,
            "continue_retrieval": False,
        }
        try:
            result = self.graph.invoke(state)
        except Exception as e:
            logger.error(f"Agent 执行异常: {e}")
            return "⚠️ Agent 执行出错，请稍后重试。"
        final = result.get("final_answer", "Agent执行完成。")
        # 兜底断言：超出轮次阈值时确保有终止信号而非无限循环
        if result.get("current_round", 0) > MAX_ROUNDS:
            logger.warning(f"Agent 轮次已达上限 {MAX_ROUNDS}，已强制终止")
        return final

    @staticmethod
    def ab_compare(
        model_client: ModelClient,
        question: str,
        model_a: str,
        model_b: str,
    ) -> ABComparison:
        msgs = [{"role": "user", "content": question}]
        sys = "你是政务政策分析专家，请客观解读以下政策问题。"
        prompt_a = [{"role": "system", "content": sys}] + msgs

        # 并行调用两个模型，缩短对比延迟
        with ThreadPoolExecutor(max_workers=2) as pool:
            fa = pool.submit(model_client.chat, model_a, prompt_a)
            fb = pool.submit(model_client.chat, model_b, prompt_a)
            answer_a = fa.result()
            answer_b = fb.result()

        analysis_prompt = f"""比较以下两个模型对同一政策问题的回答，分析差异、各自的优点和不足。

【问题】{question}

【模型A ({model_a}) 的回答】
{answer_a}

【模型B ({model_b}) 的回答】
{answer_b}

请从以下维度分析：
1. 信息完整性差异
2. 分析深度差异
3. 表述清晰度差异
4. 总体建议

返回JSON：
{{
  "difference_analysis": "差异分析",
  "better_model": "推荐哪个模型及其理由",
  "complementary_points": "两个回答可以互补的地方"
}}"""

        try:
            analysis_raw = model_client.chat(
                DEFAULT_MODEL,
                [{"role": "system", "content": "你是A/B测试分析师，只输出JSON。"},
                 {"role": "user", "content": analysis_prompt}],
                temperature=0.1,
            )
            analysis_data = json.loads(analysis_raw)
            analysis = (
                f"**差异分析**：{analysis_data.get('difference_analysis', '')}\n\n"
                f"**推荐模型**：{analysis_data.get('better_model', '')}\n\n"
                f"**互补要点**：{analysis_data.get('complementary_points', '')}"
            )
        except Exception as e:
            logger.warning(f"A/B 对比分析生成失败: {e}")
            analysis = "（A/B对比分析生成失败）"

        return ABComparison(
            question=question,
            model_a=model_a,
            model_b=model_b,
            answer_a=answer_a,
            answer_b=answer_b,
            analysis=analysis,
        )
