#!/usr/bin/env python3
"""
倪海厦中医顾问 Agent — 模型无关、支持实时搜索、结构化问诊槽位采集。
Usage:
  python agent.py                    # 交互式对话
  python agent.py --model qwen-plus # 指定模型
  python agent.py --no-search        # 禁用搜索
"""

import os, sys, json, re, urllib.request, urllib.parse, urllib.error
from openai import OpenAI

def read_clipboard():
    """读取 Windows 剪贴板文本。"""
    try:
        import win32clipboard
        win32clipboard.OpenClipboard()
        if win32clipboard.IsClipboardFormatAvailable(13):  # CF_UNICODETEXT
            data = win32clipboard.GetClipboardData(13)
            win32clipboard.CloseClipboard()
            return data
        win32clipboard.CloseClipboard()
    except:
        pass
    return None

# ── 加载 .env 文件 ──────────────────────────────────
def load_dotenv(path):
    """简单的 .env 加载器，不依赖第三方库。"""
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, val = line.partition("=")
                    key, val = key.strip(), val.strip()
                    if key not in os.environ:
                        os.environ[key] = val

HERE = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(HERE, ".env"))

# ── 常见模型预设 ────────────────────────────────────
# 用户只需设置 LLM_PROVIDER，系统自动填充 base_url 和 model
PRESETS = {
    "deepseek":  {"base_url": "https://api.deepseek.com",    "model": "deepseek-chat"},
    "qwen":      {"base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen-plus"},
    "glm":       {"base_url": "https://open.bigmodel.cn/api/paas/v4", "model": "glm-4"},
    "moonshot":  {"base_url": "https://api.moonshot.cn/v1",   "model": "moonshot-v1-8k"},
    "openai":    {"base_url": "https://api.openai.com/v1",    "model": "gpt-4o"},
    "ollama":    {"base_url": "http://localhost:11434/v1",    "model": "qwen2.5:7b"},
}

def resolve_config():
    """解析配置：支持 LLM_PROVIDER 快捷切换 或 手工指定三项。"""
    provider = os.getenv("LLM_PROVIDER", "").lower()
    if provider in PRESETS:
        preset = PRESETS[provider]
        return {
            "base_url": os.getenv("LLM_BASE_URL", preset["base_url"]),
            "api_key": os.getenv("LLM_API_KEY", ""),
            "model": os.getenv("LLM_MODEL", preset["model"]),
            "max_tokens": None,  # 不限制回复长度，让模型自由发挥
            "temperature": 0.7,
            "enable_search": True,
        }
    return {
        "base_url": os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
        "api_key": os.getenv("LLM_API_KEY", ""),
        "model": os.getenv("LLM_MODEL", "deepseek-chat"),
        "max_tokens": None,  # 不限制回复长度，让模型自由发挥
        "temperature": 0.7,
        "enable_search": True,
    }

CONFIG = resolve_config()
SEARCH_ENGINE = "https://www.baidu.com/s?wd="

# ── 加载知识库 ──────────────────────────────────────
KNOWLEDGE_BASE_PATH = os.path.join(HERE, "knowledge_base.md")
SYSTEM_PROMPT_PATH = os.path.join(HERE, "system_prompt.md")

