"""政务风 UI：6 大页面卡片化渲染（首页/知识库/政企匹配/申报标准化/落地评估/系统配置）。
全部页面统一使用白色圆角卡片 .gcard 分块，遵循政务蓝 #165DFF 视觉规范。"""
import io
import glob as g
from pathlib import Path
from typing import List, Optional

import pandas as pd
import streamlit as st

from core.schemas import ExtractedPolicy, EnterpriseNeed, ABComparison, MatchResult


# ═══════════════════════════════════════════════════════════
# 卡片辅助：政务白底卡片 + 标题 + 可选标签
# ═══════════════════════════════════════════════════════════
def _card_open(title: str = "", tag: str = ""):
    tag_html = f'<span class="card-tag">{tag}</span>' if tag else ""
    title_html = f"<h3>{title}</h3>" if title else ""
    st.markdown(f'<div class="gcard">{title_html}{tag_html}', unsafe_allow_html=True)


def _card_close():
    st.markdown("</div>", unsafe_allow_html=True)


def _metric_card(num, label):
    st.markdown(
        f'<div class="metric-card"><div class="metric-num">{num}</div>'
        f'<div class="metric-label">{label}</div></div>', unsafe_allow_html=True)


def _page_title(title: str, desc: str = ""):
    st.markdown(f"### {title}")
    if desc:
        st.caption(desc)


def _go_to(page_label: str):
    st.session_state["nav_page"] = page_label
    st.rerun()


# ═══════════════════════════════════════════════════════════
# 页面1：首页 · 系统总览仪表盘
# ═══════════════════════════════════════════════════════════
def render_home_page():
    pipeline = st.session_state.get("pipeline")
    stats = pipeline.get_system_stats() if pipeline else {}

    _card_open("欢迎使用 · 政策智能分析Agent系统", "SYSTEM OVERVIEW")
    st.markdown(
        "面向 **政务实验室项目申报、中小企业政策扶持匹配、政策落地效果研判** 场景的一体化智能分析平台。"
        "集成 RAG 政策知识库 + 大模型要素抽取 + 企业政策匹配 + 申报材料标准化 + 落地评估报告，全流程可溯源、可导出。")
    _card_close()

    st.markdown("")
    _card_open("核心数据统计看板")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        _metric_card(stats.get("policy_total", 0), "入库政策文档")
    with c2:
        _metric_card(stats.get("match_services", 0), "企业需求匹配服务次数")
    with c3:
        _metric_card(stats.get("standard_plans", 0), "标准化申报材料清单")
    with c4:
        _metric_card(stats.get("assessment_reports", 0), "政策落地评估报告")
    st.caption(f"向量库当前共 {stats.get('chunks_total', 0)} 个文本分片")
    _card_close()

    st.markdown("")
    _card_open("快捷功能入口", "QUICK START")
    entries = [
        ("📚 政策知识库管理", "上传/解析政策PDF，构建向量知识库", "kb"),
        ("🤝 政企需求智能匹配", "录入企业痛点与经营维度，自动匹配扶持政策", "match"),
        ("📋 政策申报材料标准化", "自动梳理申报流程、材料清单与审核易错点", "standard"),
        ("📊 政策落地评估报告生成", "四维度输入，结构化生成政务评估报告", "assessment"),
        ("⚙️ 系统参数与安全配置", "模型参数、API密钥安全与系统运维", "config"),
    ]
    cols = st.columns(len(entries))
    for col, (label, desc, key) in zip(cols, entries):
        with col:
            if st.button(label, key=f"quick_{key}", use_container_width=True):
                _go_to(label)
            st.caption(desc)
    _card_close()

    st.markdown("")
    _card_open("温馨提示")
    st.markdown("""
1. **API密钥安全**：密钥仅从环境变量 `.env` 读取，界面不展示明文；请勿将密钥提交至公开仓库。
2. **免费额度规避**：通义千问 qwen-max 按 token 计费，长报告生成前请确认额度；可在「系统参数」切换 qwen-turbo 降低成本。
3. **建议流程**：①知识库导入PDF → ②政企匹配输出适配政策 → ③申报材料标准化 → ④落地评估报告生成 → ⑤下载 Markdown/Excel 归档。
""")
    _card_close()


