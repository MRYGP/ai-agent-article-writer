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

## 🚀 快速启动
### 1. 环境准备
```bash
# 克隆项目
git clone https://github.com/你的用户名/ai-agent-article-writer.git
cd ai-agent-article-writer

# 安装依赖
pip install -r requirements.txt
