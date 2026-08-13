"""GUI 公共组件工厂。

提供创建常用控件组合的 helper，减少各 tab 文件中重复的 ttk 样板代码。
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional, Tuple


def labeled_input(
    parent: tk.Widget,
    label: str,
    default: str = "",
    width: int = 20,
    label_width: int = 12,
) -> Tuple[ttk.Frame, tk.StringVar]:
    """创建「标签 + 输入框」组合，返回 (frame, var)。"""
    frame = ttk.Frame(parent)
    frame.pack(fill=tk.X, pady=3)
    ttk.Label(frame, text=label, width=label_width, anchor=tk.W).pack(side=tk.LEFT)
    var = tk.StringVar(value=default)
    ttk.Entry(frame, textvariable=var, width=width).pack(side=tk.LEFT, padx=4)
    return frame, var


def labeled_combobox(
    parent: tk.Widget,
    label: str,
    values,
    default: str = "",
    label_width: int = 12,
) -> Tuple[ttk.Frame, tk.StringVar]:
    """创建「标签 + 下拉框」组合，返回 (frame, var)。"""
    frame = ttk.Frame(parent)
    frame.pack(fill=tk.X, pady=3)
    ttk.Label(frame, text=label, width=label_width, anchor=tk.W).pack(side=tk.LEFT)
    var = tk.StringVar(value=default)
    ttk.Combobox(frame, textvariable=var, values=list(values), width=17, state="readonly").pack(
        side=tk.LEFT, padx=4
    )
    return frame, var


def action_button(
    parent: tk.Widget,
    text: str,
    command: Callable,
    side: str = tk.LEFT,
    padx: int = 4,
) -> ttk.Button:
    """创建一个标准动作按钮。"""
    btn = ttk.Button(parent, text=text, command=command)
    btn.pack(side=side, padx=padx)
    return btn


def section_frame(parent: tk.Widget, title: str) -> ttk.LabelFrame:
    """创建带标题的分组框架。"""
    frame = ttk.LabelFrame(parent, text=title, padding="10")
    frame.pack(fill=tk.BOTH, expand=True, pady=6)
    return frame


def text_display(
    parent: tk.Widget,
    height: int = 18,
) -> Tuple[ttk.Frame, tk.Text]:
    """创建带滚动条的只读文本输出区，返回 (frame, text_widget)。"""
    frame = ttk.Frame(parent)
    frame.pack(fill=tk.BOTH, expand=True, pady=4)
    text = tk.Text(frame, height=height, wrap=tk.WORD, state=tk.DISABLED)
    scroll = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=text.yview)
    text.configure(yscrollcommand=scroll.set)
    text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scroll.pack(side=tk.RIGHT, fill=tk.Y)
    return frame, text


def set_text(widget: tk.Text, content: str) -> None:
    """更新只读 Text 控件内容。"""
    widget.configure(state=tk.NORMAL)
    widget.delete("1.0", tk.END)
    widget.insert(tk.END, content)
    widget.configure(state=tk.DISABLED)


def append_text(widget: tk.Text, content: str) -> None:
    """向只读 Text 控件追加内容（工作线程安全版由调用方负责调度）。"""
    widget.configure(state=tk.NORMAL)
    widget.insert(tk.END, content)
    if not content.endswith("\n"):
        widget.insert(tk.END, "\n")
    widget.see(tk.END)
    widget.configure(state=tk.DISABLED)
