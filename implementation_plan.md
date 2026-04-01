# 数字人陪伴系统 - 全面升级实施方案

## 背景

当前项目已具备：SSE流式对话、记忆提取去重、向量化检索、情感分析等核心功能。本次升级聚焦**安全性、稳定性、智能化和视觉体验**四个维度的全面增强。

## 拟变更清单

---

### 模块一：后端安全与稳定性

#### [MODIFY] [ai_service.py](file:///e:/biyesheji2_backup/backend/app/services/ai_service.py)
- 新增 `summarize_history()` 方法——调用 AI 将长对话压缩为摘要（温度 0.2，专用Prompt）
- 新增输出内容过滤`_filter_output()` ——正则黑名单过滤违禁词
- 流式 [chat_stream()](file:///e:/biyesheji2_backup/backend/app/services/ai_service.py#83-124) 新增：watchdog 机制，当 45s 无 chunk 时主动 yield 错误帧终止连接

#### [MODIFY] [prompt_service.py](file:///e:/biyesheji2_backup/backend/app/services/prompt_service.py)
- 新增 `detect_scene(message, recent_emotion)` 静态方法：关键词规则检测对话场景：
  - `crisis`（情绪危机）：含"不想活""轻生""死了算了""自杀"等
  - `emotional`（情感支持）：含"难过""崩溃""压力""焦虑""孤独"等
  - `career`（职业建议）：含"工作""面试""简历""offer""转行""找工作"等
  - `casual`（普通闲聊）：默认
- 新增四套场景 Prompt 片段：
  - **危机场景**`_CRISIS_PROMPT`：温柔共情 + 强制附加心理援助热线（北京010-82951332，全国4001161117），绝不给出任何否定或批判
  - **情感支持场景**`_EMOTIONAL_PROMPT`：先共情后建议，禁止直接给解决方案
  - **职业建议场景**`_CAREER_PROMPT`：结合行业知识库，给可执行具体建议
  - **闲聊场景**`_CASUAL_PROMPT`：轻松自然，可适当幽默
- 新增 `SAFETY_RULES` 守尾指令（防幻觉：禁止编造事实、禁止武断陈述）
- [build_persona_prompt()](file:///e:/biyesheji2_backup/backend/app/services/prompt_service.py#52-253) 新增 `scene` 和 `history_summary` 参数

#### [MODIFY] [conversation.py](file:///e:/biyesheji2_backup/backend/app/routers/conversation.py)
- 新增用户级并发 Semaphore（`_user_semaphores: dict`，每用户限 2 并发，超出立即返回"请求繁忙"错误）
- [send_message_stream()](file:///e:/biyesheji2_backup/backend/app/routers/conversation.py#341-526) 新增：
  - 场景检测 → 传入 Prompt 生成
  - 消息超过阈值时触发后台摘要（压缩历史 → 存入 `conversations.summary`）
  - 危机场景：流结束额外推送 `{type: "crisis", hotlines: [...]}` 帧
- 新增后台任务 `_update_conversation_summary()` 摘要压缩（调 ai_service.summarize_history）
- 获取历史消息时：若存在 summary 则将其作为 system context 注入，只取最新 8 条原始消息

#### [MODIFY] [config.py](file:///e:/biyesheji2_backup/backend/app/config.py)
- 新增 `max_concurrent_per_user: int = 2`
- 新增 `history_summary_threshold: int = 20`
- 新增 `recent_messages_keep: int = 8`

---

### 模块二：天气查询工具（面试前提醒）

> 仅当用户提到"面试""约好了去""明天去""后天去"等出行关键词时触发

#### [NEW] [weather_service.py](file:///e:/biyesheji2_backup/backend/app/services/weather_service.py)
- 封装 **OpenWeatherMap** 免费 API（Current Weather，60次/分钟，无需信用卡）
- `get_weather(city: str)` → 返回：温度℃、天气描述、降水概率、风速
- 城市名抽取：从用户消息中 NER 提取城市（正则匹配省市名词库，如"北京""上海""广州"等）
- 结果格式化为 Prompt 片段：
  ```
  【天气提醒】明天{city}：{desc}，气温{min}~{max}℃，
  {建议带伞 if 有雨 else 天气晴好}，{建议穿衣层次}
  ```
- 降级策略：API 不可用 / 无法识别城市时，跳过天气注入，不影响正常对话

#### [MODIFY] [config.py](file:///e:/biyesheji2_backup/backend/app/config.py)
- 新增 `weather_api_key: str = ""` （OpenWeatherMap 免费 Key，填入 .env）
- 新增 `weather_api_url: str = "https://api.openweathermap.org/data/2.5/weather"`

#### [MODIFY] [prompt_service.py](file:///e:/biyesheji2_backup/backend/app/services/prompt_service.py)
- [build_persona_prompt()](file:///e:/biyesheji2_backup/backend/app/services/prompt_service.py#52-253) 新增 `weather_info: Optional[str]` 参数
- 天气探针：`detect_interview_trip(message)` 静态方法，检测是否提到面试出行
- 若检测到 → 追加天气提醒区块到 Prompt 末尾

#### [MODIFY] [conversation.py](file:///e:/biyesheji2_backup/backend/app/routers/conversation.py)
- 引入 `_weather_service = WeatherService()`
- 面试场景下，先调 `detect_interview_trip()` → 若触发，异步获取天气 → 注入 Prompt

---

### 模块三：专业面试辅助系统

> 检测到"面试"话题时，动态注入专业面试知识库和对话引导策略

#### [NEW] [interview_service.py](file:///e:/biyesheji2_backup/backend/app/services/interview_service.py)
核心面试知识库（内置，无需外部 API）：

**通用面试知识（各专业适用）**
- 自我介绍 STAR 框架模板
- HR 面试高频 15 题标准答案思路（优缺点、职业规划、离职原因、压力处理等）
- 面试前中后行为准则（提前10分钟到、着装、结束时反问等）

**分专业知识库**（`INTERVIEW_KB: dict`）
```python
{
  "计算机/软件": {
    "技术面重点": ["数据结构", "算法", "系统设计", "项目深问"],
    "高频题": ["手写排序", "LRU缓存", "设计秒杀系统"...],
    "建议": "LeetCode 中等题熟练度 + 项目亮点提炼"
  },
  "金融": { "技术面重点": [...], "高频题": [...] },
  "教育": { ... },
  "市场营销": { ... },
  "产品经理": { ... },
  "医疗": { ... },
  "机械工程": { ... },
  "通用/文科": { ... }
}
```

- `detect_major(memories, message)` → 从用户记忆和对话中推断所学专业
- `get_interview_advice(major, stage)` → 返回该专业的面试 Prompt 片段
  - `stage`: `preparation`（面试前）/ `during`（面试中顾虑）/ `after`（面试后复盘）
- `get_common_questions(major)` → 返回该专业的 TOP 10 面试题列表

#### [MODIFY] [prompt_service.py](file:///e:/biyesheji2_backup/backend/app/services/prompt_service.py)
- 新增 `_INTERVIEW_PROMPT` 场景片段：当 `scene == "interview"` 时注入
  - 包含：STAR法则说明 + 专业知识片段 + 面试阶段专属指导
  - 强制要求 AI 给出具体、可执行的面试准备步骤，而非泛泛而谈
- `detect_scene()` 新增 `interview` 场景检测（`面试`、`笔试`、`约面`、`面经`、`offer`、`HR打电话`等）
- 场景优先级：`crisis > interview > emotional > career > casual`（`interview` 优先于普通 `career`）

#### [MODIFY] [conversation.py](file:///e:/biyesheji2_backup/backend/app/routers/conversation.py)
- 引入 `_interview_service = InterviewService()`
- `interview` 场景下：调用 `detect_major` + `get_interview_advice` → 注入到 Prompt
- 同时并发：若含出行词 → 获取天气 → 一并注入

#### [NEW] 面试提醒 SSE 帧（新增 type）
- 当检测到面试场景，SSE `meta_start` 中额外携带：
  ```json
  {"meta_start": {..., "scene": "interview", "interview_tips": ["提前10分钟到", "带好简历3份", ...]}}
  ```
- 前端 [Chat.vue](file:///e:/biyesheji2_backup/frontend/src/views/Chat.vue) 在 `interview` 场景时：顶部浮现「💼 面试模式」徽章 + 面试小提示条

#### [MODIFY] [Chat.vue](file:///e:/biyesheji2_backup/frontend/src/views/Chat.vue)（面试UI）
- 面试模式徽章：检测到 `scene=interview` 后顶部显示「💼 面试模式已激活」
- 面试 Tips 收纳条：可折叠的 Tips 面板，展示 `interview_tips` 列表
- 天气卡片：当 SSE 中含天气信息时，在 Tips 条内显示天气卡片

---

### 模块四（原模块二）：前端 GSAP 全面重写

> [!IMPORTANT]
> 保留现有所有功能逻辑（发送/接收/TTS/记忆/侧边栏/情感等），仅改视觉与动画层

#### [MODIFY] [style.css](file:///e:/biyesheji2_backup/frontend/src/style.css)
重写为深色玻璃拟态风格设计系统：
- 深色背景（`#0a0a14` → `#0d1b3e` 渐变），品牌紫色/青色系
- 新 CSS 变量（`--glass-bg`、`--glass-border`、`--accent-purple`、`--neon-glow`）
- 引入 Google Fonts（Inter + Noto Sans SC），替换系统默认字体
- 移除旧的浅色变量，全面深色化

#### [MODIFY] [Login.vue](file:///e:/biyesheji2_backup/frontend/src/views/Login.vue)
- 全屏沉浸式登录，背景浮动光斑（CSS keyframe orbs）
- gsap CDN 引入（`<script src="https://cdn.jsdelivr.net/npm/gsap@3/dist/gsap.min.js">`）或 npm install
- GSAP 入场：logo → 表单卡片 → 按钮，stagger 0.15s
- 玻璃拟态表单卡片，输入框聚焦 neon-glow

#### [MODIFY] [Home.vue](file:///e:/biyesheji2_backup/frontend/src/views/Home.vue)
- 欢迎标题：字符拆分逐个入场（JS 拆字符 + gsap.fromTo stagger）
- 数字人卡片：onMounted 后 GSAP stagger 从下→上入场
- 卡片 hover：mousemove 磁力偏移（`gsap.quickTo`）
- 卡片深色玻璃拟态样式，accent 紫色发光边框

#### [MODIFY] [Chat.vue](file:///e:/biyesheji2_backup/frontend/src/views/Chat.vue)
- 每条消息入场：`gsap.from(el, {y:20, opacity:0, duration:0.4})`（利用 Vue `v-motion` 或 `onMounted` watch messages）
- 取消按钮：`typing=true` 时显示「⊘ 取消」，调用 abortStream
- 超时 Toast：30s 定时器，时间到后显示「AI响应较慢，点击重试」+ 自动停止 loading
- 危机帧：SSE `type=crisis` 时展示 CrisisModal
- 输入框流光边框动画（聚焦时 CSS animation）
- 打字loading改为 wave 动效

#### [MODIFY] [api/index.js](file:///e:/biyesheji2_backup/frontend/src/api/index.js)
- [sendMessageStream()](file:///e:/biyesheji2_backup/frontend/src/api/index.js#65-138) 新增 30s 超时机制（`setTimeout + controller.abort()`）
- 新增请求去重（`_isSending` 状态锁，防双击重复发送）
- 新增 `onCrisis(hotlines)` 回调，解析 `type=crisis` 帧
- 响应拦截器：区分网络超时/限流429/服务器500，给出不同 Toast 文本

#### [NEW] [CrisisModal.vue](file:///e:/biyesheji2_backup/frontend/src/components/CrisisModal.vue)
- 危机干预弹窗，温柔文字 + 援助热线卡片（可拨打/复制）
- GSAP scale-in 动画，backdrop blur

---

## 验证计划

### 后端验证（手动）

```powershell
# 1. 启动后端
cd e:\biyesheji2_backup\backend
.\venv_new\Scripts\activate
uvicorn app.main:app --reload --port 8000
```

| 测试内容 | 操作 | 预期结果 |
|---------|-----|---------|
| 限流保护 | 快速连续发 3 条消息 | 第3条收到"请求繁忙"提示 |
| 危机检测 | 发送"我有点不想活了" | SSE 流末尾含 `type:crisis` 帧，前端弹出热线 |
| 历史摘要 | 发满 20 条消息后继续对话 | MongoDB中 conversations 文档出现 summary 字段 |
| 幻觉防护 | 问"某某公司的具体招聘联系方式是什么" | AI回复不编造具体联系方式，给出模糊后加"建议官网查询" |
| 超时保护 | 后端临时断开网络 | 45s后SSE推送 error 帧，前端停止转圈 |
| **天气提醒** | 发送"明天要去北京面试" | AI 回复包含北京天气信息和带伞提醒 |
| **面试模式** | 发送"明天有互联网公司的技术面" | 顶部显示💼徽章，面试 Tips 面板展开 |
| **专业匹配** | 记忆中有"计算机专业"，发送"明天面试" | AI给出数据结构/算法等计算机专项准备建议 |
| **面试阶段** | 面试后发送"刚面试完感觉没发挥好" | AI进入复盘引导模式，帮分析得失 |

### 前端验证（手动）

```powershell
# 启动前端
cd e:\biyesheji2_backup\frontend
npm run dev
```

| 页面 | 验证点 | 预期效果 |
|-----|-------|---------|
| Login | 刷新页面 | Logo→表单→按钮依次入场 |
| Home | 进入主页 | 数字人卡片从下向上 stagger 入场 |
| Home | 悬停卡片 | 卡片轻微跟随鼠标偏移（磁力效果） |
| Chat | 发送消息 | 气泡带 GSAP 入场动画 |
| Chat | 等待回复 | Wave 打字动画（非3点跳动） |
| Chat | 点击取消 | loading 立即停止，消息显示"已取消" |
| Chat | 超时场景 | 30s 后 Toast 提示重试 |
