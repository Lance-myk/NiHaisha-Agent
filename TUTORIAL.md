# 倪海厦中医 Agent — 零基础安装使用教程

## 运行方式

本项目支持两种运行方式：

| 方式 | 命令 | 说明 |
|------|------|------|
| **Web 界面** | `python web_server.py` | 推荐，浏览器访问 http://localhost:8866 |
| **CLI 命令行** | `python agent.py` | 传统命令行交互 |

---

## 第一步：安装 Python

1. 打开浏览器，访问 https://www.python.org/downloads/
2. 点击 "Download Python 3.12.x"（最新的 3.10+ 版本）
3. 下载完成后双击安装
4. **重要**：安装时勾选 "Add Python to PATH"（添加到环境变量）
5. 点击 "Install Now" 完成安装

验证安装：打开命令提示符（按 Win+R，输入 cmd，回车），输入：
```
python --version
```
如果显示版本号（如 Python 3.12.0），说明安装成功。

## 第二步：安装依赖

1. 打开命令提示符（按 Win+R，输入 cmd，回车）
2. 进入项目文件夹：
```
cd C:\Users\Administrator\source\repos\Traditional-Chinese-Medicine-nihaisha
```
3. 安装依赖：
```
pip install openai pywin32
```
等待安装完成。

## 第三步：配置 API Key

### 方式一：使用 LLM_PROVIDER 快捷切换（推荐）

1. 在项目文件夹中，找到 `.env.example` 文件
2. 复制一份，重命名为 `.env`
3. 用记事本打开 `.env`
4. 填入你的 API Key：

```
# 选择模型提供商（取消注释你想用的一行）
LLM_PROVIDER=deepseek   # DeepSeek（推荐，性价比高）
# LLM_PROVIDER=qwen       # 通义千问
# LLM_PROVIDER=glm        # 智谱 GLM
# LLM_PROVIDER=moonshot   # Moonshot
# LLM_PROVIDER=openai     # GPT-4o
# LLM_PROVIDER=ollama     # 本地模型

# 填入你的 API Key
LLM_API_KEY=sk-your-api-key-here
```

5. 保存并关闭

### 获取 API Key

**DeepSeek（推荐）**：
1. 访问 https://platform.deepseek.com/
2. 注册账号
3. 进入 "API Keys" 页面
4. 点击 "创建 API Key"
5. 复制生成的 Key（以 sk- 开头）

**通义千问**：
1. 访问 https://dashscope.aliyun.com/
2. 注册阿里云账号
3. 进入控制台，创建 API Key

**智谱 GLM**：
1. 访问 https://open.bigmodel.cn/
2. 注册账号
3. 获取 API Key

## 第四步：运行

### Web 界面方式（推荐）

1. 双击 **`启动Web.bat`**
2. 浏览器会自动打开 http://localhost:8866
3. 开始对话

或者命令行：
```bash
python web_server.py
```
然后浏览器访问 http://localhost:8866

### CLI 命令行方式

```bash
python agent.py
```

---

## 第五步：开始使用

### Web 界面

打开浏览器访问 http://localhost:8866 后：

1. 在输入框中描述你的症状或问题
2. 点击发送按钮或按 Enter
3. 等待 AI 回复
4. 点击"重置对话"清空历史

### CLI 命令行

运行后，你会看到：

```
============================================================
  倪海厦中医顾问 Agent
  模型: deepseek-chat
  搜索: 开
============================================================
============================================================
  命令: /paste 粘贴 | /slots 信息 | /reset 重置 | /quit 退出
  直接描述你的情况，我会帮你分析。
============================================================
```

直接输入你的症状或问题，Agent 会帮你分析。

### 常用命令（CLI）

- `/quit` — 退出程序
- `/reset` — 重置对话和问诊信息
- `/slots` — 查看当前已采集的问诊信息
- `/paste` — 从剪贴板粘贴内容

## 常见问题

### Q: 显示 "未检测到 API Key"
A: 请检查 .env 文件是否正确创建，LLM_API_KEY 是否填入。

### Q: 显示 "连接失败"
A: 请检查：
1. API Key 是否有效（是否被删除或过期）
2. 网络连接是否正常
3. 模型名称是否正确

### Q: 怎么换模型？
A: 打开 .env 文件，修改 LLM_PROVIDER 的值即可。

### Q: 需要联网吗？
A: 运行 Agent 本身不需要联网，但调用 LLM API 需要联网。如果想完全离线，可以使用 Ollama 本地模型。

### Q: 我的信息会被保存吗？
A: 不会。所有对话仅在本地内存中，关闭程序后即清除。不会上传到任何服务器。

## 安全提醒

1. **本工具仅供学习和日常养生参考，不构成医疗诊断或治疗建议。**
2. **身体不适请务必到正规医疗机构就诊。**
3. **急症、重症请立即就医，不要依赖本工具。**
4. **中药、针灸等治疗手段请勿自行尝试，应在有资质的中医师指导下进行。**

---

如果还有问题，欢迎提 Issue 反馈。
