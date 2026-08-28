# Fantasy Baseball Pro 插件开发指南

本指南详细介绍如何开发、安装和管理 Fantasy Baseball Pro 系统的插件，帮助您扩展系统功能以满足个性化需求。

## 📋 插件系统概述

插件系统是 Fantasy Baseball Pro 的扩展机制，允许开发者：
- 为系统添加新功能而无需修改核心代码
- 共享和分发自定义功能模块
- 隔离功能代码，提高系统稳定性

### 核心概念
- **插件**：独立的功能模块，包含特定功能的实现
- **插件目录**：存放插件的文件夹
- **插件配置**：控制插件行为的参数设置

## 🛠️ 插件开发

### 1. 插件结构

一个标准插件应包含以下文件结构：

```
plugins/
└── your_plugin_name/          # 插件名称目录
    ├── __init__.py            # 插件初始化文件
    ├── main.py                # 插件主逻辑
    ├── config.yaml            # 插件配置文件
    └── README.md              # 插件说明文档
```

### 2. 开发步骤

#### 步骤 1：创建插件目录

在 `plugins/` 目录下创建以插件名称命名的文件夹：

```bash
mkdir -p plugins/your_plugin_name
```

#### 步骤 2：创建 `__init__.py` 文件

此文件标识插件目录为 Python 包，并提供插件元数据：

```python
# plugins/your_plugin_name/__init__.py

plugin_info = {
    "name": "Your Plugin Name",
    "version": "1.0.0",
    "description": "插件功能描述",
    "author": "Your Name",
    "requires": [],  # 依赖的其他插件
    "enabled": True  # 默认启用状态
}

# 插件入口函数
def initialize():
    """初始化插件"""
    from .main import setup
    return setup()

def run():
    """运行插件"""
    from .main import execute
    return execute()
```

#### 步骤 3：创建 `main.py` 文件

实现插件的核心功能：

```python
# plugins/your_plugin_name/main.py

def setup():
    """设置插件"""
    print("Your plugin setup completed")
    return True

def execute():
    """执行插件功能"""
    # 实现插件的核心逻辑
    result = "Plugin execution result"
    print(result)
    return result

def get_config():
    """获取插件配置"""
    import yaml
    with open('plugins/your_plugin_name/config.yaml', 'r') as f:
        return yaml.safe_load(f)
```

#### 步骤 4：创建 `config.yaml` 文件

定义插件的配置参数：

```yaml
# plugins/your_plugin_name/config.yaml

# 插件配置示例
settings:
  parameter1: value1
  parameter2: value2
  parameter3:
    sub_param1: sub_value1
    sub_param2: sub_value2
```

#### 步骤 5：创建 `README.md` 文件

提供插件的使用说明：

```markdown
# Your Plugin Name

## 功能描述
插件的详细功能说明

## 安装方法
1. 将插件目录复制到 `plugins/` 文件夹
2. 在 GUI 插件管理选项卡中启用插件

## 配置参数
- `parameter1`: 参数1描述
- `parameter2`: 参数2描述

## 使用方法
使用插件的具体步骤
```

### 3. 插件开发最佳实践

1. **命名规范**：
   - 插件名称使用小写字母和下划线
   - 文件名使用清晰的描述性名称

2. **代码结构**：
   - 保持代码模块化，便于维护
   - 使用适当的异常处理
   - 添加详细的文档字符串

3. **功能实现**：
   - 专注于单一功能，避免功能过于复杂
   - 遵循系统的设计模式
   - 确保插件在启用/禁用时不会影响系统稳定性

4. **配置管理**：
   - 使用 YAML 格式存储配置
   - 提供合理的默认配置值
   - 支持通过 GUI 界面修改配置

## 📦 插件安装

### 方法 1：手动安装

1. **下载插件**：获取插件的压缩包或源代码
2. **解压插件**：将插件目录复制到 `plugins/` 文件夹
3. **启用插件**：在 GUI 插件管理选项卡中启用插件

### 方法 2：通过 GUI 安装

1. **打开插件管理选项卡**：在 Fantasy Baseball Pro GUI 中点击 "插件管理"
2. **点击 "浏览"**：选择插件的压缩包文件
3. **点击 "安装"**：系统会自动解压并安装插件
4. **启用插件**：在插件列表中选择插件并点击 "启用插件"

## 🔧 插件管理

### 通过 GUI 管理插件

1. **查看插件**：在 "插件管理" 选项卡中查看已安装的插件
2. **刷新列表**：点击 "刷新插件列表" 按钮更新插件状态
3. **启用/禁用**：选择插件后点击相应按钮改变其状态
4. **配置插件**：在 "插件配置" 文本框中编辑插件的设置参数

### 通过命令行管理插件