def load_file(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return ""

# ── 槽位管理器 ──────────────────────────────────────
SLOT_TEMPLATE = {
    "chief_complaint": {"label": "主诉", "filled": False, "value": ""},
    "cold_heat":      {"label": "寒热", "filled": False, "value": ""},
    "diet":           {"label": "饮食", "filled": False, "value": ""},
    "bowel_urine":    {"label": "二便", "filled": False, "value": ""},
    "sleep":          {"label": "睡眠", "filled": False, "value": ""},
    "tongue_pulse":   {"label": "舌脉", "filled": False, "value": ""},
    "history":        {"label": "既往", "filled": False, "value": ""},
    "gender_age":     {"label": "性别年龄", "filled": False, "value": ""},
}

# 模块级全局槽位（CLI 模式使用）
SLOTS = {k: dict(v) for k, v in SLOT_TEMPLATE.items()}

def _create_slots():
    """创建新的槽位副本（线程安全）。"""
    return {k: dict(v) for k, v in SLOT_TEMPLATE.items()}

def filled_slots(slots=None):
    target = slots if slots is not None else SLOTS
    return {k: v for k, v in target.items() if v["filled"]}

def missing_slots(slots=None):
    target = slots if slots is not None else SLOTS
    return [k for k, v in target.items() if not v["filled"]]

def slots_summary(slots=None):
    target = slots if slots is not None else SLOTS
    lines = []
    for k, v in target.items():
        status = "[OK]" if v["filled"] else "[ ]"
        lines.append(f"  {status} {v['label']}: {v['value'] if v['filled'] else '(未填)'}")
    return "\n".join(lines)

def extract_slots_from_message(msg, slots=None):
    """从用户消息中自动提取槽位信息。"""
    target = slots if slots is not None else SLOTS
    updated = []
    msg_lower = msg.lower()

    # 主诉检测
    if any(kw in msg for kw in ["不舒服", "难受", "疼", "痛", "症状", "怎么回事", "怎么了"]):
        if not target["chief_complaint"]["filled"]:
            target["chief_complaint"]["value"] = msg[:50]
            target["chief_complaint"]["filled"] = True
            updated.append("主诉→" + msg[:30])

    # 寒热检测
    for kw in ["怕冷", "怕热", "手脚冰凉", "发热", "发烧", "寒热"]:
        if kw in msg and not target["cold_heat"]["filled"]:
            target["cold_heat"]["value"] = kw
            target["cold_heat"]["filled"] = True
            updated.append(f"寒热→{kw}")
            break

    # 饮食检测
    for kw in ["胃口", "吃不下", "吃得多", "口苦", "口干", "口臭", "反酸", "恶心", "呕吐", "饮食"]:
        if kw in msg and not target["diet"]["filled"]:
            target["diet"]["value"] = kw
            target["diet"]["filled"] = True
            updated.append(f"饮食→{kw}")
            break

    # 二便检测
    for kw in ["大便", "小便", "便秘", "腹泻", "尿频", "尿急", "尿痛", "拉肚子", "潭薄"]:
        if kw in msg and not target["bowel_urine"]["filled"]:
            target["bowel_urine"]["value"] = kw
            target["bowel_urine"]["filled"] = True
            updated.append(f"二便→{kw}")
            break

    # 睡眠检测
    for kw in ["失眠", "睡不着", "多梦", "易醒", "嗜睡", "困倦", "睡眠"]:
        if kw in msg and not target["sleep"]["filled"]:
            target["sleep"]["value"] = kw
            target["sleep"]["filled"] = True
            updated.append(f"睡眠→{kw}")
            break

    # 舌脉检测
    for kw in ["舌苔", "舌", "脉", "脉象", "舌红", "舌滤", "舌白", "舌黄", "脉细", "脉弦"]:
        if kw in msg and not target["tongue_pulse"]["filled"]:
            target["tongue_pulse"]["value"] = kw
            target["tongue_pulse"]["filled"] = True
            updated.append(f"舌脉→{kw}")
            break

    # 既往检测
    for kw in ["病史", "慢性病", "高血压", "糖尿病", "心脏病", "过敏", "手术", "住院", "吃药"]:
        if kw in msg and not target["history"]["filled"]:
            target["history"]["value"] = kw
            target["history"]["filled"] = True
            updated.append(f"既往→{kw}")
            break

    # 性别年龄检测
    for kw in ["岁", "男", "女", "年龄", "多大"]:
        if kw in msg and not target["gender_age"]["filled"]:
            target["gender_age"]["value"] = msg[:30]
            target["gender_age"]["filled"] = True
            updated.append(f"性别年龄→{msg[:20]}")
            break

    return updated

def is_consultation_intent(msg):
    """判断用户是否有中医咨询意图。"""
    keywords = [
        "不舒服", "难受", "疼", "痛", "症状", "怎么回事", "怎么了",
        "中医", "中药", "针灸", "艾灸", "调理", "养生", "体质",
        "失眠", "便秘", "腹泻", "头痛", "头晕", "恶心", "呕吐",
        "胃", "肝", "脾", "肺", "肾", "心", "胆", "经络", "穴位",
        "寒", "热", "虚", "实", "湿", "痰", "瘀", "气血", "阴阳",
        "舌苔", "脉", "把脉", "问诊", "辨证", "方子", "方剂",
    ]
    return any(kw in msg for kw in keywords)

# ── 搜索功能 ─────────────────────────────────────────
def web_search(query, max_results=3):
    """搜索并获取网页内容。先用百度搜索找URL，再抓取页面文字。"""
    results = []
    try:
        # Step 1: 百度搜索获取结果链接
        url = SEARCH_ENGINE + urllib.parse.quote(query)
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        # Step 2: 提取搜索结果URL（尝试多种匹配模式）
        urls = re.findall(r'href="(https?://[^"]+)"', html)
        # 过滤掉百度自己的链接，保留真实网站
        valid_urls = [u for u in urls if 'baidu.com' not in u and len(u) > 30][:max_results]

        # Step 3: 抓取每个结果页面的文字内容
        for target_url in valid_urls:
            try:
                page_req = urllib.request.Request(target_url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                })
                with urllib.request.urlopen(page_req, timeout=8) as page_resp:
                    page_html = page_resp.read().decode("utf-8", errors="ignore")
                # 去掉所有标签，提取可见文字
                clean = re.sub(r'<script[^>]*>.*?</script>', '', page_html, flags=re.DOTALL)
                clean = re.sub(r'<style[^>]*>.*?</style>', '', clean, flags=re.DOTALL)
                clean = re.sub(r'<[^>]+>', ' ', clean)
                clean = re.sub(r'\s+', ' ', clean).strip()
                # 取有效内容（100-500字）
                if len(clean) > 100:
                    results.append(clean[:500] + "...")
            except:
                continue

        if not results:
            # Step 4: 降级——只取百度摘要
            snippets = re.findall(r'<span class="content-right_[^"]*">(.*?)</span>', html)
            for s in snippets[:max_results]:
                clean = re.sub(r'<[^>]+>', '', s).strip()
                if len(clean) > 20:
                    results.append(clean)

        return results if results else ["(搜索无结果，建议手动查询官方渠道)"]
    except Exception as e:
        return [f"(搜索暂时不可用: {e})"]

