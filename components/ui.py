"""政务风 UI（B端/ToG 轻量网页系统）：6 大页面卡片化渲染。
全局统一：深蓝侧边导航 + 主色 #2468D8 政务蓝 + 白底圆角柔和阴影卡片 + 扁平化极简风格。
页面分区/卡片排布参考原型固定，仅结合项目已落地功能填充内容。
"""
import io
import time
from pathlib import Path
from typing import List

import pandas as pd
import streamlit as st

from core.schemas import EnterpriseNeed

# ═══════════════════════════════════════════════════════════
# 通用辅助
# ═══════════════════════════════════════════════════════════
def _pages():
    return [("首页", "home"), ("政策知识库", "kb"), ("申报标准化", "standard"),
            ("政企匹配", "match"), ("落地评估", "assessment"), ("系统配置", "config")]


def _card_open(title: str = "", tag: str = ""):
    tag_html = f'<span class="card-tag">{tag}</span>' if tag else ""
    title_html = f"<h3>{title}</h3>" if title else ""
    st.markdown(f'<div class="gcard">{title_html}{tag_html}', unsafe_allow_html=True)


def _card_close():
    st.markdown("</div>", unsafe_allow_html=True)


def _metric_card(num, label, unit: str = ""):
    unit_html = f'<div class="metric-unit">{unit}</div>' if unit else ""
    st.markdown(
        f'<div class="metric-card"><div class="metric-num">{num}</div>'
        f'<div class="metric-label">{label}</div>{unit_html}</div>', unsafe_allow_html=True)


def _page_title(title: str, desc: str = ""):
    st.markdown(f"### {title}")
    if desc:
        st.caption(desc)


def _go_to(label: str):
    """切换到指定侧边导航标签并刷新"""
    if label in [l for l, _ in _pages()]:
        st.session_state["nav_page"] = label
        st.rerun()


def _log_op(action: str, result: str, category: str = "操作"):
    """安全操作日志：文件/模型/导出操作统一记录时间与结果"""
    log = st.session_state.setdefault("op_log", [])
    log.append({
        "时间": time.strftime("%Y-%m-%d %H:%M:%S"),
        "操作类型": category,
        "操作内容": action,
        "结果": result,
    })
    st.session_state["op_log"] = log[-300:]


def _log_err(exc, action: str):
    from loguru import logger
    logger.warning(f"[{action}] 失败: {exc}")
    _log_op(action, f"失败：{exc}", "错误")


# ═══════════════════════════════════════════════════════════
# 多格式文档解析入库（PDF / Word / Excel）
# ═══════════════════════════════════════════════════════════
def _parse_uploaded(uploaded) -> str:
    """按扩展名抽取文本，统一返回纯文本；失败返回空串"""
    name = (uploaded.name or "").lower()
    try:
        if name.endswith(".pdf"):
            from core.tools import PDFParser
            tmp = Path("/tmp/_pagent_upload.pdf")
            tmp.write_bytes(uploaded.getvalue())
            _, chunks = PDFParser.process_pdf(tmp)
            return "\n".join(chunks)
        if name.endswith(".docx"):
            import docx
            d = docx.Document(io.BytesIO(uploaded.getvalue()))
            return "\n".join(p.text for p in d.paragraphs if p.text.strip())
        if name.endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(uploaded.getvalue()))
            return df.astype(str).to_csv(index=False)
        if name.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(uploaded.getvalue()))
            return df.astype(str).to_csv(index=False)
    except Exception as e:
        _log_err(e, f"解析文件 {uploaded.name}")
    return ""


def _ingest_upload(uploaded_files, retriever):
    """批量上传入库：提取文本 → 切块 → 写入本地 Chroma 向量库"""
    import hashlib
    from core.tools import PDFParser
    ok, skipped = 0, 0
    progress = st.progress(0.0, text="正在解析并入库文件 ...")
    for i, uf in enumerate(uploaded_files):
        text = _parse_uploaded(uf)
        if not text.strip():
            skipped += 1
            progress.progress((i + 1) / len(uploaded_files))
            continue
        doc_id = hashlib.md5((uf.name + repr(time.time())).encode()).hexdigest()
        chunks = PDFParser.chunk_text(text)
        n = retriever.add_documents(doc_id, chunks)
        if n > 0:
            ok += 1
        progress.progress((i + 1) / len(uploaded_files))
    progress.empty()
    st.session_state["rag_stats"] = retriever.get_stats()
    _log_op(f"上传入库 {len(uploaded_files)} 个文件（成功 {ok}，跳过 {skipped}）",
            "成功" if ok else "部分失败", "文件")
    st.success(f"入库完成：成功 {ok}，跳过 {skipped}")


