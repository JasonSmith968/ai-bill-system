AI Bill System

AI智能记账系统

一个基于 AI 的个人财务管理与智能记账平台，通过自然语言、票据识别和自动分类能力，帮助用户快速完成日常记账、财务统计和支出分析。

---

项目简介

AI Bill System 是一个结合人工智能能力的智能记账系统。

用户可以通过自然语言输入消费记录，例如：

«今天中午吃饭花了38元
打车到机场花费126元
购买 Cursor Pro 订阅 20 美元»

系统将自动完成：

- 金额提取
- 时间识别
- 分类归档
- 数据存储
- 财务统计
- AI分析

帮助用户降低记账成本，提高财务管理效率。

---

核心功能

智能记账

支持自然语言输入：

今天午餐花费45元
购买域名花费88元
支付Claude会员20美元

自动解析：

- 金额
- 时间
- 分类
- 支付方式

---

AI自动分类

自动识别消费类别：

输入内容| 自动分类
午餐| 餐饮
滴滴打车| 交通
Cursor Pro| 软件订阅
域名续费| 互联网服务
酒店住宿| 差旅

---

数据统计

支持：

- 日统计
- 周统计
- 月统计
- 年统计

生成：

- 收支报表
- 分类占比
- 趋势分析

---

AI财务分析

自动生成财务洞察：

例如：

- 本月餐饮支出增长 23%
- 软件订阅成本增加
- 差旅费用高于平均水平

帮助用户了解消费习惯。

---

多模型支持（规划中）

支持接入：

- OpenAI GPT
- Claude
- DeepSeek
- Qwen
- Gemini

用户可自由切换 AI 模型。

---

技术架构

后端

- Python
- Flask / FastAPI
- SQLite / MySQL
- SQLAlchemy

AI能力

- OpenAI API
- Claude API
- DeepSeek API

前端

- HTML
- CSS
- JavaScript

部署

- Docker
- Railway
- Render
- VPS

---

项目结构

ai-bill-system
│
├── app/
├── database/
├── models/
├── routes/
├── services/
├── static/
├── templates/
├── utils/
│
├── config.py
├── app.py
├── requirements.txt
└── README.md

---

本地运行

1. 克隆项目

git clone https://github.com/JasonSmith968/ai-bill-system.git

cd ai-bill-system

---

2. 创建虚拟环境

python -m venv venv

Windows：

venv\Scripts\activate

Mac/Linux：

source venv/bin/activate

---

3. 安装依赖

pip install -r requirements.txt

---

4. 配置环境变量

创建：

.env

填写：

OPENAI_API_KEY=your_api_key
CLAUDE_API_KEY=your_api_key
DEEPSEEK_API_KEY=your_api_key

---

5. 启动项目

python app.py

访问：

http://127.0.0.1:5000

---

开发路线图

V1

- [x] 基础记账功能
- [x] 数据库设计
- [x] Web界面
- [x] GitHub部署

V2

- [ ] AI自动分类
- [ ] 支出分析
- [ ] 数据可视化

V3

- [ ] OCR票据识别
- [ ] 微信账单导入
- [ ] 支付宝账单导入

V4

- [ ] Agent自动记账
- [ ] AI财务顾问
- [ ] SaaS商业化

---

商业化方向

未来计划提供：

免费版

- 基础记账
- 数据统计

Pro版

- AI自动分类
- 高级分析
- OCR识别

Team版

- 团队财务管理
- 企业报销分析
- API接口

---

贡献

欢迎提交：

- Issue
- Pull Request
- 功能建议

共同完善 AI Bill System。

---

License

MIT License

---

作者

Jason Smith

GitHub:

https://github.com/JasonSmith968

---

如果这个项目持续迭代，目标将不仅是一个记账工具，而是一个 AI 驱动的个人财务管理平台。
