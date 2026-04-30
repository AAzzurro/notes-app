"""
AI服务模块 - 基于DeepSeek API实现AI功能
包含：AI摘要、AI问答、AI智能标签推荐
"""

import os
import requests
import json

# DeepSeek API配置
# 请通过环境变量 DEEPSEEK_API_KEY 设置你的API密钥
# 示例: export DEEPSEEK_API_KEY=sk-xxxxxx (Linux/Mac)
#       set DEEPSEEK_API_KEY=sk-xxxxxx (Windows CMD)
#       $env:DEEPSEEK_API_KEY="sk-xxxxxx" (Windows PowerShell)
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY', '')
DEEPSEEK_API_URL = 'https://api.deepseek.com/v1/chat/completions'


def call_deepseek_api(system_prompt: str, user_message: str, max_tokens: int = 1000,
                     temperature: float = 0.7, timeout: int = 60,
                     response_format: dict = None) -> str:
    """
    调用DeepSeek API
    
    Args:
        system_prompt: 系统提示词
        user_message: 用户消息
        max_tokens: 最大返回token数
        temperature: 采样温度，越低越快越稳定
        timeout: 请求超时时间（秒）
        response_format: 可选的响应格式（如 {'type': 'json_object'}）
        
    Returns:
        AI生成的回复内容
        
    Raises:
        ValueError: 当API密钥未配置时
        Exception: 当API调用失败时
    """
    if not DEEPSEEK_API_KEY:
        raise ValueError('DeepSeek API密钥未配置，请设置环境变量DEEPSEEK_API_KEY或在ai_service.py中配置')
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {DEEPSEEK_API_KEY}'
    }
    
    payload = {
        'model': 'deepseek-chat',
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_message}
        ],
        'max_tokens': max_tokens,
        'temperature': temperature,
        'stream': False,
    }
    if response_format:
        payload['response_format'] = response_format
    
    try:
        response = requests.post(
            DEEPSEEK_API_URL,
            headers=headers,
            json=payload,
            timeout=timeout
        )
        response.raise_for_status()
        result = response.json()
        return result['choices'][0]['message']['content']
    except requests.exceptions.RequestException as e:
        raise Exception(f'DeepSeek API调用失败: {str(e)}')


def generate_summary(note_title: str, note_content: str) -> str:
    """
    生成笔记摘要和核心考点
    
    Args:
        note_title: 笔记标题
        note_content: 笔记内容
        
    Returns:
        包含摘要和核心考点的Markdown格式文本
    """
    system_prompt = """你是一位专业的学习笔记分析助手。你的任务是从笔记中提取核心知识点和考点。
请用简洁清晰的语言，按照以下格式输出：

## 📝 摘要
[用2-3句话概括笔记的主要内容]

## 🎯 核心考点
1. [考点1]
2. [考点2]
3. [考点3]
...

## 💡 学习建议
[针对该笔记内容给出简短的学习建议]

请确保输出内容准确、简洁、有针对性。"""
    
    user_message = f"""请分析以下笔记并生成摘要和核心考点：

标题：{note_title}

内容：
{note_content}"""
    
    return call_deepseek_api(system_prompt, user_message, max_tokens=1500)


def chat_with_note(note_title: str, note_content: str, question: str, chat_history: list = None) -> str:
    """
    基于笔记内容进行对话问答
    
    Args:
        note_title: 笔记标题
        note_content: 笔记内容
        question: 用户问题
        chat_history: 对话历史 [{'role': 'user/assistant', 'content': '...'}]
        
    Returns:
        AI的回答
    """
    system_prompt = f"""你是一位专业的学习助手，正在帮助用户理解和学习一篇笔记的内容。

笔记标题：{note_title}

笔记内容：
{note_content}

请基于这篇笔记的内容回答用户的问题。如果用户的问题超出了笔记范围，请：
1. 首先说明这个问题不在笔记范围内
2. 然后根据你的知识尽量提供有价值的回答
3. 建议用户查阅相关资料以获取更详细的信息

请用简洁、准确、友好的语言回答。"""
    
    messages = [{'role': 'system', 'content': system_prompt}]
    
    # 添加对话历史
    if chat_history:
        for msg in chat_history:
            messages.append({
                'role': msg['role'],
                'content': msg['content']
            })
    
    # 添加当前问题
    messages.append({'role': 'user', 'content': question})
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {DEEPSEEK_API_KEY}'
    }
    
    payload = {
        'model': 'deepseek-chat',
        'messages': messages,
        'max_tokens': 1000,
        'temperature': 0.7
    }
    
    try:
        response = requests.post(
            DEEPSEEK_API_URL,
            headers=headers,
            json=payload,
            timeout=60
        )
        response.raise_for_status()
        result = response.json()
        return result['choices'][0]['message']['content']
    except requests.exceptions.RequestException as e:
        raise Exception(f'DeepSeek API调用失败: {str(e)}')


def recommend_tags(note_title: str, note_content: str) -> list:
    """
    智能推荐笔记标签（速度优化版）

    Args:
        note_title: 笔记标题
        note_content: 笔记内容

    Returns:
        推荐的标签列表
    """
    # 精简 system prompt，减少输入 token 以加快推理
    system_prompt = (
        '你是笔记标签推荐助手。根据标题和内容，返回3-5个1-4字的简洁标签，'
        '覆盖学科、知识点或主题。只输出JSON对象，格式：{"tags":["标签1","标签2","标签3"]}，不要任何其他文字。'
    )

    # 裁剪内容长度，内容越短响应越快（由 2000 -> 1000）
    trimmed = note_content[:1000]
    user_message = f'标题：{note_title}\n内容：{trimmed}'

    result = ''
    try:
        # 低温度 + 小 max_tokens + JSON 模式，大幅缩短生成耗时
        result = call_deepseek_api(
            system_prompt,
            user_message,
            max_tokens=120,
            temperature=0.2,
            timeout=30,
            response_format={'type': 'json_object'},
        )
        result = (result or '').strip()
        if result.startswith('```'):
            lines = result.split('\n')
            result = '\n'.join(lines[1:-1] if lines[-1].startswith('```') else lines[1:])

        data = json.loads(result)
        tags = data.get('tags', []) if isinstance(data, dict) else data
        if isinstance(tags, list):
            return [tag.strip() for tag in tags if isinstance(tag, str) and tag.strip()]
        return []
    except (json.JSONDecodeError, Exception):
        # 回退：从返回文本中提取JSON数组
        import re
        match = re.search(r'\[.*?\]', result, re.DOTALL)
        if match:
            try:
                tags = json.loads(match.group())
                return [tag.strip() for tag in tags if isinstance(tag, str) and tag.strip()]
            except Exception:
                pass
        return []