def should_search(msg):
    """判断是否需要联网搜索——更积极触发。"""
    triggers = [
        "最新", "最近", "现在", "2026", "2025",
        "研究", "论文", "临床", "数据", "统计",
        "治愈率", "有效率", "副作用", "禁忌", "注意事项",
        "医院", "医生", "专家", "指南", "标准",
        "多少钱", "价格", "费用", "医保",
    ]
    return any(t in msg for t in triggers)

# ── LLM 对话 ─────────────────────────────────────────
def cleanup_format(text):
    """去掉 AI 模型可能会漏的 Markdown 格式，确保输出像真人聊天。"""
    if not text:
        return text
    # 去掉 **粗体**
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    # 去掉 ### 标题
    text = re.sub(r'^#{1,6}\s*', '', text, flags=re.MULTILINE)
    # 去掉行首 - 列表标记
    text = re.sub(r'^\s*[-*]\s+', '', text, flags=re.MULTILINE)
    # 去掉行首数字编号 1. 2. 等
    text = re.sub(r'^\s*\d+[\.\、]\s*', '', text, flags=re.MULTILINE)
    return text.strip()

class TCMAdvisor:
    def __init__(self):
        self.client = OpenAI(base_url=CONFIG["base_url"], api_key=CONFIG["api_key"])
        self.knowledge_base = load_file(KNOWLEDGE_BASE_PATH)
        self.system_prompt = load_file(SYSTEM_PROMPT_PATH)
        self.conversation = []
        self.slots = _create_slots()

    def _build_system_message(self):
        """构建系统消息，包含 system prompt + 知识库摘要 + 当前槽位状态。"""
        # 加载完整知识库，不做截断
        kb = self.knowledge_base if self.knowledge_base else ""
        kb_summary = kb  # 全量加载，不限制
        slots_status = slots_summary(self.slots)
        search_note = ""
        if CONFIG["enable_search"]:
            search_note = "\n\n【联网搜索已启用。遇到最新研究数据、临床指南、药物信息等问题时，请在回答中说明需要搜索最新信息，或使用搜索工具查询。】"

        full_system = f"""{self.system_prompt}

{search_note}

【知识库参考】
{kb_summary}

【当前用户信息采集状态】
{slots_status}

请在回答时：
1. 如果用户信息不全，追问缺失的槽位（用自然的方式，不要像填表）。
2. 如果信息已经足够（至少主诉+寒热+二便+睡眠），给出辨证分析和调理建议。
3. 遇到需要最新数据时，提示用户"建议查XX官方渠道"，或主动搜索。
4. 保持直爽、接地气的风格。
5. 严格遵守安全边界，急症/重症必须建议就医。"""
        return full_system

    def _prepare_messages(self, user_msg):
        """准备消息（槽位提取 + 搜索 + 消息构建），供 chat 和 chat_stream 复用。"""
        # 检查意图
        if is_consultation_intent(user_msg):
            updates = extract_slots_from_message(user_msg, self.slots)
        else:
            updates = []

        # 构建消息
        system_msg = self._build_system_message()
        messages = [{"role": "system", "content": system_msg}]
        # 添加历史（最近10轮=20条消息）
        for h in self.conversation[-20:]:
            messages.append(h)
        messages.append({"role": "user", "content": user_msg})

        # 如果有槽位更新，追加提示
        if updates:
            hint = f"(系统自动识别到: {', '.join(updates)}。请在回复中确认并追问缺失信息。)"
            messages.append({"role": "system", "content": hint})

        # 搜索（更积极 + 真实数据）
        if CONFIG["enable_search"] and should_search(user_msg):
            search_query = user_msg[:100]
            search_results = web_search(search_query)
            if search_results:
                search_hint = f"【搜索结果】\n" + "\n".join(
                    f"· {r}" for r in search_results[:3]
                )
                messages.append({"role": "system", "content": search_hint})

        return messages, updates

    def chat(self, user_msg):
        """处理一轮对话。返回 assistant 的回复。"""
        messages, updates = self._prepare_messages(user_msg)

        # 调用 LLM
        try:
            kwargs = dict(
                model=CONFIG["model"],
                messages=messages,
                temperature=CONFIG["temperature"],
            )
            if CONFIG["max_tokens"] is not None:
                kwargs["max_tokens"] = CONFIG["max_tokens"]
            resp = self.client.chat.completions.create(**kwargs)
            reply = resp.choices[0].message.content
        except Exception as e:
            reply = f"出错了：{e}\n请检查 API 配置（base_url, api_key, model 是否正确）。"

        # 清理格式：去掉模型不听 prompt 时残留的 markdown
        reply = cleanup_format(reply)

        # 保存对话历史
        self.conversation.append({"role": "user", "content": user_msg})
        self.conversation.append({"role": "assistant", "content": reply})

        return reply

    def chat_stream(self, user_msg):
        """流式处理一轮对话。逐 token yield，最后返回完整回复。"""
        messages, updates = self._prepare_messages(user_msg)
        full_reply = ""

        # 调用 LLM（流式）
        try:
            kwargs = dict(
                model=CONFIG["model"],
                messages=messages,
                temperature=CONFIG["temperature"],
                stream=True,
            )
            if CONFIG["max_tokens"] is not None:
                kwargs["max_tokens"] = CONFIG["max_tokens"]
            for chunk in self.client.chat.completions.create(**kwargs):
                token = chunk.choices[0].delta.content or ""
                if token:
                    full_reply += token
                    yield token
        except Exception as e:
            error_msg = f"出错了：{e}\n请检查 API 配置（base_url, api_key, model 是否正确）。"
            yield error_msg
            full_reply = error_msg

        # 清理格式
        full_reply = cleanup_format(full_reply)

        # 保存对话历史（用清理后的完整回复）
        self.conversation.append({"role": "user", "content": user_msg})
        self.conversation.append({"role": "assistant", "content": full_reply})

    def reset(self):
        """重置对话和槽位。"""
        self.conversation = []
        self.slots = _create_slots()

