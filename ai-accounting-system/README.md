# AI智能记账系统

一个基于 Vue3 + Flask + MySQL + DeepSeek AI 的智能记账系统。

## 功能特性

- **用户系统**：注册、登录、JWT鉴权、个人信息管理
- **收支记录**：手动添加、编辑、删除、筛选、分页
- **AI记账**：输入一句话，AI自动识别收支类型、金额、分类
- **数据统计**：总览仪表盘、收支趋势、分类统计
- **管理后台**：用户管理、分类管理、系统统计
- **UI特性**：深色模式、响应式设计、手机端适配

## 技术栈

### 前端
- Vue 3
- Vue Router 4
- Pinia (状态管理)
- TailwindCSS
- Chart.js (图表)
- Axios

### 后端
- Flask
- Flask-SQLAlchemy
- Flask-Migrate
- PyJWT
- DeepSeek API

### 数据库
- MySQL 8.0+

## 项目结构

```
ai-accounting-system/
├── backend/                  # Flask后端
│   ├── app.py               # 主应用
│   ├── config.py            # 配置文件
│   ├── init_db.py           # 数据库初始化
│   ├── requirements.txt     # Python依赖
│   ├── models/              # 数据模型
│   ├── routes/              # API路由
│   ├── services/            # 业务逻辑
│   └── utils/               # 工具函数
├── frontend/                # Vue3前端
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── views/           # 页面组件
│       ├── stores/          # 状态管理
│       ├── router/          # 路由配置
│       ├── layouts/         # 布局组件
│       └── utils/           # 工具函数
└── README.md
```

## 快速开始

### 1. 环境准备

- Python 3.9+
- Node.js 18+
- MySQL 8.0+

### 2. 数据库配置

登录MySQL，创建数据库：

```sql
CREATE DATABASE ai_accounting CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 3. 后端配置

```bash
cd backend

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，配置数据库连接和API密钥
```

编辑 `.env` 文件：

```env
DATABASE_URL=mysql+pymysql://root:your_password@localhost:3306/ai_accounting
SECRET_KEY=your-secret-key
JWT_SECRET_KEY=your-jwt-secret
DEEPSEEK_API_KEY=your-deepseek-api-key
```

### 4. 初始化数据库

```bash
python init_db.py
```

这将创建所有表、默认分类和管理员账号（admin / admin123）。

### 5. 启动后端

```bash
python app.py
```

后端将在 http://localhost:5000 运行。

### 6. 前端配置

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

前端将在 http://localhost:5173 运行。

### 7. 访问系统

打开浏览器访问 http://localhost:5173

- 管理员账号：admin / admin123

## API文档

### 认证相关

- `POST /api/auth/register` - 用户注册
- `POST /api/auth/login` - 用户登录
- `GET /api/auth/me` - 获取当前用户
- `PUT /api/auth/me` - 更新用户信息
- `PUT /api/auth/password` - 修改密码
- `POST /api/auth/refresh` - 刷新令牌

### 交易记录

- `GET /api/transactions` - 获取交易列表
- `POST /api/transactions` - 创建交易
- `GET /api/transactions/:id` - 获取单条记录
- `PUT /api/transactions/:id` - 更新记录
- `DELETE /api/transactions/:id` - 删除记录
- `GET /api/transactions/categories` - 获取分类列表

### 数据统计

- `GET /api/dashboard/summary` - 总览统计
- `GET /api/dashboard/trend` - 收支趋势
- `GET /api/dashboard/category-stats` - 分类统计
- `GET /api/dashboard/recent` - 最近交易

### AI记账

- `POST /api/ai/parse` - AI解析文本
- `POST /api/ai/confirm` - 确认保存
- `POST /api/ai/quick-add` - 快速AI记账

### 管理后台

- `GET /api/admin/stats` - 系统统计
- `GET /api/admin/users` - 用户列表
- `PUT /api/admin/users/:id/status` - 更新用户状态
- `GET /api/admin/categories` - 分类列表
- `POST /api/admin/categories` - 创建分类
- `PUT /api/admin/categories/:id` - 更新分类
- `DELETE /api/admin/categories/:id` - 删除分类

## DeepSeek AI配置

1. 访问 https://platform.deepseek.com 注册账号
2. 获取API密钥
3. 在 `.env` 文件中配置 `DEEPSEEK_API_KEY`

## 部署说明

### 后端部署

```bash
# 使用gunicorn
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### 前端部署

```bash
# 构建生产版本
npm run build

# 将 dist 目录部署到 Nginx 或其他 Web 服务器
```

### Nginx配置示例

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        root /path/to/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    location /api {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 常见问题

### 1. 数据库连接失败

检查 `.env` 文件中的数据库配置是否正确，确保MySQL服务已启动。

### 2. AI功能不工作

检查是否正确配置了 `DEEPSEEK_API_KEY`。如果没有配置，系统会使用本地解析作为备用方案。

### 3. CORS错误

确保后端的 `CORS_ORIGINS` 配置包含前端地址。

## 许可证

MIT License