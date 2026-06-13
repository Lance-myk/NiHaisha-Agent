#!/usr/bin/env python3
"""
倪海厦中医顾问 Web UI Server
基于 Python 内置 http.server，零额外依赖
端口: 8866
Usage:
  python web_server.py
"""

import os, sys, json, re, uuid, threading, logging
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import urlparse

# ── 日志配置 ──────────────────────────────────────────
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web_server.log')
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    encoding='utf-8'
)
logger = logging.getLogger(__name__)

# 导入 agent 逻辑
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agent import TCMAdvisor, CONFIG, SLOTS, slots_summary

# ── Session 管理 ──────────────────────────────────────
SESSIONS = {}
SESSION_LOCK = threading.Lock()

# ── 点赞数据（持久化到文件）───────────────────────────
LIKE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'like_count.json')
LIKE_LOCK = threading.Lock()

def _load_like_total():
    """从文件加载点赞总数，默认88。"""
    if os.path.exists(LIKE_FILE):
        try:
            with open(LIKE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('total', 88)
        except (json.JSONDecodeError, IOError):
            pass
    return 88

def _save_like_total(total):
    """保存点赞总数到文件。"""
    try:
        with open(LIKE_FILE, 'w', encoding='utf-8') as f:
            json.dump({'total': total}, f, ensure_ascii=False)
    except IOError:
        pass

def get_or_create_session(session_id):
    """获取或创建会话。"""
    with SESSION_LOCK:
        if session_id not in SESSIONS:
            SESSIONS[session_id] = TCMAdvisor()
        return SESSIONS[session_id]

def reset_session(session_id):
    """重置会话。"""
    with SESSION_LOCK:
        if session_id in SESSIONS:
            SESSIONS[session_id].reset()
            del SESSIONS[session_id]

# ── HTML 页面 ────────────────────────────────────────
HTML_PAGE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>倪海厦中医顾问</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        .container {
            width: 100%;
            max-width: 900px;
            height: 95vh;
            background: #fff;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        /* 顶部标题栏 */
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px 25px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-shrink: 0;
        }
        .header-left {
            display: flex;
            align-items: center;
            gap: 15px;
        }
        .header h1 {
            font-size: 20px;
            font-weight: 600;
        }
        .header .status {
            font-size: 12px;
            opacity: 0.9;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #4ade80;
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .header-actions {
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .like-btn {
            display: flex;
            align-items: center;
            gap: 4px;
            padding: 6px 12px;
            border-radius: 20px;
            background: rgba(255,255,255,0.2);
            border: 1px solid rgba(255,255,255,0.3);
            color: white;
            font-size: 13px;
            cursor: pointer;
            transition: all 0.2s;
            user-select: none;
        }
        .like-btn:hover {
            background: rgba(255,255,255,0.3);
        }
        .like-btn.liked {
            background: #ff6b6b;
            border-color: #ff6b6b;
        }
        .donate-btn {
            display: flex;
            align-items: center;
            gap: 4px;
            padding: 6px 12px;
            border-radius: 20px;
            background: rgba(255,255,255,0.2);
            border: 1px solid rgba(255,255,255,0.3);
            color: white;
            font-size: 13px;
            cursor: pointer;
            transition: all 0.2s;
            user-select: none;
        }
        .donate-btn:hover {
            background: rgba(255,255,255,0.3);
        }
        /* 打赏弹窗 */
        .modal-overlay {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.5);
            z-index: 1000;
            justify-content: center;
            align-items: center;
        }
        .modal-overlay.active {
            display: flex;
        }
        .modal-content {
            background: white;
            border-radius: 16px;
            padding: 24px;
            max-width: 320px;
            text-align: center;
            animation: modalFadeIn 0.3s ease;
        }
        @keyframes modalFadeIn {
            from { opacity: 0; transform: scale(0.9); }
            to { opacity: 1; transform: scale(1); }
        }
        .modal-content h3 {
            margin-bottom: 16px;
            color: #374151;
        }
        .modal-content img {
            width: 200px;
            height: 200px;
            border-radius: 8px;
            margin-bottom: 12px;
        }
        .modal-content p {
            color: #6b7280;
            font-size: 14px;
            margin-bottom: 16px;
        }
        .modal-close {
            padding: 8px 24px;
            border-radius: 20px;
            border: none;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            font-size: 14px;
            cursor: pointer;
        }
        /* 消息区域 */
        .messages {
            flex: 1;
            overflow-y: auto;
            padding: 20px;
            background: #f8f9fa;
        }
        .message {
            display: flex;
            margin-bottom: 16px;
            animation: fadeIn 0.3s ease;
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .message.user { justify-content: flex-end; }
        .message.assistant { justify-content: flex-start; }
        .message-bubble {
            max-width: 75%;
            padding: 12px 16px;
            border-radius: 18px;
            font-size: 14px;
            line-height: 1.6;
            word-wrap: break-word;
            white-space: pre-wrap;
        }
        .message.user .message-bubble {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-bottom-right-radius: 4px;
        }
        .message.assistant .message-bubble {
            background: white;
            color: #333;
            border: 1px solid #e5e7eb;
            border-bottom-left-radius: 4px;
        }
        .message-avatar {
            width: 36px;
            height: 36px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
            margin: 0 10px;
            flex-shrink: 0;
        }
        .message.user .message-avatar {
            background: #e0e7ff;
            order: 1;
        }
        .message.assistant .message-avatar {
            background: #fef3c7;
            order: 0;
        }
        /* 欢迎消息 */
        .welcome {
            text-align: center;
            padding: 40px 20px;
            color: #6b7280;
        }
        .welcome h2 {
            font-size: 24px;
            margin-bottom: 12px;
            color: #374151;
        }
        .welcome p {
            font-size: 14px;
            line-height: 1.8;
            max-width: 500px;
            margin: 0 auto;
        }
        .welcome .tips {
            margin-top: 24px;
            padding: 16px;
            background: white;
            border-radius: 12px;
            display: inline-block;
            text-align: left;
        }
        .welcome .tips h3 {
            font-size: 14px;
            color: #374151;
            margin-bottom: 8px;
        }
        .welcome .tips ul {
            list-style: none;
            font-size: 13px;
        }
        .welcome .tips li {
            padding: 4px 0;
            color: #6b7280;
        }
        .welcome .tips li::before {
            content: "• ";
            color: #667eea;
            font-weight: bold;
        }
        /* 输入区域 */
        .input-area {
            padding: 15px 20px;
            background: white;
            border-top: 1px solid #e5e7eb;
            flex-shrink: 0;
        }
        .input-wrapper {
            display: flex;
            gap: 10px;
            align-items: flex-end;
        }
        .input-box {
            flex: 1;
            min-height: 44px;
            max-height: 120px;
            padding: 10px 16px;
            border: 2px solid #e5e7eb;
            border-radius: 22px;
            font-size: 14px;
            line-height: 1.5;
            resize: none;
            outline: none;
            transition: border-color 0.2s;
            font-family: inherit;
        }
        .input-box:focus {
            border-color: #667eea;
        }
        .send-btn {
            width: 44px;
            height: 44px;
            border-radius: 50%;
            border: none;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            font-size: 18px;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
        }
        .send-btn:hover {
            transform: scale(1.05);
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
        }
        .send-btn:active {
            transform: scale(0.95);
        }
        .send-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }
        /* 快捷命令 */
        .quick-commands {
            display: flex;
            gap: 8px;
            margin-top: 10px;
            flex-wrap: wrap;
        }
        .quick-cmd {
            padding: 4px 12px;
            border: 1px solid #e5e7eb;
            border-radius: 16px;
            background: #f9fafb;
            color: #6b7280;
            font-size: 12px;
            cursor: pointer;
            transition: all 0.2s;
        }
        .quick-cmd:hover {
            background: #667eea;
            color: white;
            border-color: #667eea;
        }
        /* 加载动画 */
        .typing-indicator {
            display: none;
            padding: 12px 16px;
            background: white;
            border-radius: 18px;
            border: 1px solid #e5e7eb;
            border-bottom-left-radius: 4px;
            width: fit-content;
        }
        .typing-indicator.active {
            display: flex;
            align-items: center;
            gap: 4px;
        }
        .typing-dot {
            width: 6px;
            height: 6px;
            background: #9ca3af;
            border-radius: 50%;
            animation: typingBounce 1.4s infinite ease-in-out;
        }
        .typing-dot:nth-child(2) { animation-delay: 0.2s; }
        .typing-dot:nth-child(3) { animation-delay: 0.4s; }
        @keyframes typingBounce {
            0%, 80%, 100% { transform: translateY(0); }
            40% { transform: translateY(-6px); }
        }
        @keyframes thinkingBounce {
            0%, 80%, 100% { transform: translateY(0); }
            40% { transform: translateY(-4px); }
        }
        .thinking-dot {
            display: inline-block;
            width: 6px;
            height: 6px;
            background: #9ca3af;
            border-radius: 50%;
            animation: thinkingBounce 1.4s infinite ease-in-out;
        }
        .thinking-dot:nth-child(2) { animation-delay: 0.2s; }
        .thinking-dot:nth-child(3) { animation-delay: 0.4s; }
        /* 滚动条 */
        .messages::-webkit-scrollbar {
            width: 6px;
        }
        .messages::-webkit-scrollbar-track {
            background: transparent;
        }
        .messages::-webkit-scrollbar-thumb {
            background: #d1d5db;
            border-radius: 3px;
        }
        .messages::-webkit-scrollbar-thumb:hover {
            background: #9ca3af;
        }
        /* 响应式 */
        @media (max-width: 640px) {
            .container {
                height: 100vh;
                border-radius: 0;
            }
            .header h1 {
                font-size: 16px;
            }
            .message-bubble {
                max-width: 85%;
                font-size: 13px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="header-left">
                <h1>🌿 倪海厦中医顾问</h1>
                <div class="status">
                    <span class="status-dot"></span>
                    <span id="model-name">加载中...</span>
                </div>
            </div>
            <div class="header-actions">
                <div class="like-btn" id="like-btn" onclick="toggleLike()">
                    <span>👍</span>
                    <span id="like-count">0</span>
                </div>
                <div class="donate-btn" onclick="showDonate()">
                    <span>🎁</span>
                    <span>打赏</span>
                </div>
            </div>
        </div>

        <!-- 打赏弹窗 -->
        <div class="modal-overlay" id="donate-modal" onclick="hideDonate(event)">
            <div class="modal-content">
                <h3>☕ 请作者喝杯咖啡</h3>
                <img src="/img/1.png" alt="赞赏码" onerror="this.style.display='none'">
                <p>感谢您的支持，我会继续完善这个项目！</p>
                <button class="modal-close" onclick="hideDonate()">关闭</button>
            </div>
        </div>

        <div class="messages" id="messages">
            <div class="welcome" id="welcome">
                <h2>👋 欢迎来到倪海厦中医顾问</h2>
                <p>基于倪海厦大师人纪系列知识，为您提供中医养生咨询。</p>
                <div class="tips">
                    <h3>📖 关于倪海厦大师</h3>
                    <p style="font-size: 13px; line-height: 1.8; color: #6b7280; margin-top: 8px;">
                        倪海厦（1954—2012），祖籍浙江瑞安、生于台湾台北，美籍知名经方中医师、五术学者，被众多学习者尊称为"倪师"。他早年自学中医成名，从军期间行医救人，后移民美国，创办汉唐中医诊所与汉唐中医学院，曾任美国佛罗里达州针灸委员会副主席，大力推动中医针灸在美国合法化与国际化传播。其一生深耕张仲景经方体系，擅长疑难重症调理，留下《人纪》《天纪》等经典教学著作与视频，以通俗直白的方式解读中医古籍，惠及无数零基础中医爱好者，是近代民间影响力最大的中医经方传播者之一。
                    </p>
                </div>
                <div class="tips" style="margin-top: 16px;">
                    <h3>💡 您可以这样提问：</h3>
                    <ul>
                        <li>"我最近失眠，晚上睡不着，白天没精神"</li>
                        <li>"我胃不好，吃点凉的就难受，大便不成形"</li>
                        <li>"我手脚冰凉，容易疲劳，这是怎么回事？"</li>
                        <li>"我痛经，小腹冷痛，月经有血块"</li>
                    </ul>
                </div>
            </div>
        </div>

        <div class="input-area">
            <div class="input-wrapper">
                <textarea
                    class="input-box"
                    id="input-box"
                    placeholder="描述您的症状或问题..."
                    rows="1"
                    onkeydown="handleKeyDown(event)"
                ></textarea>
                <button class="send-btn" id="send-btn" onclick="sendMessage()">
                    ➤
                </button>
            </div>
            <div class="quick-commands">
                <span class="quick-cmd" onclick="resetDialog()">🔄 重置对话</span>
            </div>
        </div>
    </div>

    <script>
        const messagesEl = document.getElementById('messages');
        const inputBox = document.getElementById('input-box');
        const sendBtn = document.getElementById('send-btn');
        const welcomeEl = document.getElementById('welcome');

        // 从 localStorage 恢复对话历史
        let conversationHistory = JSON.parse(localStorage.getItem('tcm_conversation') || '[]');
        let sessionId = localStorage.getItem('tcm_session_id') || generateSessionId();
        localStorage.setItem('tcm_session_id', sessionId);

        // 生成会话 ID
        function generateSessionId() {
            return 'sess_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
        }

        // 加载状态
        fetch('/api/status')
            .then(r => r.json())
            .then(data => {
                document.getElementById('model-name').textContent = data.model;
            })
            .catch(() => {
                document.getElementById('model-name').textContent = '未连接';
            });

        // 恢复历史消息
        if (conversationHistory.length > 0) {
            welcomeEl.style.display = 'none';
            conversationHistory.forEach(msg => {
                appendMessage(msg.role, msg.content, false);
            });
        }

        // 自动调整输入框高度
        inputBox.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = Math.min(this.scrollHeight, 120) + 'px';
        });

        function handleKeyDown(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        }

        function appendMessage(role, content, save = true) {
            if (save) {
                conversationHistory.push({ role, content });
                localStorage.setItem('tcm_conversation', JSON.stringify(conversationHistory));
            }

            if (welcomeEl.style.display !== 'none') {
                welcomeEl.style.display = 'none';
            }

            const msgDiv = document.createElement('div');
            msgDiv.className = `message ${role}`;

            const avatar = role === 'user' ? '👤' : '🤖';
            const bubble = document.createElement('div');
            bubble.className = 'message-bubble';
            bubble.textContent = content;

            const avatarDiv = document.createElement('div');
            avatarDiv.className = 'message-avatar';
            avatarDiv.textContent = avatar;

            if (role === 'user') {
                msgDiv.appendChild(bubble);
                msgDiv.appendChild(avatarDiv);
            } else {
                msgDiv.appendChild(avatarDiv);
                msgDiv.appendChild(bubble);
            }

            messagesEl.appendChild(msgDiv);
            scrollToBottom();
        }

        function appendStreamingMessage() {
            if (welcomeEl.style.display !== 'none') {
                welcomeEl.style.display = 'none';
            }

            const msgDiv = document.createElement('div');
            msgDiv.className = 'message assistant';
            msgDiv.id = 'streaming-message';

            const avatarDiv = document.createElement('div');
            avatarDiv.className = 'message-avatar';
            avatarDiv.textContent = '🤖';

            const bubble = document.createElement('div');
            bubble.className = 'message-bubble';
            bubble.id = 'streaming-bubble';
            bubble.textContent = '';

            msgDiv.appendChild(avatarDiv);
            msgDiv.appendChild(bubble);
            messagesEl.appendChild(msgDiv);
            scrollToBottom();

            return bubble;
        }

        function showThinking() {
            if (welcomeEl.style.display !== 'none') {
                welcomeEl.style.display = 'none';
            }

            const msgDiv = document.createElement('div');
            msgDiv.className = 'message assistant';
            msgDiv.id = 'thinking-message';

            const avatarDiv = document.createElement('div');
            avatarDiv.className = 'message-avatar';
            avatarDiv.textContent = '🤖';

            const bubble = document.createElement('div');
            bubble.className = 'message-bubble';
            bubble.style.display = 'flex';
            bubble.style.alignItems = 'center';
            bubble.style.gap = '8px';
            bubble.innerHTML = `
                <span style="color:#6b7280;font-size:13px;">思考中</span>
                <span class="thinking-dot"></span>
                <span class="thinking-dot"></span>
                <span class="thinking-dot"></span>
            `;

            msgDiv.appendChild(avatarDiv);
            msgDiv.appendChild(bubble);
            messagesEl.appendChild(msgDiv);
            scrollToBottom();

            return msgDiv;
        }

        function hideThinking(thinkingEl) {
            if (thinkingEl && thinkingEl.parentNode) {
                thinkingEl.parentNode.removeChild(thinkingEl);
            }
        }

        function scrollToBottom() {
            messagesEl.scrollTop = messagesEl.scrollHeight;
        }

        let abortController = null;

        async function sendMessage() {
            const text = inputBox.value.trim();
            if (!text) return;

            // 取消之前的请求
            if (abortController) {
                abortController.abort();
            }
            abortController = new AbortController();

            // 禁用输入
            inputBox.disabled = true;
            sendBtn.disabled = true;
            inputBox.value = '';
            inputBox.style.height = 'auto';

            appendMessage('user', text);

            // 显示"思考中"动画
            const thinkingBubble = showThinking();
            let fullText = '';
            let hasResponse = false;

            // 统一的输入框恢复函数
            function restoreInput() {
                inputBox.disabled = false;
                sendBtn.disabled = false;
                inputBox.style.height = 'auto';
                inputBox.focus();
                abortController = null;
                console.log('[DEBUG] Input restored at', new Date().toISOString());
            }

            try {
                console.log('[DEBUG] Starting fetch...');
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        message: text,
                        session_id: sessionId
                    }),
                    signal: abortController.signal
                });
                console.log('[DEBUG] Fetch response received');

                // 移除"思考中"动画
                hideThinking(thinkingBubble);

                // 创建流式消息气泡
                const bubble = appendStreamingMessage();
                hasResponse = true;

                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let buffer = '';
                let streamEnded = false;

                try {
                    while (!streamEnded) {
                        const { done, value } = await reader.read();
                        if (done) {
                            console.log('[DEBUG] Stream done');
                            break;
                        }

                        buffer += decoder.decode(value, { stream: true });
                        const lines = buffer.split('\n');
                        buffer = lines.pop() || '';

                        for (const line of lines) {
                            if (line.startsWith('data: ')) {
                                const data = line.slice(6);
                                if (data === '[DONE]') {
                                    streamEnded = true;
                                    break;
                                }
                                try {
                                    const parsed = JSON.parse(data);
                                    if (parsed.token) {
                                        fullText += parsed.token;
                                        bubble.textContent = fullText;
                                        scrollToBottom();
                                    }
                                } catch (e) {
                                    // ignore parse errors
                                }
                            }
                        }
                    }
                } catch (readError) {
                    console.error('[DEBUG] Reader error:', readError);
                }

                // 更新最终文本
                if (fullText) {
                    bubble.textContent = fullText;
                }

                // 保存完整回复
                conversationHistory.push({ role: 'assistant', content: fullText });
                localStorage.setItem('tcm_conversation', JSON.stringify(conversationHistory));

            } catch (error) {
                console.error('[DEBUG] Fetch error:', error);
                if (error.name !== 'AbortError') {
                    hideThinking(thinkingBubble);
                    if (!hasResponse) {
                        appendMessage('assistant', '抱歉，连接出错，请稍后重试。', false);
                    }
                }
            } finally {
                console.log('[DEBUG] Finally block executing');
                restoreInput();
            }
        }

        async function sendCommand(cmd) {
            inputBox.disabled = true;
            sendBtn.disabled = true;

            try {
                const response = await fetch('/api/command', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        command: cmd,
                        session_id: sessionId
                    })
                });

                const data = await response.json();

                if (cmd === '/reset') {
                    resetDialog();
                }
            } catch (error) {
                appendMessage('assistant', '命令执行失败，请重试。', false);
            } finally {
                inputBox.disabled = false;
                sendBtn.disabled = false;
            }
        }

        function resetDialog() {
            // 清空对话历史
            conversationHistory = [];
            localStorage.removeItem('tcm_conversation');
            // 生成新会话
            sessionId = generateSessionId();
            localStorage.setItem('tcm_session_id', sessionId);
            // 清空消息区域（保留欢迎消息）
            messagesEl.innerHTML = '';
            // 重新添加欢迎消息
            const welcomeDiv = document.createElement('div');
            welcomeDiv.className = 'welcome';
            welcomeDiv.id = 'welcome';
            welcomeDiv.innerHTML = `
                <h2>👋 欢迎来到倪海厦中医顾问</h2>
                <p>基于倪海厦大师人纪系列知识，为您提供中医养生咨询。</p>
                <div class="tips">
                    <h3>💡 您可以这样提问：</h3>
                    <ul>
                        <li>"我最近失眠，晚上睡不着，白天没精神"</li>
                        <li>"我胃不好，吃点凉的就难受，大便不成形"</li>
                        <li>"我手脚冰凉，容易疲劳，这是怎么回事？"</li>
                        <li>"我痛经，小腹冷痛，月经有血块"</li>
                    </ul>
                </div>
            `;
            messagesEl.appendChild(welcomeDiv);
            // 更新 welcomeEl 引用
            welcomeEl = welcomeDiv;
        }

        // 点赞功能：每个访问者只能点赞一次，再次点击取消
        let hasLiked = localStorage.getItem('tcm_has_liked') === 'true';

        function updateLikeDisplay(total) {
            const likeBtn = document.getElementById('like-btn');
            const likeCountEl = document.getElementById('like-count');
            likeCountEl.textContent = total;
            if (hasLiked) {
                likeBtn.classList.add('liked');
            } else {
                likeBtn.classList.remove('liked');
            }
        }

        async function toggleLike() {
            try {
                const action = hasLiked ? 'unlike' : 'like';
                const response = await fetch('/api/like', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action: action })
                });
                const data = await response.json();
                if (data.total !== undefined) {
                    hasLiked = !hasLiked;
                    localStorage.setItem('tcm_has_liked', hasLiked.toString());
                    updateLikeDisplay(data.total);
                }
            } catch (error) {
                console.error('点赞操作失败:', error);
            }
        }

        // 加载点赞数据
        fetch('/api/like')
            .then(r => r.json())
            .then(data => {
                updateLikeDisplay(data.total);
            })
            .catch(() => {
                updateLikeDisplay(88);
            });
        function showDonate() {
            document.getElementById('donate-modal').classList.add('active');
        }

        function hideDonate(event) {
            if (event && event.target !== event.currentTarget) return;
            document.getElementById('donate-modal').classList.remove('active');
        }

        // 初始化点赞显示
        updateLikeDisplay();
    </script>
