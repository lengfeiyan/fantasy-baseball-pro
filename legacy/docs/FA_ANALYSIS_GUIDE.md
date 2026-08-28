# FA球员分析工具使用指南

## 1. 功能概述

FA球员分析工具是Fantasy Baseball Pro的一个新功能模块，用于在赛季过程中辅助挑选自由球员（FA）。该工具基于实时数据、Statcast高级数据和智能算法，为用户提供个性化的FA球员推荐。

## 2. 核心功能

### 2.1 数据管理
- **更新FA池**：从数据源获取最新的自由球员数据
- **更新伤病数据**：获取最新的球员伤病信息
- **手工数据导入**：支持从CSV、Excel、JSON文件导入数据

### 2.2 智能推荐
- **综合价值评估**：基于实时表现、Statcast数据、伤病风险和位置稀缺性计算球员价值
- **位置需求匹配**：根据用户阵容缺口推荐合适位置的球员
- **风险偏好调整**：支持保守、平衡、激进三种风险偏好
- **位置筛选**：可按特定位置筛选推荐

### 2.3 数据分析
- **球员详细信息**：查看球员的基本统计、Statcast数据和价值评估
- **推荐结果导出**：将推荐结果导出为CSV文件
- **实时数据缓存**：优化数据获取性能

## 3. 使用方法

### 3.1 通过GUI使用

1. **打开FA分析选项卡**：在Fantasy Baseball Pro主界面中点击"FA分析"选项卡

2. **更新数据**：
   - 点击"更新FA池"按钮获取最新的自由球员数据
   - 点击"更新伤病数据"按钮获取最新的伤病信息

3. **设置筛选条件**：
   - **位置**：选择要筛选的位置，默认为"All"
   - **风险偏好**：选择风险偏好（保守、平衡、激进）
   - **推荐数量**：设置要生成的推荐数量

4. **生成推荐**：点击"生成推荐"按钮，系统将根据设置生成FA球员推荐

5. **查看球员详情**：在推荐列表中选择球员，查看详细信息

6. **导出结果**：点击"导出结果"按钮，将推荐结果导出为CSV文件

### 3.2 通过命令行使用

#### 更新FA池数据
```bash
python import_fa_data.py --action update-fa
```

#### 更新伤病数据
```bash
python import_fa_data.py --action update-injury
```

#### 导入数据文件
```bash
python import_fa_data.py --action import-file --file data/fa_pool.csv --type fa_pool
```

## 4. 配置说明

FA分析工具的配置选项位于`config.yaml`文件中的`fa_analyzer`部分：

```yaml
# FA分析配置
fa_analyzer:
  # 数据更新频率（小时）
  update_frequency: 6
  # 默认推荐数量
  default_top_n: 10
  # 数据来源优先级
  data_sources:
    - MLB_API
    - FANGRAPHS
    - ESPN
  # 推荐算法参数
  algorithm:
    position_weight: 0.3
    performance_weight: 0.4
    risk_weight: 0.2
    opportunity_weight: 0.1
  # 风险模型配置
  risk_model:
    # 风险偏好默认值: conservative / balanced / aggressive
    default_preference: "balanced"
    # 伤病影响权重
    injury_weight: 0.3
  # 缓存配置
  cache:
    # 缓存过期时间（小时）
    expiry: 24
    # 缓存目录
    directory: "data/cache"
```

## 5. 数据说明

### 5.1 数据库表结构

**fa_pool**：存储自由球员信息
- id: 唯一标识
- player_id: 球员ID
- name: 球员姓名
- team: 球队
- pos: 位置
- status: 状态
- last_updated: 最后更新时间

**player_season_stats**：存储球员赛季统计数据
- id: 唯一标识
- player_id: 球员ID
- name: 球员姓名
- team: 球队
- pos: 位置
- stat_type: 统计类型
- value: 统计值
- game_date: 比赛日期
- created_at: 创建时间

**user_roster**：存储用户阵容
- id: 唯一标识
- player_id: 球员ID
- name: 球员姓名
- team: 球队
- pos: 位置
- status: 状态
- acquisition_date: 获取日期

**injury_reports**：存储伤病报告
- id: 唯一标识
- player_id: 球员ID
- name: 球员姓名
- injury_type: 伤病类型
- severity: 严重程度
- start_date: 开始日期
- expected_return: 预计回归日期
- status: 状态
- created_at: 创建时间

### 5.2 数据来源

- **在线数据**：通过API获取实时数据
- **手工导入**：支持CSV、Excel、JSON格式文件
- **数据缓存**：本地缓存以提高性能

## 6. 价值计算方法

### 6.1 综合价值评分

```
综合评分 = (VORP × 0.3) + (趋势得分 × 0.15) + (伤病调整后价值 × 0.15) + (位置稀缺性调整 × 0.15) + (Statcast得分 × 0.25)
```

### 6.2 Statcast评分

**打者Statcast评分**：
```
Statcast得分 = (xwOBA × 300) + (Barrel Rate × 100) + (Exit Velocity × 1) + (Hard Hit Rate × 100) + (Swing Contact Rate × 100)
```

**投手Statcast评分**：
```
Statcast得分 = ((3 - xERA) × 20) + (Whiff Rate × 100) + (Spin Rate × 0.1) + (Velocity × 2) + ((1 - Hard Hit Allowed Rate) × 100)
```

### 6.3 伤病调整

- 轻度伤病：0.85
- 中度伤病：0.65
- 重度伤病：0.4
- 长期伤停：0.15

### 6.4 位置稀缺性调整

- C：1.3
- SS：1.2
- 2B：1.1
- 3B：1.05
- 1B：0.9
- OF：0.85
- SP：1.0
- RP：1.15

## 7. 常见问题

### 7.1 数据更新失败
- 检查网络连接
- 检查API密钥配置
- 尝试手工导入数据

### 7.2 推荐结果不准确
- 更新最新数据
- 调整风险偏好
- 检查阵容需求设置

### 7.3 GUI启动失败
- 检查Python环境
- 安装必要的依赖
- 查看日志文件了解详细错误

## 8. 依赖要求

- Python 3.7+
- pandas
- numpy
- sqlite3
- tkinter

## 9. 未来扩展

- **交易分析**：分析潜在交易的价值
- **Waiver Wire管理**：Waiver Wire优先级管理
- **预测模型**：基于历史数据预测球员未来表现
- **自动化管理**：设置自动FA挑选规则
- **移动应用**：移动端FA管理

## 10. 联系信息

Fantasy Baseball Pro v2026.0
专业级Fantasy Baseball分析与选秀模拟系统
© 2026 Fantasy Baseball Pro