```bash
# 列出所有插件
python -m plugins.manager list

# 启用插件
python -m plugins.manager enable plugin_name

# 禁用插件
python -m plugins.manager disable plugin_name

# 查看插件信息
python -m plugins.manager info plugin_name
```

## 📝 插件开发示例

### 示例 1：简单数据导入插件

```python
# plugins/custom_import/__init__.py

plugin_info = {
    "name": "Custom Data Import",
    "version": "1.0.0",
    "description": "导入自定义格式的球员数据",
    "author": "Developer",
    "requires": [],
    "enabled": True
}

def initialize():
    from .main import setup
    return setup()

def run(data_file):
    from .main import import_data
    return import_data(data_file)
```

```python
# plugins/custom_import/main.py

import pandas as pd

def setup():
    """设置插件"""
    print("Custom data import plugin setup completed")
    return True

def import_data(data_file):
    """导入自定义数据"""
    try:
        # 读取自定义格式数据
        df = pd.read_csv(data_file, delimiter=';')
        
        # 数据处理逻辑
        # ...
        
        return df
    except Exception as e:
        print(f"Import error: {e}")
        return None
```

### 示例 2：自定义分析插件

```python
# plugins/advanced_analysis/__init__.py

plugin_info = {
    "name": "Advanced Analysis",
    "version": "1.0.0",
    "description": "提供高级球员分析功能",
    "author": "Developer",
    "requires": [],
    "enabled": True
}

def initialize():
    from .main import setup
    return setup()

def run(player_data):
    from .main import analyze
    return analyze(player_data)
```

```python
# plugins/advanced_analysis/main.py

def setup():
    """设置插件"""
    print("Advanced analysis plugin setup completed")
    return True

def analyze(player_data):
    """执行高级分析"""
    # 分析逻辑
    # ...
    
    analysis_results = {
        "strengths": [],
        "weaknesses": [],
        "recommendations": []
    }
    
    return analysis_results
```

## 🔍 插件调试

### 常见问题及解决方案

1. **插件不显示在列表中**
   - 检查插件目录结构是否正确
   - 确保 `__init__.py` 文件存在且格式正确
   - 点击 "刷新插件列表" 按钮

2. **插件启用失败**
   - 检查插件依赖是否满足
   - 查看系统日志了解具体错误
   - 确保插件代码无语法错误

3. **插件功能异常**
   - 检查插件配置是否正确
   - 验证输入数据格式
   - 添加详细的日志输出以定位问题

### 调试技巧

1. **添加日志输出**：在关键位置添加 print 语句或使用 logging 模块
2. **使用断点**：在 IDE 中设置断点进行调试
3. **测试模式**：创建测试脚本验证插件功能

## 📚 插件 API 参考

### 核心 API

#### 插件初始化
```python
def initialize():
    """初始化插件"""
    # 初始化代码
    return True  # 返回 True 表示初始化成功
```

#### 插件执行
```python
def run(*args, **kwargs):
    """执行插件功能"""
    # 功能实现
    return result  # 返回执行结果
```

#### 配置获取
```python
def get_config():
    """获取插件配置"""
    # 读取配置
    return config  # 返回配置字典
```

### 系统接口

插件可以通过以下方式与系统交互：

1. **访问数据**：
   - 读取系统生成的 CSV 文件
   - 调用系统数据管理模块

2. **调用系统功能**：
   - 使用系统的工具函数
   - 集成系统的分析功能

3. **扩展 GUI**：
   - 添加自定义选项卡
   - 扩展现有界面功能

## 🤝 插件分享

### 打包插件

1. **创建插件目录**：确保插件目录结构完整
2. **添加 README**：提供详细的使用说明
3. **压缩插件**：将插件目录压缩为 ZIP 文件

### 分享渠道

- **GitHub**：创建仓库托管插件代码
- **论坛**：在相关论坛分享插件
- **邮件**：直接发送给需要的用户

## 📄 插件清单

### 官方推荐插件

| 插件名称 | 版本 | 功能描述 | 下载链接 |
|---------|------|---------|----------|
| Custom Data Import | 1.0.0 | 导入自定义格式的数据 | - |
| Advanced Analysis | 1.0.0 | 高级球员分析功能 | - |
| League Rules | 1.0.0 | 特定联盟规则支持 | - |
| Draft Strategy | 1.0.0 | 自定义选秀策略 | - |

### 社区贡献插件

欢迎社区成员贡献插件，扩展 Fantasy Baseball Pro 的功能生态。

## 📞 支持与反馈

如果您在插件开发过程中遇到问题或有任何建议，请通过以下方式联系我们：

- **GitHub Issues**：提交问题和功能请求
- **邮件**：发送邮件至支持邮箱
- **论坛**：在相关论坛讨论插件开发

---

**Fantasy Baseball Pro 插件系统** - 让您的 Fantasy Baseball 体验更加个性化！ 🎉