</body>
</html>
"""

# ── HTTP 请求处理 ────────────────────────────────────
class RequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # 静默日志，减少输出
        pass

    def _send_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == '/' or path == '/index.html':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode('utf-8'))

        elif path == '/api/status':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self._send_cors_headers()
            self.end_headers()
            data = {
                "model": CONFIG.get("model", "unknown"),
                "search_enabled": CONFIG.get("enable_search", False),
                "api_connected": bool(CONFIG.get("api_key")),
            }
            self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

        elif path == '/api/like':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self._send_cors_headers()
            self.end_headers()
            total = _load_like_total()
            self.wfile.write(json.dumps({"total": total}, ensure_ascii=False).encode('utf-8'))

        elif path == '/img/1.png':
            self._serve_file('img/1.png', 'image/png')

        else:
            self.send_response(404)
            self.end_headers()

    def _serve_file(self, relative_path, content_type):
        """提供静态文件服务。"""
        file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)
        if os.path.exists(file_path):
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self._send_cors_headers()
            self.end_headers()
            with open(file_path, 'rb') as f:
                self.wfile.write(f.read())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # 读取请求体
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            data = {}

        if path == '/api/chat':
            self._handle_chat(data)
        elif path == '/api/command':
            self._handle_command(data)
        elif path == '/api/like':
            self._handle_like(data)
        else:
            self.send_response(404)
            self.end_headers()

    def _handle_chat(self, data):
        """处理聊天请求，使用 SSE 流式输出。"""
        message = data.get('message', '').strip()
        session_id = data.get('session_id', 'default')
        logger.info(f"[CHAT] session={session_id}, message={message[:50]}...")

        if not message:
            self.send_response(400)
            self.end_headers()
            logger.warning("[CHAT] Empty message")
            return

        advisor = get_or_create_session(session_id)
        logger.info(f"[CHAT] Advisor created, session={session_id}")

        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'keep-alive')
        self._send_cors_headers()
        self.end_headers()
        logger.info("[CHAT] SSE headers sent")

        try:
            token_count = 0
            for token in advisor.chat_stream(message):
                # SSE 格式: data: {...}\n\n
                payload = json.dumps({"token": token}, ensure_ascii=False)
                self.wfile.write(f"data: {payload}\n\n".encode('utf-8'))
                self.wfile.flush()
                token_count += 1

            # 结束标记
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
            logger.info(f"[CHAT] Stream complete, tokens={token_count}")

        except Exception as e:
            logger.error(f"[CHAT] Error during stream: {e}")
            error_msg = json.dumps({"error": str(e)}, ensure_ascii=False)
            self.wfile.write(f"data: {error_msg}\n\n".encode('utf-8'))
            self.wfile.flush()

    def _handle_like(self, data):
        """处理点赞/取消点赞请求，返回最新总数。"""
        action = data.get('action', 'like')
        with LIKE_LOCK:
            total = _load_like_total()
            if action == 'like':
                total += 1
            elif action == 'unlike' and total > 0:
                total -= 1
            _save_like_total(total)

        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps({"total": total}, ensure_ascii=False).encode('utf-8'))

    def _handle_command(self, data):
        """处理命令请求（/reset, /slots 等）。"""
        command = data.get('command', '')
        session_id = data.get('session_id', 'default')

        result = {}

        if command == '/reset':
            reset_session(session_id)
            result = {"status": "ok", "message": "已重置对话和问诊信息"}
        else:
            result = {"status": "error", "message": f"未知命令: {command}"}

        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(result, ensure_ascii=False).encode('utf-8'))


# ── 主程序 ────────────────────────────────────────────
class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """多线程 HTTP 服务器，支持 SSE 流式输出不阻塞。"""
    daemon_threads = True
    allow_reuse_address = True

def main():
    port = 8866
    server = ThreadedHTTPServer(('0.0.0.0', port), RequestHandler)

    print("=" * 60)
    print(f"  倪海厦中医顾问 Web UI")
    print(f"  地址: http://localhost:{port}")
    print(f"  模型: {CONFIG.get('model', 'unknown')}")
    print("=" * 60)
    print("  按 Ctrl+C 停止服务")
    print("=" * 60)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已停止")
        server.shutdown()

if __name__ == '__main__':
    main()