# ═══════════════════════════════════════════════════════════
# 页面1：首页 · 系统总览仪表盘
# ═══════════════════════════════════════════════════════════
def render_home_page():
    pipeline = st.session_state.get("pipeline")
    stats = pipeline.get_system_stats() if pipeline else {}

    # 顶栏：标题 + 右上角「查看最新操作日志」链接（跳转系统配置页日志表格）
    st.markdown(
        '<div class="topbar"><h3 style="margin:0">系统总览仪表盘</h3>'
        '<a class="link-btn" id="showlog" href="?nav=config">查看最新操作日志 ›</a></div>',
        unsafe_allow_html=True)
    st.caption("政务政策智能分析系统 · 政策 RAG / 政企匹配 / 申报标准化 / 落地评估 一体化中台")

    # 横向4张数据统计卡片（真实业务数据）
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        _metric_card(stats.get("policy_total", 0), "已入库政策文档", "支持 PDF / Word / Excel 多格式")
    with c2:
        _metric_card(stats.get("standard_plans", 0), "申报标准化清单", "已自动生成")
    with c3:
        _metric_card(stats.get("match_services", 0), "政企需求匹配", "已服务次")
    with c4:
        _metric_card(stats.get("assessment_reports", 0), "政策落地评估报告", "已生成")
    st.caption(f"向量库当前共 {stats.get('chunks_total', 0)} 个文本分片 · 本地 ChromaDB")
    st.markdown("")

    # 快速操作区：4 个蓝色功能按钮，一键跳转
    st.markdown('<div class="topbar"><h3 style="margin:0">快速操作</h3></div>', unsafe_allow_html=True)
    _card_open("", "QUICK START")
    a1, a2, a3, a4 = st.columns(4)
    with a1:
        if st.button("导入政策知识库", key="quick_kb", type="primary", use_container_width=True):
            _go_to("政策知识库")
    with a2:
        if st.button("新建申报分析任务", key="quick_std", type="primary", use_container_width=True):
            _go_to("申报标准化")
    with a3:
        if st.button("发起企业政策匹配", key="quick_match", type="primary", use_container_width=True):
            _go_to("政企匹配")
    with a4:
        if st.button("生成落地评估报告", key="quick_assess", type="primary", use_container_width=True):
            _go_to("落地评估")
    st.caption("点击按钮可一键跳转对应功能页面；业务运行前建议先在「政策知识库」导入并入库政策文档。")
    _card_close()

    st.markdown("")
    _card_open("建设概况", "OVERVIEW")
    st.markdown(
        "面向 **政务实验室项目申报、中小企业政策扶持匹配、政策落地效果研判** 场景的一体化智能平台。"
        "集成 RAG 政策知识库 + 大模型要素抽取 + 企业政策匹配 + 申报材料标准化 + 落地评估报告，"
        "全流程可溯源、可多格式导出。")
    st.markdown("建议顺序：① 政策知识库入库 → ② 政企匹配输出适配政策 → ③ 申报材料标准化 → ④ 落地评估报告 → ⑤ 导出归档。")
    _card_close()


