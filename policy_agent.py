import sys
import os

# ─────────────────────────────────────────────────────────────
# 自动引导：若用系统 Python 直接运行且项目 venv 存在，自动切换至 venv
# 解决未激活虚拟环境导致的 ModuleNotFoundError（loguru 等依赖缺失）
# ─────────────────────────────────────────────────────────────
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
_VENV_PY = os.path.join(_APP_DIR, "venv", "bin", "python3")
if os.path.exists(_VENV_PY) and os.path.realpath(sys.executable) != os.path.realpath(_VENV_PY):
    os.execv(_VENV_PY, [_VENV_PY] + sys.argv)

sys.path.insert(0, ".")

import streamlit as st
from loguru import logger

# ═══════════════════════════════════════════════════════════
# 政务风全局主题：政务深蓝 #165DFF，白底卡片，圆角+柔和阴影
# 字号规范：总标题20px / 板块标题17px / 正文表单15px / 备注13px / 按钮14px
# ═══════════════════════════════════════════════════════════
st.set_page_config(page_title="政策智能分析Agent系统", page_icon="⚖️", layout="wide")

GOV_CSS = """
<style>
/* ---------- 基础重置：弱化 Streamlit 原生痕迹 ---------- */
#MainMenu, footer, header, [data-testid="stToolbar"], [data-testid="stDecoration"] {visibility: hidden;}
.block-container {padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1400px;}
[data-testid="stAppViewContainer"] {background: #ffffff;}
[data-testid="stHeader"] {background: transparent;}

/* ---------- 字体与文字色阶 ---------- */
html, body, [class*="css"], .stMarkdown, .stText, p, span, div, label {
    font-family: -apple-system, "PingFang SC", "Microsoft YaHei", "Source Han Sans SC", sans-serif;
}
h1 {font-size: 20px !important; font-weight: 700; color: #111824;}
h2, h3 {font-size: 17px !important; font-weight: 700; color: #111824;}
p, li, .stMarkdown p {font-size: 15px; color: #1D2129; line-height: 1.7;}
[data-testid="stCaptionContainer"] p, .stCaption, small, .stMarkdown small {font-size: 13px !important; color: #6B7785;}
.stButton button, .stDownloadButton button, .stFormSubmitButton button {font-size: 14px;}

/* ---------- 侧边导航 ---------- */
[data-testid="stSidebar"] {background: #ffffff; border-right: 1px solid #E5E6EB;}
[data-testid="stSidebar"] .stRadio [role="radiogroup"] {gap: 0.25rem;}
[data-testid="stSidebar"] .stRadio label {
    padding: 0.5rem 0.8rem; border-radius: 8px; font-size: 15px; color: #1D2129;
    background: transparent; border: 1px solid transparent; transition: all 0.15s;
}
[data-testid="stSidebar"] .stRadio label:hover {background: #E8F3FF; color: #165DFF;}
[data-testid="stSidebar"] .stRadio label:has(input:checked) {
    background: #165DFF; color: #ffffff; font-weight: 600;
    box-shadow: 0 2px 6px rgba(22, 93, 255, 0.3);
}

/* ---------- 白色卡片分块 ---------- */
div[data-testid="stVerticalBlock"]:has(> div > div > div > div > div > .gcard) {gap: 1rem;}
.gcard {
    background: #ffffff; border: 1px solid #E5E6EB; border-radius: 8px;
    box-shadow: 0 2px 8px rgba(17, 24, 32, 0.04);
    padding: 1.1rem 1.3rem; margin-bottom: 0.6rem;
}
.gcard h3 {margin: 0 0 0.7rem 0; padding-bottom: 0.5rem; border-bottom: 2px solid #E8F3FF;}
.gcard .card-tag {
    display: inline-block; background: #E8F3FF; color: #165DFF;
    border-radius: 4px; padding: 2px 8px; font-size: 12px; font-weight: 600; margin-bottom: 0.6rem;
}

/* ---------- 仪表盘数字卡片 ---------- */
.metric-card {
    background: #ffffff; border: 1px solid #E5E6EB; border-radius: 8px;
    box-shadow: 0 2px 8px rgba(17, 24, 32, 0.04); padding: 1rem 1.2rem; text-align: center;
}
.metric-card .metric-num {font-size: 28px; font-weight: 700; color: #165DFF; line-height: 1.2;}
.metric-card .metric-label {font-size: 13px; color: #6B7785; margin-top: 0.2rem;}

/* ---------- 按钮层级：主操作政务蓝，次要浅灰 ---------- */
.stButton button[kind="primary"], .stFormSubmitButton button[kind="primary"],
.stDownloadButton button {background: #165DFF; color: #fff; border: none;}
.stButton button[kind="primary"]:hover, .stFormSubmitButton button[kind="primary"]:hover,
.stDownloadButton button:hover {background: #0e42c0;}
.stButton button:not([kind="primary"]) {background: #F2F3F5; color: #1D2129; border: 1px solid #E5E6EB;}
.stButton button:not([kind="primary"]):hover {background: #E8F3FF; color: #165DFF;}

/* ---------- 输入控件 ---------- */
.stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] > div,
.stNumberInput input, [data-baseweb="input"] {
    border-radius: 6px !important; border-color: #E5E6EB !important; font-size: 15px;
}
.stTextArea textarea {line-height: 1.7;}

/* ---------- 表格与长文本滚动 ---------- */
[data-testid="stDataFrame"] {border: 1px solid #E5E6EB; border-radius: 8px; overflow: hidden;}
.stMarkdown pre, .stMarkdown code {border-radius: 6px;}
div[data-testid="stVerticalBlockBorderWrapper"] {border-color: #E5E6EB !important;}

/* ---------- 对话消息 ---------- */
.stChatMessage {background: #F8FAFF; border: 1px solid #E5E6EB; border-radius: 8px;}

/* ---------- 状态提示 ---------- */
.stAlert {border-radius: 8px; border-color: #E5E6EB;}
</style>
"""
st.markdown(GOV_CSS, unsafe_allow_html=True)

