import os
import time
from typing import List, Dict, Optional

from loguru import logger

# 通义千问走 DashScope OpenAI 兼容接口；其余模型走 aisuite
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DASHSCOPE_MODEL = "qwen-max"

MODEL_MAP: Dict[str, str] = {
    "tongyi": "dashscope:qwen-max",
    "gpt4": "openai:gpt-4o",
    "gpt4o-mini": "openai:gpt-4o-mini",
    "claude": "anthropic:claude-3-5-sonnet-latest",
}
AVAILABLE_MODELS = list(MODEL_MAP.keys())

# 模型 → (所需环境变量, 供应商名)
KEY_MODEL_MAP: Dict[str, tuple] = {
    "tongyi": ("DASHSCOPE_API_KEY", "dashscope"),
    "gpt4": ("OPENAI_API_KEY", "openai"),
    "gpt4o-mini": ("OPENAI_API_KEY", "openai"),
    "claude": ("ANTHROPIC_API_KEY", "anthropic"),
}

# 默认超时与重试（成本/资源兜底）
DEFAULT_TIMEOUT = 120.0          # 单次请求超时（秒）
MAX_RETRIES = 2                  # 瞬时错误重试次数
RETRY_BACKOFF = 2.0              # 退避基数（秒）

# 预估计费（qwen-max DashScope 标准价，元/千token，用于成本日志；非精确账单）
COST_PER_1K_INPUT = 0.02
COST_PER_1K_OUTPUT = 0.06


def _estimate_tokens(text: str) -> int:
    """中文场景的粗略 token 估算（每字符≈0.6 token）。"""
    return max(1, int(len(text) * 0.6))


def _is_retryable(e: Exception) -> bool:
    """瞬时错误（网络/超时/限流/5xx）才值得重试，避免掩盖真实错误。"""
    msg = str(e).lower()
    return any(k in msg for k in (
        "timeout", "timed out", "connection", "connect", "429", "rate",
        "too many", "5", "internal", "unavailable", "overloaded",
    ))


class ModelClient:
    def __init__(self):
        import aisuite as ai
        self.client = ai.Client()
        self._cache: Dict[str, bool] = {}
        self._dashscope_client = None
        self.total_input_tokens = 0      # 累计输入 token（成本统计）
        self.total_output_tokens = 0     # 累计输出 token

    def _get_dashscope_client(self):
        from openai import OpenAI
        if self._dashscope_client is None:
            self._dashscope_client = OpenAI(
                api_key=os.getenv("DASHSCOPE_API_KEY"),
                base_url=DASHSCOPE_BASE_URL,
                timeout=DEFAULT_TIMEOUT,
                max_retries=1,
            )
        return self._dashscope_client

    def _chat_dashscope(self, messages, temperature, max_tokens, json_mode=False) -> str:
        client = self._get_dashscope_client()
        kwargs = dict(model=DASHSCOPE_MODEL, messages=messages,
                      temperature=temperature, max_tokens=max_tokens)
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        response = client.chat.completions.create(**kwargs)
        return response.choices[0].message.content

    def chat(
        self,
        model_key: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,          # 事实问答默认低温，抑制幻觉
        max_tokens: int = 4096,
        json_mode: bool = False,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> str:
        if model_key not in MODEL_MAP:
            raise ValueError(f"未知模型: {model_key}，可选: {', '.join(MODEL_MAP.keys())}")
        env_var, _ = KEY_MODEL_MAP.get(model_key, (None, None))
        if env_var and not os.getenv(env_var):
            raise RuntimeError(
                f"模型 {model_key} 调用失败: 缺少 {env_var} 环境变量。"
                f"请在 .env 中配置后重启，或选择其他已配置密钥的模型。"
            )

        in_tokens = sum(_estimate_tokens(m.get("content", "")) for m in messages)

        last_err = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                if model_key == "tongyi":
                    content = self._chat_dashscope(messages, temperature, max_tokens, json_mode)
                else:
                    model = MODEL_MAP.get(model_key)
                    kwargs = dict(model=model, messages=messages,
                                  temperature=temperature, max_tokens=max_tokens, timeout=timeout)
                    if json_mode:
                        kwargs["response_format"] = {"type": "json_object"}
                    response = self.client.chat.completions.create(**kwargs)
                    content = response.choices[0].message.content

                out_tokens = _estimate_tokens(content or "")
                self.total_input_tokens += in_tokens
                self.total_output_tokens += out_tokens
                cost = (in_tokens / 1000 * COST_PER_1K_INPUT
                        + out_tokens / 1000 * COST_PER_1K_OUTPUT)
                logger.info(
                    f"[模型] {model_key} | in≈{in_tokens} out≈{out_tokens} tok | "
                    f"预估成本≈¥{cost:.4f} | 累计输入{self.total_input_tokens} 输出{self.total_output_tokens}")
                return content or ""
            except Exception as e:
                last_err = e
                if not _is_retryable(e):
                    break
                if attempt < MAX_RETRIES:
                    wait = RETRY_BACKOFF * (2 ** attempt)
                    logger.warning(f"模型 {model_key} 瞬时错误({e})，{wait:.0f}s 后重试 {attempt+1}/{MAX_RETRIES}")
                    time.sleep(wait)
                else:
                    logger.error(f"模型 {model_key} 重试耗尽仍失败: {e}")

        logger.error(f"模型 {model_key} 调用失败: {last_err}")
        raise RuntimeError(f"模型 {model_key} 调用失败: {last_err}")

    def get_cost_summary(self) -> Dict[str, int]:
        """累计 token 用量，供系统配置页展示（资源/成本管控）。"""
        return {
            "input_tokens": self.total_input_tokens,
            "output_tokens": self.total_output_tokens,
            "est_cost_yuan": round(
                self.total_input_tokens / 1000 * COST_PER_1K_INPUT
                + self.total_output_tokens / 1000 * COST_PER_1K_OUTPUT, 4),
        }

    def check_availability(self, model_key: str) -> bool:
        """按 .env 密钥判断可用性（不做网络探测，避免沙盒/离线误判）。"""
        if model_key in self._cache:
            return self._cache[model_key]
        env_var, _ = KEY_MODEL_MAP.get(model_key, (None, None))
        ok = bool(env_var and os.getenv(env_var))
        self._cache[model_key] = ok
        return ok

    def get_available_models(self) -> List[str]:
        ordered = ["tongyi"] + [m for m in AVAILABLE_MODELS if m != "tongyi"]
        return [m for m in ordered if self.check_availability(m)]


def build_messages(system_prompt: str, user_prompt: str) -> List[Dict[str, str]]:
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
