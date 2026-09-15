# Technical Report

The repository contains two versions of the report, both compiled to PDF.

| File | Language | Compiler |
|---|---|---|
| `report.tex` / `report.pdf` | English | `pdflatex` |
| `report_zh.tex` / `report_zh.pdf` | 中文 | `xelatex` + `ctex` |

## English version

```bash
cd report
pdflatex -interaction=nonstopmode -halt-on-error report.tex
pdflatex -interaction=nonstopmode -halt-on-error report.tex
```

## 中文版本

```bash
cd report
xelatex -interaction=nonstopmode -halt-on-error report_zh.tex
xelatex -interaction=nonstopmode -halt-on-error report_zh.tex
```

## Contents

- Introduction and design goals / 引言与设计目标
- System architecture / 系统架构
- Skill interface and registry / 技能接口与注册表
- Implementation of navigation, validation, and recovery / 导航、验证与恢复实现
- Closed-loop execution feedback / 闭环执行反馈
- Experimental platform and test results / 实验平台与测试结果
- Safety, limitations, and next steps / 安全性、局限性与后续工作
- References / 参考文献

## Figures

- `figures/architecture.png`: original English report figure.
- `figures/architecture_feedback.png`: updated architecture figure used by
  both current reports, including the execution-feedback edge.