from utils.helpers import load_env, check_api_keys, ensure_dirs
from core.models import ModelClient
from core.tools import PDFParser, RAGRetriever, PolicyExtractor, PolicyMatcher
from core.agent import PolicyAgent

# 侧边导航菜单（6大页面，顺序贴合业务流转）
PAGES = [
    ("🏠 首页总览", "home"),
    ("📚 政策知识库管理", "kb"),
    ("🤝 政企需求智能匹配", "match"),
    ("📋 政策申报材料标准化", "standard"),
    ("📊 政策落地评估报告生成", "assessment"),
    ("⚙️ 系统参数与安全配置", "config"),
]
PAGE_LABEL = {key: label for label, key in PAGES}


def init_session():
    if "initialized" in st.session_state:
        return
    ensure_dirs()
    load_env()
    keys = check_api_keys()
    st.session_state["api_keys"] = keys

    try:
        mc = ModelClient()
        st.session_state["model_client"] = mc
        available = mc.get_available_models()
        st.session_state["available_models"] = available or ["tongyi"]
        logger.info(f"可用模型(按密钥): {available or ['tongyi']}")
    except Exception as e:
        logger.error(f"模型客户端初始化失败: {e}")
        st.session_state["available_models"] = ["tongyi"]

    st.session_state["pdf_files"] = PDFParser.list_pdfs()
    st.session_state["initialized"] = True


def init_rag():
    mc = st.session_state.get("model_client")
    if not mc:
        return
    try:
        retriever = RAGRetriever()
        extractor = PolicyExtractor(mc)
        matcher = PolicyMatcher(mc)
        agent = PolicyAgent(mc, retriever, extractor, matcher)
        from core.pipeline import PolicyPipeline
        pipeline = PolicyPipeline(mc, retriever, extractor, matcher)
        st.session_state["retriever"] = retriever
        st.session_state["extractor"] = extractor
        st.session_state["matcher"] = matcher
        st.session_state["agent"] = agent
        st.session_state["pipeline"] = pipeline
        st.session_state["rag_stats"] = retriever.get_stats()
        st.session_state["rag_ready"] = True
        logger.info("RAG + Agent + Pipeline 初始化完成")
    except Exception as e:
        st.session_state["rag_ready"] = False
        logger.error(f"RAG初始化失败: {e}")