# ═══════════════════════════════════════════════════════════
# 页面2：政策知识库管理（基础模块）
# ═══════════════════════════════════════════════════════════
def render_kb_page():
    _page_title("📚 政策知识库管理", "政策PDF解析入库 · 文档管理 · 向量库状态")

    pipeline = st.session_state.get("pipeline")
    retriever = st.session_state.get("retriever")
    pdf_files = st.session_state.get("pdf_files", [])
    stats = pipeline.get_system_stats() if pipeline else {}

    # 卡1：系统初始化操作
    _card_open("系统初始化操作", "INIT")
    c1, c2, c3 = st.columns(3)
    if c1.button("📁 创建项目目录", use_container_width=True):
        from utils.helpers import ensure_dirs
        ensure_dirs()
        st.success("项目目录已就绪（policy_docs / data / output 等）")
    if c2.button("📥 一键构建向量知识库", use_container_width=True, type="primary"):
        st.session_state["action_ingest"] = True
    if c3.button("🗑️ 清空向量库", use_container_width=True):
        st.session_state["action_clear_vectordb"] = True
    _card_close()

    st.markdown("")
    # 卡2：PDF 政策文件上传
    _card_open("PDF 政策文件上传", "UPLOAD")
    uploaded = st.file_uploader(
        "批量上传政策PDF（自动存入 policy_docs/ 并解析切块入库）",
        type=["pdf"], accept_multiple_files=True)
    if uploaded:
        save_dir = Path("policy_docs")
        save_dir.mkdir(parents=True, exist_ok=True)
        saved = 0
        for uf in uploaded:
            (save_dir / uf.name).write_bytes(uf.getvalue())
            saved += 1
        st.session_state["pdf_files"] = []
        from core.tools import PDFParser
        st.session_state["pdf_files"] = PDFParser.list_pdfs()
        st.success(f"已保存 {saved} 个PDF至 policy_docs/，点击「一键构建向量知识库」完成入库")
    st.caption(f"`policy_docs/` 目录当前发现 {len(pdf_files)} 个PDF文件")
    _card_close()

    st.markdown("")
    # 卡3：政策文档管理表格
    _card_open("政策文档管理", "MANAGE")
    if pdf_files:
        rows = []
        for fp in pdf_files:
            rows.append({
                "文件名称": fp.name,
                "文件大小(KB)": round(fp.stat().st_size / 1024, 1),
                "是否已入库": "是" if stats.get("policy_total", 0) > 0 else "否",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.caption("支持在 `policy_docs/` 目录中直接删除文件后点击「刷新」，重新构建向量库。")
    else:
        st.info("暂无政策文件，请在上方上传PDF。")
    _card_close()

    st.markdown("")
    # 卡4：知识库运行状态
    _card_open("知识库运行状态", "STATUS")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        _metric_card(stats.get("policy_total", 0), "入库政策文档")
    with c2:
        _metric_card(stats.get("chunks_total", 0), "向量文本分片")
    with c3:
        _metric_card("ChromaDB", "向量数据库")
    with c4:
        _metric_card("bge-small-zh / Fallback", "嵌入模型")
    st.caption("存储路径：`data/chroma_db`　|　结构化提取结果：`data/processed/`　|　报告输出：`output/`")
    _card_close()


# ═══════════════════════════════════════════════════════════
# 页面3：政企需求智能匹配【迭代2】
# ═══════════════════════════════════════════════════════════
def render_match_page():
    _page_title("🤝 政企需求智能匹配", "录入中小企业经营现状与痛点 → 检索政策库扶持条目 → 输出匹配分析方案")

    pipeline = st.session_state.get("pipeline")
    retriever = st.session_state.get("retriever")

    if pipeline.retriever.collection.count() == 0:
        st.info("向量库为空，请先前往「政策知识库管理」导入政策PDF。")
        return

    # 卡1：企业信息 & 需求录入表单
    _card_open("企业信息 & 需求录入", "INPUT")
    with st.form("match_form"):
        c1, c2, c3 = st.columns(3)
        with c1:
            ent_name = st.text_input("企业名称", value="武汉华光精密科技有限公司")
            ent_industry = st.text_input("所属行业", value="光电")
            ent_region = st.text_input("注册属地", value="武汉光谷")
        with c2:
            ent_size = st.selectbox("营收规模", ["500万以下", "500万-2000万", "2000万-1亿", "1亿以上"], index=2)
            ent_employees = st.number_input("员工人数", min_value=0, value=86)
            ent_rnd = st.text_input("研发投入占比", value="4.2%")
        with c3:
            ent_patents = st.number_input("知识产权数量", min_value=0, value=12)
            ent_years = st.number_input("成立年限", min_value=1, value=5)
        pain_points = st.text_area(
            "经营痛点（多行输入）", height=90,
            value="研发投入高、融资成本高；缺少知识产权布局与成果转化渠道；申报高新技术企业缺乏辅导，人工审核标准不统一导致材料返工。",
        )
        develop_goal = st.text_area("发展诉求（多行输入）", height=70,
                                    value="获得研发费用补贴；降低融资成本；获得高企认定辅导。")
        support_dir = st.text_area("想要获取的政策扶持方向（多行输入）", height=70,
                                   value="研发费用补贴；贷款贴息；高新技术企业培育奖励。")
        c_sub, c_clear = st.columns(2)
        submitted = c_sub.form_submit_button("🤝 提交匹配", type="primary", use_container_width=True)
        if c_clear.form_submit_button("🧹 清空表单", use_container_width=True):
            st.rerun()
    _card_close()

    if submitted:
        needs = [l.strip() for l in develop_goal.split("\n") + support_dir.split("\n") if l.strip()]
        enterprise = EnterpriseNeed(
            name=ent_name, industry=ent_industry, size=ent_size, revenue=ent_size,
            employee_count=ent_employees, rnd_ratio=ent_rnd, patent_count=ent_patents,
            needs=needs, additional_info={"region": ent_region, "years": ent_years},
        )
        dimensions = {
            "name": ent_name, "industry": ent_industry, "region": ent_region,
            "size": ent_size, "employees": f"{ent_employees}人",
            "rnd_ratio": ent_rnd, "patents": f"{ent_patents}项", "years": f"{ent_years}年",
        }
        with st.spinner("正在检索政策库并调用大模型进行需求匹配分析（约30-60秒）..."):
            res_match = pipeline.match_enterprise(enterprise, top_k=5, model_key="tongyi")
            res_analyze = pipeline.analyze_enterprise_match(pain_points, dimensions, top_k=5, model_key="tongyi")
        st.session_state["match_page"] = {
            "enterprise": enterprise, "res_match": res_match, "res_analyze": res_analyze,
        }

    page_data = st.session_state.get("match_page")
    if not page_data:
        return
    res_match = page_data["res_match"]
    res_analyze = page_data["res_analyze"]
    enterprise = page_data["enterprise"]
    ranked = res_match.get("ranked", [])
    matches = res_match.get("matches", [])

    st.markdown("")
    # 卡2：政策匹配总分结果
    _card_open("政策匹配总分结果", "SCORE")
    if ranked:
        overall = round(sum(r["match_score"] for r in ranked) / len(ranked), 1)
        top = ranked[0]
    else:
        overall, top = 0, None
    c1, c2, c3 = st.columns(3)
    with c1:
        _metric_card(f"{overall}分", "整体匹配分值")
    with c2:
        _metric_card(len(ranked), "适配政策数量")
    with c3:
        _metric_card(top["priority_level"] if top else "—", "最优申报优先级")
    st.markdown("**整体扶持方向总结**")
    report = res_analyze.get('content', '') if res_analyze.get('ok') else '匹配分析失败，请重试。'
    st.markdown(f"<div style='max-height:260px;overflow-y:auto;border:1px solid #E5E6EB;"
                f"border-radius:6px;padding:10px;font-size:14px;color:#1D2129;line-height:1.8;'>{report}</div>",
                unsafe_allow_html=True)
    _card_close()

    st.markdown("")
    # 卡3：细分政策匹配列表表格
    _card_open("细分政策匹配列表", "DETAIL")
    if ranked:
        df = pd.DataFrame(ranked)
        df = df.rename(columns={
            "rank": "排名", "policy_title": "政策名称", "match_score": "匹配度得分",
            "priority_level": "申报优先级", "priority_reason": "适配条款/落地建议",
        })
        st.dataframe(df, use_container_width=True, hide_index=True)

        for m in matches:
            badge = {"高": "🟢", "中": "🟡", "低": "🔴"}.get(m.priority_level, "⚪")
            with st.expander(f"{badge} {m.policy_title} — 匹配度 {m.match_score:.0f}%"):
                st.markdown(f"**申报优先级**：{m.priority_level}　—　{m.priority_reason or '—'}")
                st.markdown(f"**已满足条件**：{('；'.join(m.matched_criteria)) if m.matched_criteria else '暂无'}")
                st.markdown(f"**未满足条件**：{('；'.join(m.unmatched_criteria)) if m.unmatched_criteria else '暂无'}")
                st.caption(m.summary)

        # Excel 导出
        from utils.exporter import export_match_results
        xlsx_bytes = export_match_results(ranked)
        st.download_button("📥 下载匹配结果 Excel", data=xlsx_bytes,
                           file_name=f"{enterprise.name}_匹配结果.xlsx", use_container_width=True)
    else:
        st.info("本次匹配未命中政策，请检查企业信息或先入库更多政策。")
    _card_close()

    st.markdown("")
    # 卡4：原文溯源查看
    _card_open("原文溯源查看", "TRACE")
    if matches:
        titles = {m.policy_id: m.policy_title for m in matches}
        sel_id = st.selectbox("选中政策查看原文片段", list(titles.keys()),
                              format_func=lambda x: titles[x], key="match_trace_sel")
        chunks = retriever.get_by_doc_id(sel_id, top_k=3)
        if chunks:
            for i, ch in enumerate(chunks, 1):
                st.markdown(f"**片段{i}**：")
                st.markdown(f"<div style='max-height:180px;overflow-y:auto;border:1px solid #E5E6EB;"
                            f"border-radius:6px;padding:8px;font-size:13px;color:#6B7785;'>{ch['text']}</div>",
                            unsafe_allow_html=True)
        else:
            st.caption("向量库中未找到该政策原文片段。")
    else:
        st.caption("执行匹配后可在此追溯政策原文，验证分析结论真实性。")
    _card_close()


# ═══════════════════════════════════════════════════════════
# 页面4：政策申报材料标准化【迭代1】
# ═══════════════════════════════════════════════════════════
def render_standard_page():
    _page_title("📋 政策申报材料标准化", "面向专项政府项目申报：申报流程 + 材料清单 + 审核易错点，输出标准化申报材料台账")

    pipeline = st.session_state.get("pipeline")
    policies = pipeline.load_processed_policies() if pipeline else []
    if not policies:
        st.info("暂无已提取政策，请先前往「政策知识库管理」解析政策PDF。")
        return

    # 卡1：选择申报项目
    _card_open("选择申报项目", "SELECT")
    sel = st.selectbox("下拉选定已入库的专项政策项目", policies,
                       format_func=lambda p: p.title, key="std_sel")
    st.markdown(f"**政策ID**：`{sel.id}`　|　**适用主体**：{'、'.join(sel.applicable_entities) or '—'}")
    if st.button("▶️ 生成申报材料标准化台账", type="primary", use_container_width=True):
        with st.spinner("大模型自动梳理申报全链路流程、材料清单与审核易错点（约30-60秒）..."):
            res = pipeline.generate_application_standard(sel, "tongyi")
        if res["ok"]:
            st.session_state["std_page"] = res
            st.success(f"台账已生成：{res['path']}")
        else:
            st.error(res["message"])
    _card_close()

    res = st.session_state.get("std_page")
    if not res or not res.get("ok"):
        return
    std = res["standard"]

    st.markdown("")
    # 卡2：申报全流程梳理
    _card_open("申报全流程梳理", "PROCESS")
    process = pd.DataFrame(std.application_process)
    process = process.rename(columns={"step": "执行环节", "content": "关键内容",
                                      "responsible": "责任主体", "duration": "预计周期"})
    st.dataframe(process, use_container_width=True, hide_index=True)
    _card_close()

    st.markdown("")
    # 卡3：标准化材料清单
    _card_open("标准化材料清单", "MATERIAL")
    checklist = pd.DataFrame(std.material_checklist)
    checklist = checklist.rename(columns={"item": "材料名称", "format": "格式要求",
                                          "content_points": "内容要点", "tips": "提交节点/注意事项"})
    st.dataframe(checklist, use_container_width=True, hide_index=True)
    st.markdown("**材料规范要点**")
    for i, pt in enumerate(std.material_points, 1):
        st.markdown(f"{i}. {pt}")
    _card_close()

    st.markdown("")
    # 卡4：审核易错点汇总 + 一键导出
    _card_open("审核易错点汇总", "RISK")
    for i, mis in enumerate(std.audit_mistakes, 1):
        st.markdown(f"⚠️ {i}. {mis}")
    st.markdown("**质量管控清单**")
    for i, qc in enumerate(std.quality_control, 1):
        st.markdown(f"✔️ {i}. {qc}")
    st.markdown("---")
    c_md, c_xlsx = st.columns(2)
    with open(res["path"], "rb") as f:
        c_md.download_button("⬇️ 下载 Markdown 文档", f, file_name=res["path"].split("/")[-1],
                             use_container_width=True)
    from utils.exporter import export_application_standard
    xlsx_bytes = export_application_standard(std.model_dump())
    c_xlsx.download_button("📥 导出 Excel 材料清单", data=xlsx_bytes,
                           file_name=f"{sel.title}_申报材料台账.xlsx", use_container_width=True)
    st.caption("文档已同步保存至项目 `output/application/` 目录，可长期留存。")
    _card_close()


# ═══════════════════════════════════════════════════════════
# 页面5：政策落地评估报告自动生成【迭代3】
# ═══════════════════════════════════════════════════════════
def render_assessment_page():
    _page_title("📊 政策落地评估报告自动生成", "政策条文 + 适用群体 + 落地约束 + 企业反馈 → 结构化政务评估报告")

    pipeline = st.session_state.get("pipeline")
    policies = pipeline.load_processed_policies() if pipeline else []
    if not policies:
        st.info("暂无已提取政策，请先前往「政策知识库管理」解析政策PDF。")
        return

    # 卡1：关联数据调取
    _card_open("关联数据调取", "DATA BIND")
    sel = st.selectbox("关联扶持政策", policies, format_func=lambda p: p.title, key="assess_sel")
    prior = sorted(g.glob("output/enterprise_match/*.md") + g.glob("output/matching/*.json"), reverse=True)
    st.markdown(f"**政策适用主体**：{'、'.join(sel.applicable_entities) or '—'}")
    st.markdown(f"**关联往期匹配数据**：{len(prior)} 份（存于 `output/enterprise_match/`、`output/matching/`）")
    if prior:
        with st.expander("查看最近一份匹配数据"):
            st.markdown(open(prior[0], encoding="utf-8").read()[:1500])
    _card_close()

    st.markdown("")
    # 卡2：落地情况反馈录入
    _card_open("落地情况反馈录入", "FEEDBACK")
    feedback = st.text_area(
        "填写政策推行进度、企业受益情况、落地阻碍、群众诉求与整改推进台账（多行输入）",
        height=160, key="assess_feedback",
        value="政策发布后已有3家企业完成申报，2家通过初审，1家材料被退回（研发费用归集口径不一致）；"
              "企业普遍反映线上申报系统填报指引不清晰，第三方检测报告模板不统一导致返工；"
              "资金拨付存在延迟，距公示已过3个月仍未到账；企业希望提供申报辅导与材料标准化模板。",
    )
    _card_close()

    st.markdown("")
    # 卡3：报告生成与预览
    _card_open("报告生成与预览", "GENERATE")
    if st.button("▶️ 生成标准化政策落地效果评估报告", type="primary", use_container_width=True):
        with st.spinner("大模型基于四维度生成结构化评估报告（约30-60秒）..."):
            res = pipeline.generate_policy_assessment(sel, feedback, "tongyi")
        if res["ok"]:
            st.session_state["assess_page"] = res
            st.success("报告生成完成")
        else:
            st.error(res["message"])

    res = st.session_state.get("assess_page")
    if res and res.get("ok"):
        a = res["assessment"]
        st.markdown("#### ① 政策落地整体概况")
        st.markdown(a.overall)
        st.markdown("#### ② 落地实施成效")
        for s in a.strengths:
            st.markdown(f"- **{s.get('title','')}**：{s.get('detail','')}")
        st.markdown("#### ③ 现存难点与制约因素")
        for d in a.landing_difficulties:
            st.markdown(f"- **{d.get('title','')}**：{d.get('detail','')}")
        st.markdown("#### ④ 优化迭代对策建议")
        for i, sug in enumerate(a.iteration_suggestions, 1):
            st.markdown(f"{i}. {sug}")
    else:
        st.caption("点击上方按钮生成报告，报告将在此处完整预览。")
    _card_close()

    st.markdown("")
    # 卡4：文档导出
    _card_open("文档导出", "EXPORT")
    if res and res.get("ok"):
        c_md, c_xlsx = st.columns(2)
        with open(res["md_path"], "rb") as f:
            c_md.download_button("⬇️ 下载 Markdown 报告", f,
                                 file_name=res["md_path"].split("/")[-1], use_container_width=True)
        from utils.exporter import export_assessment
        xlsx_bytes = export_assessment(a)
        c_xlsx.download_button("📥 导出 Excel 评估报告", data=xlsx_bytes,
                               file_name=f"{a.policy_title}_落地评估.xlsx", use_container_width=True)
        if res.get("docx_path"):
            with open(res["docx_path"], "rb") as f:
                st.download_button("📄 下载 Word 文档", f,
                                   file_name=res["docx_path"].split("/")[-1], use_container_width=True)
        st.caption(f"报告已保存至 `output/assessment/` 目录（Markdown / Word / Excel 三格式）。")
    else:
        st.caption("生成报告后可在此下载 Markdown / Excel / Word 多格式文档。")
    _card_close()


# ═══════════════════════════════════════════════════════════
# 页面6：系统参数与安全配置
# ═══════════════════════════════════════════════════════════
def render_config_page():
    _page_title("⚙️ 系统参数与安全配置", "模型推理参数 · API密钥安全管理 · 系统运维")

    # 卡1：大模型推理参数
    _card_open("大模型推理参数", "MODEL")
    c1, c2, c3 = st.columns(3)
    with c1:
        model_choice = st.selectbox("推理模型", ["qwen-max", "qwen-turbo"],
                                    index=0, help="qwen-max 效果更优，qwen-turbo 更省钱")
    with c2:
        max_tokens = st.slider("生成长度（max_tokens）", 512, 8192, 4096, step=512)
    with c3:
        temperature = st.slider("随机性（temperature）", 0.0, 1.0, 0.3, step=0.1)
    st.caption("当前版本通义千问经 DashScope OpenAI 兼容接口直连调用；参数在代码层生效，后续可扩展为运行时配置。")

    # 资源/成本统计（模型调用兜底监控）
    mc = st.session_state.get("model_client")
    if mc and hasattr(mc, "get_cost_summary"):
        cost = mc.get_cost_summary()
        k1, k2, k3 = st.columns(3)
        with k1:
            _metric_card(cost["input_tokens"], "累计输入 tokens")
        with k2:
            _metric_card(cost["output_tokens"], "累计输出 tokens")
        with k3:
            _metric_card(f"¥{cost['est_cost_yuan']}", "预估费用（通义千问）")
        st.caption("单次调用均受超时(120s)与瞬时错误重试(2次)兜底；意图分类固定 temperature=0，事实问答默认 0.3。")
    _card_close()

    st.markdown("")
    # 卡2：API密钥安全管理
    _card_open("API 密钥安全管理", "SECURITY")
    keys = st.session_state.get("api_keys", {})
    rows = [("dashscope", "通义千问 Qwen"), ("openai", "OpenAI"), ("anthropic", "Claude")]
    for short, label in rows:
        present = bool(keys.get(short))
        c1, c2 = st.columns([1, 3])
        with c1:
            st.markdown(f"**{label}**")
        with c2:
            st.markdown(f"`{short.upper()}_API_KEY`：{'✅ 已配置（仅从环境变量读取，不展示明文）' if present else '⚠️ 未配置'}")
    st.markdown("---")
    st.markdown("""
**安全规则**
- 密钥仅通过 `.env` 环境变量加载，界面/日志均不展示明文；
- 免费额度用尽或密钥失效时，模型调用会抛出明确错误提示，不会静默扣费；
- 请勿将 `.env`、`data/`、`output/` 提交到公开仓库，防止密钥泄露。
""")
    _card_close()

    st.markdown("")
    # 卡3：系统运维
    _card_open("系统运维", "OPS")
    c1, c2, c3 = st.columns(3)
    if c1.button("🧹 清理缓存", use_container_width=True):
        import shutil
        shutil.rmtree("data/cache", ignore_errors=True)
        Path("data/cache").mkdir(parents=True, exist_ok=True)
        st.success("缓存已清理")
    if c2.button("📜 查看运行日志", use_container_width=True):
        log_files = list(Path("logs").glob("*.log")) + list(Path(".").glob("*.log"))
        if log_files:
            with st.expander("最近日志（尾部200行）"):
                st.code("\n".join(log_files[0].read_text(encoding="utf-8").splitlines()[-200:]))
        else:
            st.info("暂未发现日志文件")
    if c3.button("♻️ 项目整体重置", use_container_width=True):
        import shutil
        for d in ["data/chroma_db", "data/cache"]:
            shutil.rmtree(d, ignore_errors=True)
        for d in ["output/assessment", "output/matching", "output/application", "output/enterprise_match"]:
            shutil.rmtree(d, ignore_errors=True)
        st.success("已重置向量库与输出目录，可重新导入数据")
    _card_close()
