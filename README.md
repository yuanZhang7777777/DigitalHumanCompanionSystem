# 数字人情感陪伴系统 (Digital Companion System V2)

本项目是一个包含智能情感分析、专业面试辅导、天气提醒功能和本地语音合成（GPT-SoVITS）的数字人陪伴系统。项目采用前后端分离架构搭建。

---

## 一、 系统启动指南

系统运行需要分别启动后端（FastAPI）、前端（Vue3 + Vite）以及可选的本地语音合成服务引擎。

### 1. 启动后端 (Backend)

后端使用 Python 构建，负责 AI 逻辑、数据存储、对话流管理。

**操作步骤 (在终端中运行)：**
```powershell
# 1. 切换到后端目录
cd backend

# 2. 激活虚拟环境 (Windows)
.\venv_new\Scripts\activate
# (如果是 Mac/Linux，使用 source venv_new/bin/activate)

# 3. 安装依赖 (如果是首次部署)
pip install -r requirements.txt

# 4. 启动服务 (默认跑在 8000 端口)
uvicorn app.main:app --reload --port 8000
```
*提示：可以通过访问 `http://127.0.0.1:8000/docs` 查看后端的自动 API 文档。*

### 2. 启动前端 (Frontend)

前端基于 Vue 3 + Vite 构建，负责用户交互和卡片/徽章动效渲染。

**操作步骤 (在新开启的一个终端中运行)：**
```powershell
# 1. 切换到前端目录
cd frontend

# 2. 安装 Node 依赖 (首部部署时使用)
npm install

# 3. 启动开发服务器
npm run dev
```
*完成后，通常可以通过浏览器访问 `http://localhost:5173/` 体验项目。*

---

## 二、 语音合成 (GPT-SoVITS) 启动配置

由于系统深度集成了 GPT-SoVITS 来实现高度逼真的个性化声音，如果你期望系统不仅仅使用云端默认发声，还需要单独启动它的 API。

### 1. 终端启动命令
你需要进入你个人本地下载的 `GPT-SoVITS` 核心工具目录下启动它的 Web API。
```powershell
# 切换到你的 GPT-SoVITS 根目录
cd E:\你的路径\GPT-SoVITS

# 启动环境并运行 API 监听程序
# (取决于你的版本，通常运行 api_v2.py 或 api.py)
runtime\python.exe api_v2.py -a 127.0.0.1 -p 9880 
```

### 2. 语音文件在哪里配置？
我们的项目中并没有将体积庞大的 `.pth` 后缀权重和 `.wav` 参考音频打包进代码里。系统是采用**动态查询数据库配置**的方式来调用这些文件的。

这部分语音信息存放于 MongoDB 数据库底下的 `digital_persons` 集合（数字人档案集合）中。
在对应数字人的 `tts_config` 字段里，它长这样：
```json
"tts_config": {
  "gpt_weights": "E:/GPT-SoVITS/GPT_weights/xxx.ckpt",
  "sovits_weights": "E:/GPT-SoVITS/SoVITS_weights/xxx.pth",
  "ref_audio_path": "E:/GPT-SoVITS/reference_audios/温柔问候.wav",
  "prompt_text": "你好啊，很高兴见到你。",
  "prompt_lang": "zh"
}
```
*总结：语音文件存放于你自己机器本地（或服务器）上的任意物理路径。你需要把实际存放的绝对路径写入上面提到的 MongoDB 的 `digital_persons` 表中即可。*

---

## 三、 MongoDB 数据库 (库与表结构)

系统会自动连接本机的 `mongodb://localhost:27017`，如果集合不存在，当我们第一次写入数据时，**MongoDB 会自动创建库和表**，你**无需手动执行 SQL 语句去建表**。

- **数据库名**：`digital_companion`

**核心 Collection (集合/表) 梳理：**
1. `users`: 用户表（存储账号及密码）
2. `user_profiles`: 用户画象表（存储年龄、职业偏好等分析结果）
3. `digital_persons`: 虚拟人档案表（存储可聊天的虚拟人名称、性格 Prompt、上文提到的语音路径等）
4. `conversations`: 会话记录表（包含最后一条时间以及后台动态长文本压缩的 `summary` 字段）
5. `messages`: 聊天消息流表（系统提取上下文的来源）
6. `memories`: 记忆向量库表（用来做用户偏好提取时的基于大模型的长记忆库）

如果你为了方便体验，想向 `digital_persons` 快速塞一条配置初始数据（用于在首页点出来），可以通过 MongoDB 原生命令或 MongoDB Compass 可视化工具执行这段脚本：

```javascript
use digital_companion;

// 插入一个名叫"小云"的数字人（附带语音参数示例，你可以自行改成你的实际音频路径）
db.digital_persons.insertOne({
  "name": "小云 (知心学姐)",
  "avatar_url": "https://api.dicebear.com/7.x/adventurer/svg?seed=Felix",
  "persona_prompt": "你是一个温柔、善解人意的知心大姐姐。你的语气总是很关心我...",
  "status": "active",
  "created_at": new Date(),
  "tts_config": {
    "gpt_weights": "E:/your_models/xiaoyun.ckpt",
    "sovits_weights": "E:/your_models/xiaoyun.pth",
    "ref_audio_path": "E:/your_audio/xiaoyun_hi.wav",
    "prompt_text": "你好，我是小云！",
    "prompt_lang": "zh"
  }
});
```