def ingest_pdfs():
    """PDF 批量解析入库：文本切块 → 向量化 → 写入 Chroma 向量库"""
    pdf_files = st.session_state.get("pdf_files", [])
    if not pdf_files:
        st.error("未发现PDF文件")
        return
    retriever = st.session_state.get("retriever")
    if not retriever:
        st.error("向量库未初始化")
        return

    parser = PDFParser()
    processed = 0
    progress = st.progress(0.0, text="正在解析并入库PDF ...")
    for i, path in enumerate(pdf_files):
        doc_id = parser.file_hash(path)
        text, chunks = parser.process_pdf(path)
        if chunks:
            n = retriever.add_documents(doc_id, chunks)
            if n > 0:
                processed += 1
        progress.progress((i + 1) / len(pdf_files))
    progress.empty()
    st.session_state["rag_stats"] = retriever.get_stats()
    st.success(f"导入完成！已处理 {processed}/{len(pdf_files)} 个PDF文件")
    logger.info(f"批量导入完成: {processed}/{len(pdf_files)}")


def clear_vectordb():
    import shutil
    chroma_dir = "data/chroma_db"
    try:
        shutil.rmtree(chroma_dir, ignore_errors=True)
        for key in ("retriever", "agent", "pipeline"):
            st.session_state.pop(key, None)
        st.session_state["rag_ready"] = False
        st.session_state["rag_stats"] = {"total_chunks": 0}
        st.success("向量库已清空")
        init_rag()
        st.rerun()
    except Exception as e:
        st.error(f"清空失败: {e}")


def main():
    init_session()

    # 侧边导航：固定菜单栏，选中项高亮政务蓝
    with st.sidebar:
        st.markdown("## ⚖️ 政策智能分析Agent")
        st.markdown("政务实验室项目申报 · 中小企业政策服务 · 落地效果研判", unsafe_allow_html=True)
        st.markdown("<hr style='border:1px solid #E5E6EB'>", unsafe_allow_html=True)
        page = st.radio("功能导航", [label for label, _ in PAGES],
                        key="nav_page", label_visibility="collapsed")
        st.markdown("<hr style='border:1px solid #E5E6EB'>", unsafe_allow_html=True)
        st.caption(f"当前页面：{page}")
        if st.session_state.get("api_keys"):
            names = {"dashscope": "通义千问", "openai": "OpenAI", "anthropic": "Claude"}
            configured = [names[k] for k, v in st.session_state["api_keys"].items() if v]
            st.caption("已配置密钥：" + ("、".join(configured) if configured else "无"))
        else:
            st.caption("未检测到API密钥，请前往「系统参数与安全配置」配置")

    page_key = dict((label, key) for label, key in PAGES)[page]

    # 首页仪表盘与系统配置页不依赖 RAG 初始化
    if page_key == "home":
        from components.ui import render_home_page
        render_home_page()
        return
    if page_key == "config":
        from components.ui import render_config_page
        render_config_page()
        return

    # 业务页面需先初始化 RAG + Agent + Pipeline
    if not st.session_state.get("rag_ready"):
        with st.container():
            st.markdown('<div class="gcard"><h3>🚀 系统初始化</h3>', unsafe_allow_html=True)
            st.info("首次使用需先初始化 RAG 向量库与 Agent 引擎")
            if st.button("🚀 一键初始化系统", type="primary", use_container_width=True):
                with st.spinner("正在加载Embedding并初始化向量库 ..."):
                    init_rag()
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        return

    # 按导航分发至对应页面
    from components.ui import (render_kb_page, render_match_page,
                               render_standard_page, render_assessment_page)
    if page_key == "kb":
        render_kb_page()
    elif page_key == "match":
        render_match_page()
    elif page_key == "standard":
        render_standard_page()
    elif page_key == "assessment":
        render_assessment_page()

    # 侧边栏快捷操作（向量库导入/清空）全局可用
    if st.session_state.get("action_ingest"):
        st.session_state["action_ingest"] = False
        if not st.session_state.get("rag_ready"):
            init_rag()
        ingest_pdfs()
        st.rerun()
    if st.session_state.get("action_clear_vectordb"):
        st.session_state["action_clear_vectordb"] = False
        clear_vectordb()
        st.rerun()


if __name__ == "__main__":
    main()