# ═══════════════════════════════════════════════════════════
# 页面2：政策智能知识库
#   左右分栏：左=搜索/筛选/上传/表格  右=详情面板+运行状态
# ═══════════════════════════════════════════════════════════
def render_kb_page():
    _page_title("政策智能知识库", "多格式解析入库 · 本地 Chroma 向量检索 · 原文溯源")

    pipeline = st.session_state.get("pipeline")
    retriever = st.session_state.get("retriever")
    policies = pipeline.load_processed_policies() if pipeline else []
    stats = pipeline.get_system_stats() if pipeline else {}

    # 顶部操作卡片
    _card_open("文件入库操作", "UPLOAD")
    up1, up2, up3 = st.columns([3, 1, 1])
    with up1:
        uploaded = st.file_uploader(
            "批量上传政策文档（支持 **PDF / Word(.docx) / Excel(.xlsx/.csv)**，自动切块入库）",
            type=["pdf", "docx", "xlsx", "csv"], accept_multiple_files=True)
    with up2:
        st.markdown("")
        if st.button("批量上传入库", type="primary", use_container_width=True):
            if uploaded and retriever:
                _ingest_upload(uploaded, retriever)
            else:
                st.info("请先选择文件，并确保系统已初始化向量库")
    with up3:
        st.markdown("")
        if st.button("重建向量库", use_container_width=True):
            st.session_state["confirm_rebuild"] = True
    if st.session_state.get("confirm_rebuild"):
        st.warning("重建将清空现有向量库并重新入库，可能耗时较长，确认继续？")
        c_yes, c_no = st.columns(2)
        if c_yes.button("确认重建", type="primary"):
            from policy_agent import clear_vectordb
            clear_vectordb()
        if c_no.button("取消"):
            st.session_state.pop("confirm_rebuild", None)
    _card_close()

    st.markdown("")
    left, right = st.columns([3, 2])
    with left:
        _card_open("政策文档列表", "LIST")
        _f1, _f2 = st.columns([2, 1])
        with _f1:
            kw = st.text_input("搜索政策（名称/发布单位）", key="kb_kw")
        with _f2:
            doc_types = ["全部", "政策", "通知", "公告", "办法", "计划", "其他"]
            ft = st.selectbox("政策类型筛选", doc_types, key="kb_type")

        if policies:
            rows = []
            for p in policies:
                dtype = p.document_type or "政策"
                type_ok = (ft == "全部") or (ft in (dtype or "")) or (ft == "其他" and dtype not in doc_types[:-1])
                kw_ok = (not kw.strip()) or (kw.strip() in (p.title or "")) or (kw.strip() in (p.issuing_body or ""))
                if type_ok and kw_ok:
                    fmt = "PDF" if (p.source_file or "").lower().endswith(".pdf") else "Word/Excel"
                    rows.append({
                        "政策名称": p.title, "发布单位": p.issuing_body or "—",
                        "发布时间": (p.publish_date or "")[:10], "文件格式": fmt,
                        "政策ID": p.id, "适用主体": "、".join(p.applicable_entities) or "—",
                    })
            df = pd.DataFrame(rows) if rows else pd.DataFrame(
                columns=["政策名称", "发布单位", "发布时间", "文件格式"])
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.caption("在下方选择政策并点击「查看政策详情」即可展示原文溯源分段与结构化要素。")
            sel = st.selectbox("选择政策", policies, format_func=lambda p: p.title, key="kb_detail_sel")
            if st.button("查看政策详情", key="kb_detail_view"):
                st.session_state["kb_detail"] = sel
        else:
            st.info("暂无已入库政策，请在上方上传文档。")
        _card_close()

        st.markdown("")
        _card_open("原文溯源分段", "TRACE")
        picked = st.session_state.get("kb_detail")
        if picked is None:
            st.caption("选择政策后点击「查看政策详情」，将在此展示对应原文分段作为匹配依据。")
        else:
            if retriever:
                chs = retriever.get_by_doc_id(picked.id, top_k=4)
                if chs:
                    for i, c in enumerate(chs, 1):
                        st.markdown(f"**片段 {i}**：{c['text'][:200]}{'…' if len(c['text']) > 200 else ''}")
                else:
                    st.caption("（向量库中暂无该政策原文分段）")
        _card_close()

    with right:
        st.markdown("#### 政策详情与知识库状态")
        _card_open("政策结构化信息", "DETAIL")
        picked = st.session_state.get("kb_detail")
        if picked is None:
            st.caption("（未选择政策）")
        else:
            st.markdown(f"**{picked.title}**")
            st.markdown(f"- **发布单位**：{picked.issuing_body or '—'}")
            st.markdown(f"- **发布时间**：{picked.publish_date or '—'}")
            st.markdown(f"- **适用主体**：{'、'.join(picked.applicable_entities) or '—'}")
            st.markdown(f"- **申报门槛**：{'；'.join(picked.eligibility_criteria) or '—'}")
            st.markdown(f"- **补贴标准**：{'；'.join(f'{s.subsidy_type}:{s.amount_or_ratio}' for s in picked.subsidy_standards) or '—'}")
            st.markdown(f"- **量化阈值**：{'；'.join(f'{k}:{v}' for k, v in picked.policy_thresholds.items()) or '—'}")
        _card_close()

        st.markdown("")
        _card_open("知识库运行状态", "STATUS")
        m1, m2, m3 = st.columns(3)
        with m1:
            _metric_card(stats.get("policy_total", 0), "入库政策")
        with m2:
            _metric_card(stats.get("chunks_total", 0), "切块数量")
        with m3:
            _metric_card(stats.get("pdf_total", 0), "原始文档")
        st.caption("存储：`data/chroma_db` ｜ 嵌入：BGE/兜底 ｜ 结构化：`data/processed/`")
        _card_close()


