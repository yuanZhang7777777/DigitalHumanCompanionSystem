# 1Panel 部署数字人项目详细教程 (含 GPT-SoVITS API)

本教程将指引您如何在云服务器上通过 **1Panel** 面板部署本项目，并实现 **GPT-SoVITS 语音推理引擎** 的云端 API 化运行。

## 一、 准备工作
1. **主服务器**: 阿里云/腾讯云等（建议 Ubuntu 22.04，2核4G+，无需显卡，用于跑前端后端和数据库）。
2. **显卡服务器** (仅需语音功能时): 如果主服务器没显卡，建议租用 **AutoDL** 或类似的 GPU 云（最低建议 RTX 3060 12G）。
3. **环境**: 确保主服务器已通过 `curl` 安装 1Panel。

---

## 二、 代码打包与上传
不要直接在服务器上 `git clone`，因为环境配置（如 .env）和一些本地资源需要手动处理。

1. **本地打包**:
   - 在您的电脑上，进入 `biyesheji2` 文件夹。
   - **删除** (或不选入压缩包): `node_modules` (前端)、`venv` (后端虚拟环境)、`.git`。
   - 将 `backend`、`frontend`、`docs` 文件夹及根目录文件压缩为 `project.zip`。
2. **上传到服务器**:
   - 登录 1Panel -> 进入“文件”菜单。
   - 建议路径：`/opt/1panel/apps/my-project`。
   - 点击“上传”，选择 `project.zip`，上传后右键“解压”。

---

## 三、 数据库与应用环境 (1Panel 应用商店)
在 1Panel 应用商店安装：
1. **MongoDB**: 安装后创建一个名为 `digital_human` 的数据库，并开启“外部访问”(需在安全组放行 27017，仅限调试，线上建议内网访问)。
2. **OpenResty**: 用于托管前端和 API 转发。

---

## 四、 部署 GPT-SoVITS API (关键步骤)
由于 GPT-SoVITS 依赖显卡，推荐在 **AutoDL** 或带 GPU 的服务器上部署其 API 模式。

### 1. 部署推理服务
如果您使用 [GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS) 官方代码：
1. 在显卡服务器执行：
   ```bash
   python api.py -dr "您的权重路径/weights_gpt.ckpt" -ds "您的权重路径/weights_sovits.pth" -a "0.0.0.0" -p 9880
   ```
2. **防火墙**: 放行 `9880` 端口。
3. **获取 API 地址**: 假设显卡服务器 IP 为 `1.2.3.4`，则 API 地址为 `http://1.2.3.4:9880`。

---

## 五、 后端部署 (FastAPI + Docker)
1. **创建环境变量**: 在 `/backend` 目录下创建 `.env` 文件：
   ```env
   # 数据库
   MONGODB_URL=mongodb://root:您的密码@127.0.0.1:27017/digital_human?authSource=admin
   
   # 语音引擎 (填写您刚才部署的显卡服务器 API 地址)
   TTS_API_URL=http://1.2.3.4:9880
   
   # 阿里云配置
   AI_API_KEY=xxxx
   OSS_ACCESS_KEY_ID=xxxx
   OSS_ACCESS_KEY_SECRET=xxxx
   OSS_ENDPOINT=oss-cn-beijing.aliyuncs.com
   OSS_BUCKET_NAME=xxxx
   
   # 安全
   JWT_SECRET=随便写个长字符串
   ```
2. **Docker 编排**: 在 1Panel “容器” -> “编排” 中点击“创建编排”：
   - **名称**: `digital-human-backend`
   - **内容**:
     ```yaml
     version: '3'
     services:
       app:
         build: 
           context: ./backend
           dockerfile: Dockerfile
         ports:
           - "8000:8000"
         restart: always
     ```
   *(注意：请确保 backend 目录下已有 Dockerfile，如果没有，可参考项目根目录的样例)*

---

## 六、 前端部署 (静态托管)
1. **本地构建**:
   - 在本地 `frontend` 目录运行 `npm run build`。
   - 生成的 `dist` 文件夹压缩上传到服务器 `/www/sites/yourdomain/index`。
2. **1Panel 网站配置**:
   - 点击“网站” -> “创建网站” -> “静态网站”。
   - **域名**: 您的服务器 IP 或自有域名。
   - **核心配置 (反向代理)**:
     在网站设置的“配置文件”中，在 `server` 块内加入：
     ```nginx
     # 反向代理后端 API
     location /api/ {
         proxy_pass http://127.0.0.1:8000/api/;
         proxy_set_header Host $host;
         proxy_set_header X-Real-IP $remote_addr;
     }
     ```

---

## 七、 常见问题
1. **跨域错误**: 确保 OSS 的 CORS 设置允许您的域名/IP 访问。
2. **语音不响**: 检查后端 `.env` 里的 `TTS_API_URL` 是否能被后端容器访问到（若在同一台机器，用 `http://host.docker.internal:9880`）。
3. **502 Bad Gateway**: 通常是后端 Docker 没启动成功，检查 1Panel 容器日志。

> [!TIP]
> **关于成本**: 显卡服务器建议平时用 AutoDL 关机（按量计费），真正演示时开启 API 即可。
