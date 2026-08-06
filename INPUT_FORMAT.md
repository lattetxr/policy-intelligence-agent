# 输入格式说明

## ① policy_docs/ — 政策PDF

将政策文件 PDF 放入本目录，运行「全流程 → ① 政策PDF解析」即可：
自动切片 → RAG向量库 → 调用通义千问提取 **申报门槛 / 补贴标准 / 适用企业** → 结果存至 `data/processed/*.json`。

## ② data/input/enterprises/ — 企业信息

可选。也可在网页侧边栏直接填写企业信息。

```json
{
  "name": "企业名称",
  "industry": "所属行业",
  "size": "小型",
  "registered_capital": "500万元",
  "revenue": "3200万元",
  "employee_count": 85,
  "rnd_ratio": "4.2%",
  "patent_count": 12,
  "needs": ["研发费用补贴", "高新技术企业培育"]
}
```

## ③ data/input/feedback/ — 科研团队反馈台账（模块3输入）

**输入入口**：将台账文件放入本目录（支持 `.json` / `.xlsx` / `.csv`），
或在「全流程 → ③ 落地评估报告」页面上传文件。

**JSON 格式**：

```json
{
  "policy_title": "政策名称",
  "research_team": "团队名",
  "period": "2026年第二季度",
  "feedback_items": [
    {
      "date": "2026-04-10",
      "team": "微纳制造团队",
      "category": "申报流程",     // 分类：申报流程/材料要求/政策解读/资金到位
      "content": "反馈内容",
      "status": "已解决",          // 状态：已解决/进行中/未解决
      "impact": "影响说明"
    }
  ]
}
```

**Excel 格式**（表头固定）：`日期 | 团队 | 分类 | 内容 | 状态 | 影响`

## 输出目录

| 模块 | 输出路径 |
|------|----------|
| ① 政策要素提取 | `data/processed/*.json` |
| ② 政企匹配 | `output/matching/*.json` |
| ③ 落地评估报告 | `output/assessment/*.md` |
