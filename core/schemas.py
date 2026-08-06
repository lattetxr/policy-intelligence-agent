from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class SubsidyStandard(BaseModel):
    subsidy_type: str = ""                 # 补贴类型（研发补贴/贷款贴息/人才奖励等）
    amount_or_ratio: str = ""              # 金额或比例
    conditions: List[str] = Field(default_factory=list, description="享受条件")


class ExtractedPolicy(BaseModel):
    id: str = ""
    title: str = ""
    source_file: str = ""
    publish_date: Optional[str] = None
    issuing_body: Optional[str] = None
    document_type: Optional[str] = None
    eligibility_criteria: List[str] = Field(default_factory=list, description="申报门槛")
    applicable_entities: List[str] = Field(default_factory=list, description="适用主体")
    policy_thresholds: Dict[str, str] = Field(default_factory=dict, description="政策阈值（量化指标）")
    constraint_clauses: List[str] = Field(default_factory=list, description="约束条款")
    support_scope: Optional[str] = None
    subsidy_standards: List[SubsidyStandard] = Field(default_factory=list, description="补贴标准")
    application_process: Optional[str] = None
    raw_text_snippet: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class EnterpriseNeed(BaseModel):
    name: str = ""
    industry: str = ""
    size: str = ""
    registered_capital: Optional[str] = None
    revenue: Optional[str] = None
    employee_count: Optional[int] = None
    rnd_ratio: Optional[str] = None
    patent_count: Optional[int] = None
    needs: List[str] = Field(default_factory=list)
    additional_info: Dict[str, Any] = Field(default_factory=dict)


class MatchResult(BaseModel):
    policy_title: str = ""
    policy_id: str = ""
    match_score: float = 0.0
    priority_level: str = ""               # 申报优先级：高/中/低
    priority_reason: str = ""
    matched_criteria: List[str] = Field(default_factory=list)
    unmatched_criteria: List[str] = Field(default_factory=list)
    summary: str = ""


class FeedbackEntry(BaseModel):
    date: str = ""                         # 反馈日期
    team: str = ""                         # 反馈团队
    category: str = ""                     # 分类：申报流程/材料要求/政策解读/资金到位等
    content: str = ""                      # 反馈内容
    status: str = ""                       # 状态：已解决/进行中/未解决
    impact: str = ""                       # 影响说明


class FeedbackLedger(BaseModel):
    policy_title: str = ""
    research_team: str = ""
    period: str = ""
    feedback_items: List[FeedbackEntry] = Field(default_factory=list)


class AssessmentReport(BaseModel):
    policy_title: str = ""
    policy_id: str = ""
    generated_at: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    applicability_assessment: str = ""
    key_requirements: List[str] = Field(default_factory=list)
    risk_notes: List[str] = Field(default_factory=list)
    recommendation: str = ""
    model_used: str = ""


class ABComparison(BaseModel):
    question: str = ""
    model_a: str = ""
    model_b: str = ""
    answer_a: str = ""
    answer_b: str = ""
    analysis: str = ""


class EnterpriseMatchReport(BaseModel):
    """企业需求-政策匹配分析结果（迭代2：痛点驱动匹配 + 适配条目 + 落地建议）"""
    enterprise_name: str = ""
    pain_points: str = ""
    dimensions: Dict[str, Any] = Field(default_factory=dict)
    generated_at: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    model_used: str = ""
    matched_policies: List[str] = Field(default_factory=list, description="命中的政策标题列表")
    match_analysis: str = ""            # 匹配度分析正文
    adapted_items: str = ""             # 适配政策条目（政策→具体扶持条目）
    landing_advice: str = ""            # 落地建议（申报路径、材料、优先级）


class PolicyAssessment(BaseModel):
    """政策落地效果评估报告（迭代3：政策条文+适用人群+落地约束+用户反馈 → 优势/难点/迭代建议）"""
    policy_title: str = ""
    policy_id: str = ""
    generated_at: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    model_used: str = ""
    overall: str = ""                                   # 总体评估结论
    strengths: List[Dict[str, str]] = Field(default_factory=list,
        description="政策优势：[{title, detail}]")
    landing_difficulties: List[Dict[str, str]] = Field(default_factory=list,
        description="落地难点：[{title, detail}]")
    feedback_analysis: str = ""                         # 用户反馈维度分析
    iteration_suggestions: List[str] = Field(default_factory=list,
        description="迭代建议")


class ApplicationStandard(BaseModel):
    """政策申报材料标准化结果（迭代1：申报流程 + 材料要点 + 易错点 + 材料清单）"""
    policy_title: str = ""
    policy_id: str = ""
    generated_at: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    model_used: str = ""
    application_process: List[Dict[str, str]] = Field(default_factory=list,
        description="申报全链路流程：[{step, content, responsible, duration}]")
    material_points: List[str] = Field(default_factory=list, description="材料规范要点")
    audit_mistakes: List[str] = Field(default_factory=list, description="审核易错点")
    material_checklist: List[Dict[str, str]] = Field(default_factory=list,
        description="标准化申报材料清单：[{item, format, content_points, tips}]")
    quality_control: List[str] = Field(default_factory=list, description="质量管控清单")