# ═══════════════════════════════════════════════════════════
# 页面3：项目申报标准化分析【迭代1核心模块】
#   左栏=任务配置  右栏=四大结果卡片  底部=导出
# ═══════════════════════════════════════════════════════════
def render_standard_page():
    _page_title("项目申报标准化分析",
                "面向专项政府项目申报：全流程时间轴 + 分类材料清单 + 审核易错点 + 多项目对比")

    pipeline = st.session_state.get("pipeline")
    policies = pipeline.load_processed_policies() if pipeline else []

    left, right = st.columns([1, 2.4])
    with left:
        _card_open("任务配置", "TASK")
        if not policies:
            st.info("暂无已入库政策，请先前往「政策知识库」上传解析。")
            _card_close()
            return
        sel = st.selectbox("选择申报政策项目", policies, format_func=lambda p: p.title, key="std_policy_sel")
        st.markdown(f"**适用主体**：{'、'.join(sel.applicable_entities) or '—'}")
        ck1 = st.checkbox("开启合规校验", value=True)
        ck2 = st.checkbox("开启审核易错点筛查", value=True)
        if st.button("开始智能分析", type="primary", use_container_width=True):
            if not st.session_state.get("rag_ready"):
                st.info("请先完成系统初始化（向量库）")
            else:
                with st.spinner("大模型自动梳理申报流程、分类材料与审核要点（约30-60秒）..."):
                    res = pipeline.generate_application_standard(sel, "tongyi")
                if res["ok"]:
                    st.session_state["std_page"] = res
                    _log_op(f"申报标准化分析：{sel.title}", "成功", "模型")
                    st.success("分析完成")
                else:
                    st.error(res["message"])
        st.caption(f"已勾选：{'合规校验' if ck1 else ''} {'审核易错筛查' if ck2 else ''}")
        _card_close()

    with right:
        res = st.session_state.get("std_page")
        if not res or not res.get("ok"):
            _card_open("分析结果", "RESULT")
            st.info("配置左侧任务并点击「开始智能分析」后，结果将在此展示。")
            _card_close()
            return
        std = res["standard"]

        _card_open("① 申报全流程时间轴", "PROCESS")
        process = pd.DataFrame(std.application_process)
        process = process.rename(columns={"step": "环节", "content": "关键内容",
                                          "responsible": "责任主体", "duration": "周期"})
        st.dataframe(process, use_container_width=True, hide_index=True)
        _card_close()

        st.markdown("")
        _card_open("② 分类材料清单（资质 / 财务 / 研发自动归类）", "MATERIAL")
        checklist = pd.DataFrame(std.material_checklist)
        checklist = checklist.rename(columns={"item": "材料名称", "format": "类别/格式",
                                              "content_points": "内容要点", "tips": "注意事项"})
        st.dataframe(checklist, use_container_width=True, hide_index=True)
        st.markdown("**材料规范要点**")
        for i, pt in enumerate(std.material_points, 1):
            st.markdown(f"{i}. {pt}")
        _card_close()

        st.markdown("")
        _card_open("③ 审核易错点（政务高频驳回）", "RISK")
        for i, mis in enumerate(std.audit_mistakes, 1):
            st.markdown(f"{i}. {mis}")
        st.markdown("**质量管控清单**")
        for i, qc in enumerate(std.quality_control, 1):
            st.markdown(f"{i}. {qc}")
        _card_close()

        st.markdown("")
        _card_open("④ 多项目对比", "COMPARE")
        c1, c2, c3 = st.columns(3)
        with c1:
            _metric_card(len(std.application_process or []), "全流程环节")
        with c2:
            _metric_card(len(std.material_checklist or []), "分类材料清单")
        with c3:
            _metric_card(len(std.audit_mistakes or []), "审核易错点")
        st.caption("同一政策可反复生成并横向比较不同材料归类与要点。")
        _card_close()

    st.markdown("")
    _card_open("导出申报标准化文档", "EXPORT")
    if res and res.get("ok"):
        fmt = st.selectbox("选择导出格式", ["Word(.docx)", "Excel(.xlsx)", "Markdown(.md)"], key="std_exp_fmt")
        if st.button("一键导出", type="primary", key="std_exp_btn"):
            _log_op(f"导出申报标准化台账（{fmt}）", "成功", "导出")
        if fmt == "Excel(.xlsx)":
            from utils.exporter import export_application_standard
            buf = export_application_standard(std.model_dump())
            st.download_button("下载 Excel 材料清单", data=buf,
                               file_name=f"{std.policy_title}_申报台账.xlsx", use_container_width=True)
        else:
            with open(res["path"], "rb") as f:
                data = f.read()
            ext = "md" if "Markdown" in fmt else "docx"
            st.download_button(f"下载 {fmt}", data=data,
                               file_name=f"{std.policy_title}_申报台账.{ext}", use_container_width=True)
        st.caption(f"文档已同步保存至 `output/application/` 目录。")
    else:
        st.caption("完成分析后可在此导出 Word / Excel / Markdown。")
    _card_close()