# ── CLI 界面 ─────────────────────────────────────────
def test_connection():
    """测试 API 连接是否正常。"""
    try:
        client = OpenAI(base_url=CONFIG["base_url"], api_key=CONFIG["api_key"])
        resp = client.chat.completions.create(
            model=CONFIG["model"],
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=5,
        )
        return True, resp.choices[0].message.content
    except Exception as e:
        return False, str(e)

def main():
    import textwrap

    print("=" * 60)
    print("  倪海厦中医顾问 Agent")
    print(f"  模型: {CONFIG['model']}")
    print(f"  搜索: {'开' if CONFIG['enable_search'] else '关'}")
    print("=" * 60)

    if not CONFIG["api_key"]:
        print("\n❌ 未检测到 API Key！")
        print("   请复制 .env.example 为 .env 并填入你的 API Key。")
        print("   或者设置环境变量 LLM_API_KEY=你的key")
        print()
        print("   快速开始（任选一种）：")
        print("   · DeepSeek:  set LLM_PROVIDER=deepseek && set LLM_API_KEY=sk-xxx")
        print("   · 通义千问:  set LLM_PROVIDER=qwen && set LLM_API_KEY=sk-xxx")
        print("   · 智谱GLM:   set LLM_PROVIDER=glm && set LLM_API_KEY=xxx")
        input("\n   按回车退出...")
        return

    # 测试连接
    print("  正在测试 API 连接...", end=" ", flush=True)
    ok, msg = test_connection()
    if ok:
        print("[OK] 连接成功")
    else:
        print(f"[X] 连接失败: {msg[:120]}")
        print("\n   请检查 .env 中的 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL 是否正确。")
        print("   常见问题：")
        print("   · API Key 是否有效？")
        print("   · Base URL 是否需要加 /v1？")
        print("   · 模型名是否与 API 提供商匹配？")
        input("\n   按回车退出...")
        return

    print("=" * 60)
    print("  命令: /paste 粘贴 | /slots 信息 | /reset 重置 | /quit 退出")
    print("  直接描述你的情况，我会帮你分析。")
    print("=" * 60)
    print()

    advisor = TCMAdvisor()

    while True:
        try:
            user_input = input("\n[You] 你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        if not user_input:
            continue

        if user_input == "/quit":
            print("再见！")
            break
        elif user_input == "/reset":
            advisor.reset()
            print("[OK] 已重置对话和信息采集")
            continue
        elif user_input == "/slots":
            print(slots_summary())
            continue
        elif user_input == "/paste":
            cb = read_clipboard()
            if cb and cb.strip():
                user_input = " ".join(cb.strip().split("\n"))
                print(f"📋 剪贴板已读取 ({len(user_input)}字)")
                print(f"📋 内容: {user_input[:100]}...")
            else:
                print("📋 剪贴板为空或无法读取")
                continue

        print("\n🤖 顾问: ", end="", flush=True)
        reply = advisor.chat(user_input)
        print(reply)

if __name__ == "__main__":
    main()
