import os
import json
from pathlib import Path
from typing import Optional
from loguru import logger


def load_env(env_path: str = ".env") -> None:
    try:
        from dotenv import load_dotenv
        p = Path(env_path)
        if p.exists():
            load_dotenv(p)
            logger.info(f"已加载环境变量: {p.resolve()}")
        else:
            logger.warning(f".env 文件不存在: {p.resolve()}")
    except ImportError:
        logger.warning("python-dotenv 未安装，跳过.env加载")


def check_api_keys() -> dict:
    keys = {
        "openai": bool(os.getenv("OPENAI_API_KEY")),
        "anthropic": bool(os.getenv("ANTHROPIC_API_KEY")),
        "dashscope": bool(os.getenv("DASHSCOPE_API_KEY")),
    }
    available = [k for k, v in keys.items() if v]
    missing = [k for k, v in keys.items() if not v]
    if missing:
        logger.info(f"API密钥缺失: {', '.join(missing)}（对应模型将不可用）")
    return keys


def ensure_dirs():
    for d in ["policy_docs", "data/input/policies", "data/input/feedback", "data/input/enterprises",
              "data/chroma_db", "data/processed", "data/cache",
              "output/assessment", "output/matching", "output/application", "output/enterprise_match"]:
        Path(d).mkdir(parents=True, exist_ok=True)
    logger.info("数据目录已就绪")