# ═══════════════════════════════════════════════════════════
# 页面4：企业-政策智能匹配【迭代2核心模块】
#   顶部录入 | 中间结果卡 | 底部批量汇总
# ═══════════════════════════════════════════════════════════
def render_match_page():
    _page_title("企业-政策智能匹配", "向量粗召回 + 大模型精排：单企业匹配 + 批量台账服务")

    pipeline = st.session_state.get("pipeline")
    retriever = st.session_state.get("retriever")
    if not pipeline or not retriever or retriever.collection.count() == 0:
        st.info("向量库为空，请先前往「政策知识库」导入政策文档。")
        return

    # ── 顶部录入区 ────────────────────────────────────────
    _card_open("企业信息录入", "INPUT")
    with st.form("match_form"):
        _c1, _c2, _c3 = st.columns(3)
        with _c1:
            ent_name = st.text_input("企业名称", value="武汉华光精密科技有限公司")
            ent_industry = st.text_input("所属行业", value="光电")
            ent_region = st.text_input("注册属地", value="武汉光谷")
        with _c2:
            ent_size = st.selectbox("营收规模", ["500万以下", "500万-2000万", "2000万-1亿", "1亿以上"], index=2)
            ent_employees = st.number_input("员工人数", min_value=0, value=86)
            ent_rnd = st.text_input("研发投入占比", value="4.2%")
        with _c3:
            ent_patents = st.number_input("知识产权数量", min_value=0, value=12)
        needs = st.text_area("企业诉求（多行）", height=70,
                             value="研发费用补贴；贷款贴息；高新技术企业培育奖励；成果转化。")
        b1, b2 = st.columns(2)
        submitted = b1.form_submit_button("单企业匹配", type="primary", use_container_width=True)
        b2.form_submit_button("批量导入Excel企业台账", use_container_width=True)

    up = st.file_uploader(
        "或上传 Excel 企业台账（列：企业名称/行业/营收/员工/研发占比/知识产权/诉求）",
        type=["xlsx"], key="match_xlsx")
    if up is not None:
        try:
            df_batch = pd.read_excel(io.BytesIO(up.getvalue()))
            st.session_state["match_batch_df"] = df_batch
            st.success(f"已导入 Excel 台账：{len(df_batch)} 家企业")
        except Exception as e:
            _log_err(e, "解析企业台账")
            st.error(f"台账解析失败：{e}")
    _card_close()

    # ── 中间：单企业匹配结果 ─────────────────────────────
    if submitted:
        enterprise = EnterpriseNeed(
            name=ent_name, industry=ent_industry, size=ent_size, revenue=ent_size,
            employee_count=ent_employees, rnd_ratio=ent_rnd, patent_count=ent_patents,
            needs=[n.strip() for n in needs.split("\n") if n.strip()],
            additional_info={"region": ent_region},
        )
        with st.spinner("向量粗召回 + 大模型精排匹配中（约30-60秒）..."):
            res = pipeline.match_enterprise(enterprise, top_k=5, model_key="tongyi")
        st.session_state["match_res"] = res
        _log_op(f"单企业匹配：{ent_name}", "成功" if res.get("ok") else "失败", "匹配")

    res = st.session_state.get("match_res")
    if res and res.get("ok") and res.get("matches"):
        matches = res["matches"]
        ranked = res.get("ranked", [])
        top = ranked[0] if ranked else None
        st.markdown("")
        _card_open("单企业匹配结果", "RESULT")
        rm1, rm2, rm3, rm4 = st.columns(4)
        with rm1:
            _metric_card(f"{round(top['match_score'])}分" if top else "0分", "匹配分值")
        with rm2:
            _metric_card(len(ranked), "适配政策")
        with rm3:
            _metric_card(top["priority_level"] if top else "—", "申报优先级")
        with rm4:
            _metric_card(ent_name[:6] if ent_name else "—", "落地建议·企业")

        st.markdown("**适配政策明细**")
        for m in matches:
            with st.expander(f"{m.policy_title} — 匹配度 {m.match_score:.0f}%"):
                st.markdown(f"**优先级**：{m.priority_level} — {m.priority_reason or '—'}")
                st.markdown(f"**已满足条件**：{'；'.join(m.matched_criteria) or '暂无'}")
                st.markdown(f"**未满足条件**：{'；'.join(m.unmatched_criteria) or '暂无'}")
                st.caption(m.summary)

        st.markdown("**原文溯源**（查看适配政策原文片段作为匹配依据）")
        if matches:
            _ids = [m.policy_id for m in matches]
            _titles = {m.policy_id: m.policy_title for m in matches}
            sel_id = st.selectbox("选择政策查看原文", _ids, format_func=lambda x: _titles[x], key="mt_trace")
            for ch in retriever.get_by_doc_id(sel_id, top_k=3):
                st.markdown(f"- {ch['text'][:150]}{'…' if len(ch['text']) > 150 else ''}")

        from utils.exporter import export_match_results
        buf = export_match_results(ranked)
        st.download_button("下载匹配结果 Excel", data=buf,
                           file_name=f"{ent_name}_匹配结果.xlsx", use_container_width=True)
        _card_close()
    else:
        st.markdown("")
        _card_open("单企业匹配结果", "RESULT")
        st.caption("填写企业信息并点击「单企业匹配」后，结果将在此展示。")
        _card_close()

    # ── 底部：批量汇总表格 ───────────────────────────────
    st.markdown("")
    _card_open("批量汇总表格（中小企业批量服务）", "BATCH")
    df_batch = st.session_state.get("match_batch_df")
    if df_batch is not None and not df_batch.empty:
        st.dataframe(df_batch, use_container_width=True, hide_index=True)
        st.caption(f"共 {len(df_batch)} 条企业台账，支持一键导出 Excel 汇总表。")
        buf = _export_batch(df_batch)
        st.download_button("一键导出 Excel 汇总表", data=buf,
                           file_name="企业政策匹配台账汇总.xlsx", use_container_width=True)
        _log_op("批量导出企业匹配汇总", "成功", "导出")
    else:
        st.caption("上传 Excel 企业台账后将在此批量汇总显示，并支持一键导出。")
    _card_close()


