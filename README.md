# SK-AutoWriter 公众号自动化Agent
> 监控案例文件夹 → 自动读取评估报告 → 调用AI生成公众号文章

---

## ✨ 项目简介
SK-AutoWriter 是一个轻量级、自动化的AI Agent，专门用于将AI产品评估报告自动转换成结构完整、可直接发布的公众号文章。

### 核心能力
- **自动监控**：监听指定文件夹，新文件一创建就自动触发处理
- **智能改写**：基于预设的公众号写作框架，自动提炼报告核心数据、反直觉洞察和失败案例
- **自动输出**：生成Markdown格式的文章，保存到指定目录，可直接复制发布
- **稳定可靠**：内置文件写入校验、API超时/重试、并发控制，避免卡死和重复处理

---
📁 项目结构
ai-agent-article-writer/
├── .gitignore              # 忽略敏感文件与垃圾文件
├── README.md               # 项目说明文档
├── requirements.txt        # Python依赖清单
├── agent3a_article.md      # 公众号文章写作提示词模板
├── sk_autowriter.py        # Agent主程序
├── cases/2026/             # 待处理的评估报告目录（监控文件夹）
└── articles/2026/          # 生成的公众号文章输出目录
## 🚀 快速启动
### 1. 环境准备
```bash
# 克隆项目
git clone https://github.com/你的用户名/ai-agent-article-writer.git
cd ai-agent-article-writer

# 安装依赖
pip install -r requirements.txt
📝 使用流程
启动 Agent：运行 python sk_autowriter.py，终端会显示监控启动成功
放入报告：将 Markdown 格式的评估报告（如 CASE-001.md）复制到 cases/2026/ 文件夹
自动处理：Agent 会自动读取文件，调用 AI 生成公众号文章
获取结果：生成的文章会自动保存到 articles/2026/ 目录，文件名格式为 Article_原文件名.md
