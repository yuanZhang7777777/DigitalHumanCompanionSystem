# 数字人陪伴系统 - 后端API

## 快速启动指南

### 1. 激活虚拟环境
```bash
.\venv\Scripts\activate
```

### 2. 启动服务器
```bash
python run.py
```
或者
```bash
uvicorn app.main:app --reload
```

### 3. 访问API文档
- API文档：http://localhost:8000/docs
- 根路径：http://localhost:8000/
- 健康检查：http://localhost:8000/health

## 项目结构

```
backend/
├── venv/                    # Python虚拟环境
├── app/
│  ├── __init__.py          # 应用初始化
│   ├── main.py             # 主程序入口
│   ├── config.py           # 配置文件
│   ├── database.py         # 数据库连接
│   ├── models/             # 数据模型
│   ├── routers/            # API路由
│   ├── services/           # 业务逻辑
│   └── utils/              # 工具函数
├── .env                    # 环境变量
├── requirements.txt        # 依赖列表
└── run.py                  # 启动脚本
```

## 数据库集合

MongoDB数据库：`digital_companion`

集合：
- users - 用户信息
- digital_persons - 数字人配置
- conversations - 对话记录
- emotional_analysis - 情感分析
- career_suggestions - 职业建议

## 当前状态

✅ Python虚拟环境已创建
✅ FastAPI项目已搭建
✅ MongoDB已连接
✅ 数据库集合已创建
✅ 所有依赖已安装

📝 下一步：测试服务器启动