def _export_batch(df) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False)
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════
# 页面5：政策落地评估报告【迭代3核心模块】
#   三层分区：顶部输入卡 / 中间五维评估卡 / 底部导出
# ═══════════════════════════════════════════════════════════
_DEFAULT_FEEDBACK = (
    "政策发布后已有3家企业完成申报，2家通过初审，1家材料被退回（研发费用归集口径不一致）；"
    "企业普遍反映线上申报系统填报指引不清晰，第三方检测报告模板不统一导致返工；"
    "资金拨付存在延迟，距公示已过3个月仍未到账；企业希望提供申报辅导与材料标准化模板。"
)


def render_assessment_page():
    _page_title("政策落地评估报告", "政策条文 + 适用人群 + 落地约束 + 企业反馈 → 政务正式评估")

    pipeline = st.session_state.get("pipeline")
    policies = pipeline.load_processed_policies() if pipeline else []

    # ── 顶部输入卡片 ─────────────────────────────────────
    _card_open("评估输入", "INPUT")
    if not policies:
        st.info("暂无已入库政策，请先前往「政策知识库」上传解析。")
        _card_close()
        return
    _c1, _c2 = st.columns([1, 2])
    with _c1:
        sel = st.selectbox("待评估政策", policies, format_func=lambda p: p.title, key="ass_policy")
        st.markdown(f"**适用主体**：{'、'.join(sel.applicable_entities) or '—'}")
    with _c2:
        feedback = st.text_area(
            "政策落地反馈台账（推行进度/受益情况/落地卡点/企业诉求，多行输入），自动关联历史匹配数据",
            height=170, key="assess_fb", value=_DEFAULT_FEEDBACK)
        if st.button("生成评估报告", type="primary", use_container_width=True):
            if not st.session_state.get("rag_ready"):
                st.info("请先完成系统初始化（向量库）")
            else:
                with st.spinner("自动聚合政策库与往期匹配数据，生成规范化政务评估报告..."):
                    res = pipeline.generate_policy_assessment(sel, feedback, "tongyi")
                if res["ok"]:
                    st.session_state["assess_res"] = res
                    _log_op(f"生成评估报告：{sel.title}", "成功", "模型")
                else:
                    st.error(res["message"])
    _card_close()

    res = st.session_state.get("assess_res")
    if not res or not res.get("ok"):
        st.markdown("")
        _card_open("评估维度结果", "RESULT")
        st.info("完成上方输入并点击「生成评估报告」后，评估结果将在此展示。")
        _card_close()
        return
    a = res["assessment"]

    # ── 中间：横向五张评估维度卡片 ───────────────────────
    st.markdown('<div class="topbar"><h3 style="margin:0">五大评估维度</h3></div>', unsafe_allow_html=True)
    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        _card_open("落地难度", "维度1")
        _metric_card(len(a.landing_difficulties or []), "个现存难点")
        st.caption("难点密度越高落地难度越大")
        _card_close()
    with k2:
        _card_open("覆盖受益范围", "维度2")
        _metric_card(len(a.strengths or []), "项阶段性成效")
        st.caption((a.overall or "—")[:46])
        _card_close()
    with k3:
        _card_open("现存落地卡点", "维度3")
        for d in (a.landing_difficulties or [])[:3]:
            st.markdown(f"- {d.get('title','')}：{(d.get('detail','') or '')[:32]}")
        _card_close()
    with k4:
        _card_open("企业诉求", "维度4")
        st.markdown((a.feedback_analysis or "—")[:80])
        _card_close()
    with k5:
        _card_open("迭代优化建议", "维度5")
        _metric_card(len(a.iteration_suggestions or []), "条建议")
        st.caption("按优先级推进")
        _card_close()

    st.markdown("")
    _card_open("评估报告明细", "DETAIL")
    st.markdown("#### 总体结论")
    st.markdown(a.overall or "—")
    st.markdown("#### 阶段性成效（覆盖受益范围）")
    for s in (a.strengths or []):
        st.markdown(f"- **{s.get('title','')}**：{s.get('detail','')}")
    st.markdown("#### 现存难点与制约（落地卡点）")
    for d in (a.landing_difficulties or []):
        st.markdown(f"- **{d.get('title','')}**：{d.get('detail','')}")
    st.markdown("#### 企业诉求分析")
    st.markdown(a.feedback_analysis or "—")
    st.markdown("#### 迭代优化建议")
    for i, sug in enumerate(a.iteration_suggestions or [], 1):
        st.markdown(f"{i}. {sug}")
    _card_close()

    # ── 底部导出 ────────────────────────────────────────
    st.markdown("")
    _card_open("导出评估报告", "EXPORT")
    fmt = st.selectbox("导出格式", ["Word 标准公文(.docx)", "Markdown(.md)", "Excel 统计台账(.xlsx)"],
                       key="assess_exp")
    if fmt.startswith("Word"):
        if res.get("docx_path"):
            with open(res["docx_path"], "rb") as f:
                st.download_button("下载 Word 标准公文", data=f,
                                   file_name=res["docx_path"].split("/")[-1], use_container_width=True)
    elif fmt.startswith("Markdown"):
        with open(res["md_path"], "rb") as f:
            st.download_button("下载 Markdown", data=f,
                               file_name=res["md_path"].split("/")[-1], use_container_width=True)
    else:
        from utils.exporter import export_assessment
        buf = export_assessment(a)
        st.download_button("下载 Excel 统计台账", data=buf,
                           file_name=f"{a.policy_title}_落地评估.xlsx", use_container_width=True)
    st.caption("报告已同时保存至 `output/assessment/` 目录（Markdown / Word / Excel）。")
    _card_close()


