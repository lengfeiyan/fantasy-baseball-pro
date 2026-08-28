"""异常信息中文化（修复 L2：中文界面弹英文异常）。

后台任务抛出的 Python/网络库异常信息是英文的，直接弹窗给中文用户很突兀。
``friendly_error()`` 把常见异常翻译成中文说明，并附原始信息供排查。
"""

from __future__ import annotations

import re
from typing import Any, Optional

_CJK = re.compile(r"[\u4e00-\u9fff]")

# (正则, 中文说明)，按顺序匹配第一条命中的
_MESSAGE_RULES = [
    (r"(?i)invalid literal for int", "输入的不是有效整数"),
    (r"(?i)could not convert string to float", "输入的不是有效数字"),
    (r"(?i)no such file or directory", "文件不存在，请检查路径"),
    (r"(?i)is a directory", "路径指向了文件夹而不是文件"),
    (r"(?i)permission denied", "没有读写权限"),
    (r"(?i)http error 401", "认证失败（HTTP 401）"),
    (r"(?i)http error 403", "访问被拒绝（HTTP 403，数据源可能屏蔽了请求）"),
    (r"(?i)http error 404", "请求的资源不存在（HTTP 404，数据源页面可能有变动）"),
    (r"(?i)http error 429", "请求过于频繁，被限流（HTTP 429），请稍后再试"),
    (r"(?i)http error 5\d\d", "数据源服务器异常（HTTP 5xx），请稍后再试"),
    (r"(?i)http error", "HTTP 请求失败"),
    (r"(?i)timed out|timeout", "网络请求超时，请检查网络后重试"),
    (r"(?i)connection refused", "连接被拒绝，目标服务器未响应"),
    (r"(?i)connection reset", "连接被重置，请重试"),
    (r"(?i)getaddrinfo failed|name or service not known", "域名解析失败，请检查网络"),
    (r"(?i)no space left|disk full", "磁盘空间不足"),
    (r"(?i)unable to open database|database is locked", "数据库访问失败（可能被其他进程占用）"),
    (r"(?i)operationalerror", "数据库操作失败"),
]

_TYPE_HINTS = {
    "KeyError": "缺少必要的数据字段（数据源返回格式可能有变）",
    "ValueError": "数值或参数不合法",
    "FileNotFoundError": "文件不存在，请检查路径",
    "NotADirectoryError": "路径指向了文件夹而不是文件",
    "PermissionError": "没有读写权限",
    "TimeoutError": "网络请求超时，请检查网络后重试",
}


def _type_hint(e: BaseException) -> Optional[str]:
    """按异常类型（含父类）匹配中文说明。"""
    for base in type(e).__mro__:
        if base.__name__ in _TYPE_HINTS:
            return _TYPE_HINTS[base.__name__]
    return None


def _message_hint(msg: str) -> Optional[str]:
    """按消息文本匹配中文说明。"""
    for pattern, hint in _MESSAGE_RULES:
        if re.search(pattern, msg):
            return hint
    return None


def friendly_error(e: Any) -> str:
    """把异常转成对中文用户友好的说明。

    - 消息本身已含中文：原样返回（业务代码主动抛出的中文错误）
    - 命中已知类型/消息：返回「中文说明 + 原始详情」
    - 未命中：返回「操作失败 + 原始详情」
    """
    if e is None:
        return "操作失败"
    msg = str(e).strip()
    if not msg:
        return "操作失败"
    if _CJK.search(msg):
        return msg
    # 先按消息文本（能给出更具体的中文说明，如"不是有效整数"），再按异常类型兜底
    hint = _message_hint(msg)
    if hint is None and isinstance(e, BaseException):
        hint = _type_hint(e)
    if hint is None:
        hint = "操作失败"
    return f"{hint}\n\n详情：{msg}"
