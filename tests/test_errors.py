"""gui/errors.py 的 friendly_error 测试（修复 L2：中文界面弹英文异常）。"""

from fantasy_baseball.gui.errors import friendly_error


def test_chinese_message_passthrough():
    """业务代码主动抛的中文错误原样返回。"""
    assert friendly_error(ValueError("选秀顺位必须在 1-12 之间")) == "选秀顺位必须在 1-12 之间"


def test_invalid_int_message():
    out = friendly_error(ValueError("invalid literal for int() with base 10: 'abc'"))
    assert "有效整数" in out
    assert "详情" in out and "'abc'" in out


def test_file_not_found():
    out = friendly_error(FileNotFoundError("no such file or directory: 'x.csv'"))
    assert "文件不存在" in out


def test_http_403_message():
    out = friendly_error(OSError("HTTP Error 403: Forbidden"))
    assert "访问被拒绝" in out


def test_timeout_type():
    out = friendly_error(TimeoutError("timed out"))
    assert "超时" in out


def test_keyerror_type():
    """KeyError 的 str 只是键名，须按类型翻译。"""
    out = friendly_error(KeyError("vorp"))
    assert "数据字段" in out
    assert "'vorp'" in out


def test_none_and_unknown():
    assert friendly_error(None) == "操作失败"
    out = friendly_error(RuntimeError("something weird happened"))
    assert out.startswith("操作失败")
    assert "something weird happened" in out