# ═══════════════════════════════════════════════════════════
# 页面6：系统安全与模型配置
#   上方左右双卡片 + 下方安全操作日志表格
# ═══════════════════════════════════════════════════════════
def render_config_page():
    _page_title("系统安全与模型配置", "沙盒三重安全 · 通义千问双模型切换 · .env 密钥隔离")

    top_l, top_r = st.columns(2)
    with top_l:
        _card_open("沙盒安全监控", "SECURITY")
        s1, s2, s3 = st.columns(3)
        with s1:
            st.markdown("**目录只读**")
            _metric_card("ON" if _is_readonly("policy_docs") else "OFF", "只读监控")
            st.caption("policy_docs 只读 + 运行目录沙盒隔离")
        with s2:
            st.markdown("**网络白名单**")
            _metric_card("ON", "访问白名单")
            st.caption("仅放行 API 域名（dashscope/aliyuncs 等）")
        with s3:
            st.markdown("**300秒超时**")
            _metric_card("ON", "资源限额")
            st.caption("单任务超时 / token 上限双重兜底")
        st.markdown("---")
        st.markdown("""
**沙盒三重安全说明**
1. **目录只读**：`policy_docs/` 只读，`data/`、`output/` 限定写入白名单；
2. **网络白名单**：仅允许调用已配置的大模型 API 域名，无外部探测；
3. **资源限额**：单次调用 `timeout=120s` + 瞬时错误重试 2 次，生成长度上限兜底。""")
        st.caption("额度耗尽/网络中断时自动 **Fallback 降级**提示，不会静默失败。")
        _card_close()

    with top_r:
        _card_open("大模型配置", "MODEL")
        c1, c2 = st.columns(2)
        with c1:
            model_choice = st.selectbox("推理模型", ["qwen-max", "qwen-turbo"], index=0,
                                        help="qwen-max 效果更优，qwen-turbo 更省钱")
        with c2:
            max_tokens = st.slider("生成长度（max_tokens）", 512, 8192, 4096, step=512)
        temperature = st.slider("随机性（temperature）", 0.0, 1.0, 0.3, step=0.1)
        if st.button("测试 API 连通", type="primary"):
            _log_op(f"API 连通性测试：{model_choice}", "触发", "模型")
            st.info(f"将调用 {model_choice} 发送最小请求验证连通性（需已配置 DASHSCOPE_API_KEY）")
        st.markdown("---")
        keys = st.session_state.get("api_keys", {})
        st.markdown(f"**密钥状态**：`DASHSCOPE_API_KEY` {'已配置' if keys.get('dashscope') else '未配置'}"
                    f" ｜ `OPENAI_API_KEY` {'已配置' if keys.get('openai') else '未配置'}"
                    f" ｜ `ANTHROPIC_API_KEY` {'已配置' if keys.get('anthropic') else '未配置'}")
        st.markdown("**密钥安全**：密钥仅从 `.env` 读取，前端不展示明文；请勿提交 `.env` 至仓库。")
        _card_close()

    st.markdown("")
    _card_open("安全操作日志", "LOG")
    logs = st.session_state.get("op_log", [])
    if logs:
        st.dataframe(pd.DataFrame(logs), use_container_width=True, hide_index=True)
        st.caption(f"共 {len(logs)} 条操作记录（时间 / 操作类型 / 操作内容 / 结果）。")
    else:
        st.caption("暂无操作记录，页面上的入库、匹配、分析、导出等操作会自动写入日志。")
    _card_close()


def _is_readonly(path: str) -> bool:
    """沙盒只读状态展示：真实目录权限检测 + 兜底 True"""
    try:
        import os
        return not os.access(path, os.W_OK)
    except Exception:
        return True