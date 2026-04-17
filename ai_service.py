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


def call_deepseek_api(system_prompt: str, user_message: str, max_tokens: int = 1000) -> str:
    """
    调用DeepSeek API
    
    Args:
        system_prompt: 系统提示词
        user_message: 用户消息
        max_tokens: 最大返回token数
        
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
    智能推荐笔记标签
    
    Args:
        note_title: 笔记标题
        note_content: 笔记内容
        
    Returns:
        推荐的标签列表
    """
    system_prompt = """你是一位专业的笔记标签推荐助手。你的任务是根据笔记内容推荐合适的标签。

请遵循以下规则：
1. 推荐3-5个最合适的标签
2. 标签应该简洁明了，通常是1-4个字
3. 标签应该反映笔记的核心主题、学科领域或知识点
4. 常见的标签类型包括：学科名（如"操作系统"、"数据结构"）、知识点（如"进程"、"排序算法"）、难度级别（如"基础"、"进阶"）

请以JSON数组格式返回标签，例如：["操作系统", "进程管理", "调度算法"]"""
    
    user_message = f"""请为以下笔记推荐合适的标签：

标题：{note_title}

内容：
{note_content[:2000]}  # 限制长度避免超出token限制

请直接返回JSON数组格式的标签列表。"""
    
    try:
        result = call_deepseek_api(system_prompt, user_message, max_tokens=200)
        # 尝试解析JSON
        # 处理可能的markdown代码块格式
        result = result.strip()
        if result.startswith('```'):
            # 移除markdown代码块标记
            lines = result.split('\n')
            result = '\n'.join(lines[1:-1] if lines[-1].startswith('```') else lines[1:])
        
        tags = json.loads(result)
        if isinstance(tags, list):
            return [tag.strip() for tag in tags if isinstance(tag, str) and tag.strip()]
        return []
    except (json.JSONDecodeError, Exception):
        # 如果JSON解析失败，尝试从文本中提取标签
        # 查找方括号内的内容
        import re
        match = re.search(r'\[.*?\]', result, re.DOTALL)
        if match:
            try:
                tags = json.loads(match.group())
                return [tag.strip() for tag in tags if isinstance(tag, str) and tag.strip()]
            except:
                pass
        return []
