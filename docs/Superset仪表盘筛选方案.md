# Superset 仪表盘筛选加载方案

## 1. 背景

当前 Data Formulator 中的 `Superset 仪表盘` 面板，主要能力是：

1. 列出当前用户可见的 Superset dashboards。
2. 展开某个 dashboard 后，列出该 dashboard 关联的数据集。
3. 用户选择一个数据集后，将该数据集直接加载到本地 DuckDB。

当前实现并不会自动复用 Superset dashboard 页面上“当前已经选中的筛选条件”。  
因此，用户虽然是从“仪表盘”入口进入，但实际拿到的数据更接近：

- 该 dashboard 关联的数据集原始数据
- 或虚拟数据集 SQL 的原始查询结果

而不是：

- 该 dashboard 在当前筛选条件下的数据

## 2. 本次方案目标

本方案的目标是，在 **不实现“读取当前 dashboard 已选条件”** 的前提下，尽量提升“从仪表盘加载数据”的准确性和可用性。

本次需要实现：

1. 读取 dashboard 允许的筛选项。
2. 识别每个筛选项对应的字段、数据集、类型、作用范围。
3. 在 Data Formulator 中动态生成筛选表单。
4. 当用户选择某个筛选项时，再去读取该筛选项的候选值。
5. 用户在 Data Formulator 中重新选择一次条件。
6. 按用户选择的条件加载对应数据集。

本次明确不做：

1. 不读取 dashboard 页面“当前已选中的筛选条件”。
2. 不复刻 Superset 的运行时联动状态。
3. 不实现 cross-filter、drill-down、图表联动状态同步。
4. 不保证 100% 覆盖所有 Superset native filter 的高级特性。

## 3. 设计原则

### 3.1 边界清晰

只读取 **静态配置** 和 **字段候选值**，不处理 **运行时筛选状态**。

### 3.2 可渐进增强

先支持最常见的筛选类型：

- 单选
- 多选
- 文本搜索
- 数值比较
- 时间范围

复杂类型后续再补。

### 3.3 候选值按需加载

当某些字段候选值很多时，不应在 dashboard 展开时一次性读取全部候选值。  
建议改为：

1. 先只展示“可筛字段列表”
2. 用户选择某个筛选项
3. 前端再单独请求该字段的候选值
4. 候选值面板支持分页、limit、搜索

这也是本方案的重点。

## 4. 用户体验方案

## 4.1 交互流程

用户进入 `Superset 仪表盘` 后：

1. 看到 dashboard 列表
2. 展开某个 dashboard
3. 看到该 dashboard 关联的数据集
4. 点击某个数据集的“按条件加载”按钮
5. 打开“筛选条件”对话框
6. 对话框内显示该 dashboard 对当前数据集可用的筛选项
7. 用户选择某个筛选项后，系统再去拉取该字段候选值
8. 用户填写筛选条件并提交
9. 后端按条件加载数据到 DuckDB

## 4.2 建议 UI 结构

对话框可分为 3 个区域：

### A. 顶部：目标信息

- Dashboard 名称
- Dataset 名称
- Schema / Database

### B. 中间：筛选项列表

每个筛选项展示：

- 筛选名称
- 目标字段
- 目标 dataset
- 筛选类型
- 是否支持多选

### C. 底部：当前条件编辑区

用户选中某个筛选项后，右侧或下方展示对应输入控件：

- 枚举字段：下拉 / 多选
- 文本字段：输入框
- 数值字段：操作符 + 输入值
- 时间字段：开始时间 + 结束时间

## 4.3 候选值加载策略

候选值过多时，建议采用以下策略：

1. 默认不自动读取所有候选值
2. 只有当用户点击某个筛选项时才读取
3. 首次仅拉取前 `N` 个值，例如 50 或 100 个
4. 若用户继续输入关键字，则按关键字再次请求
5. 若字段基数极高，则仅支持远程搜索，不提供全量下拉

推荐规则：

- 低基数字段：直接读取前 100 个 distinct values
- 中基数字段：读取前 50 个，支持搜索
- 高基数字段：不预拉全量，只在用户输入关键词后搜索

## 5. 功能范围定义

## 5.1 需要支持的能力

### Dashboard 级

- 获取 dashboard 详情
- 获取 dashboard 的 native filter 配置
- 获取 dashboard 关联的数据集

### Dataset 级

- 获取 dataset 字段元信息
- 获取字段类型
- 获取字段候选值

### 加载级

- 将用户在 Data Formulator 中选择的 filters 转换为查询条件
- 在加载 dataset 时将 filters 应用到 SQL

## 5.2 暂不支持的能力

- dashboard 当前页面 filter state 还原
- 级联筛选联动
- 当前 dashboard 中不同图表上下文差异化 filter 合并
- 原生 Superset URL 参数完全兼容

## 6. 依赖的 Superset 接口

以下是建议依赖的 Superset API。

## 6.1 Dashboard 详情

`GET /api/v1/dashboard/{id_or_slug}`

用途：

- 获取 dashboard 详情
- 获取 `json_metadata`
- 从 `json_metadata` 中解析 `native_filter_configuration`

关键点：

- 新旧版本 Superset 可能同时存在 `native_filter_configuration` 或旧字段命名
- 需要兼容空值和结构差异

## 6.2 Dashboard 数据集列表

`GET /api/v1/dashboard/{id_or_slug}/datasets`

用途：

- 获取 dashboard 关联的数据集
- 用于当前 UI 中的数据集列表展示
- 作为 filter -> dataset 关联的补充校验

## 6.3 Dashboard 图表列表

`GET /api/v1/dashboard/{id_or_slug}/charts`

用途：

- 可选增强项
- 用于分析某些 filter 作用范围
- 第一版不是强依赖，但建议预留

## 6.4 Dataset 详情

`GET /api/v1/dataset/{pk}`

用途：

- 获取 columns / metrics
- 获取字段类型
- 校验 filter 中引用的字段是否存在

## 6.5 Dataset 字段候选值

`GET /api/v1/dataset/distinct/{column_name}`

用途：

- 获取字段 distinct values
- 支撑单选、多选、下拉搜索

注意：

- 具体请求参数需结合 Superset 实际版本确认
- 候选值读取应尽量支持 limit / search
- 若官方接口能力不足，可在我方后端代理层补一层搜索与分页能力

## 6.6 可选增强：Chart Data

`GET /api/v1/chart/{pk}/data/`  
`POST /api/v1/chart/data`

用途：

- 当 `dataset/distinct` 无法满足复杂候选值读取时，可作为增强方案
- 可借助 `extra_form_data` 做更复杂的数据查询

缺点：

- 更复杂
- 与 chart query context 绑定更紧
- 第一版不建议优先依赖

## 7. 我方系统需要新增的接口

为了避免前端直接拼装 Superset 请求，建议仍然由 Data Formulator 后端做代理层。

## 7.1 获取 dashboard 可用筛选项

建议新增接口：

`GET /api/superset/catalog/dashboards/{dashboard_id}/filters`

返回示例：

```json
{
  "status": "ok",
  "dashboard_id": 12,
  "filters": [
    {
      "id": "NATIVE_FILTER-abc",
      "name": "地区",
      "filter_type": "select",
      "dataset_id": 45,
      "dataset_name": "sales_orders",
      "column_name": "region",
      "column_type": "STRING",
      "multi": true,
      "required": false,
      "supports_search": true
    }
  ]
}
```

后端职责：

1. 调用 Superset dashboard detail 接口
2. 解析 `json_metadata.native_filter_configuration`
3. 过滤出与当前 dataset 相关的筛选项
4. 结合 dataset detail 补齐字段类型

## 7.2 获取某筛选项的候选值

建议新增接口：

`GET /api/superset/catalog/filters/options`

建议请求参数：

- `dashboard_id`
- `dataset_id`
- `column_name`
- `keyword` 可选
- `limit` 可选
- `offset` 可选

返回示例：

```json
{
  "status": "ok",
  "dataset_id": 45,
  "column_name": "region",
  "options": [
    { "label": "East", "value": "East" },
    { "label": "West", "value": "West" }
  ],
  "has_more": true
}
```

后端职责：

1. 优先调用 Superset 的 distinct values 能力
2. 若支持搜索参数，则直接透传
3. 若官方接口不支持搜索，可在我方后端做本地裁剪或改用 SQL / chart data 兜底

## 7.3 按筛选条件加载 dataset

扩展现有接口：

`POST /api/superset/data/load-dataset`

新增请求字段：

```json
{
  "dataset_id": 45,
  "row_limit": 20000,
  "table_name": "sales_orders_filtered",
  "filters": [
    {
      "column": "region",
      "operator": "IN",
      "value": ["East", "West"]
    },
    {
      "column": "order_date",
      "operator": "BETWEEN",
      "value": ["2025-01-01", "2025-01-31"]
    }
  ]
}
```

后端职责：

1. 校验字段是否存在于 dataset 中
2. 将结构化 filters 转换为 SQL `WHERE` 条件
3. 对物理表和虚拟数据集统一在外层包裹查询
4. 限制允许的操作符，避免注入风险

## 8. 前端实现方案

## 8.1 `SupersetDashboards.tsx` 建议改造点

在每个 dataset 操作区新增一个按钮：

- `按条件加载`

点击后：

1. 打开 `DashboardFilterDialog`
2. 传入 `dashboardId`
3. 传入 `datasetId`
4. 读取当前 dashboard 可用筛选项

## 8.2 新增组件建议

建议新增组件：

- `DashboardFilterDialog.tsx`

职责：

1. 拉取当前 dashboard 的筛选项定义
2. 按字段类型渲染输入控件
3. 在用户选中某个筛选项时，按需请求候选值
4. 收集用户填写的 filters
5. 提交到 `load-dataset`

## 8.3 前端状态建议

对话框内建议维护这些状态：

- `availableFilters`
- `selectedFilterId`
- `filterOptionsCache`
- `loadingOptions`
- `filtersFormValue`
- `submitLoading`

其中：

- `filterOptionsCache` 用于缓存已读过的候选值
- 同一个字段再次打开时避免重复请求

## 8.4 候选值按需加载规则

建议规则如下：

1. 对话框打开时只加载 filter 定义，不加载 options
2. 用户点击某个筛选项时，再触发 options 请求
3. 若字段类型不适合读取候选值，例如自由文本字段，则不请求 options
4. 若字段是枚举型、多选型，则请求 options
5. 若用户在搜索框输入关键字，则重新请求 options

建议前端交互：

- 输入框防抖 300ms
- 请求参数带 `keyword`
- 列表最多展示 50 条
- 有更多时显示“继续搜索以缩小范围”

## 9. 后端实现方案

## 9.1 `superset_client.py` 需要新增的方法

建议新增：

1. `get_dashboard_detail(access_token, dashboard_id)`
2. `get_dashboard_charts(access_token, dashboard_id)` 可选
3. `get_dataset_distinct_values(access_token, dataset_id, column_name, keyword=None, limit=50, offset=0)`

## 9.2 `catalog.py` 需要新增的能力

建议新增：

1. `get_dashboard_filters(...)`
2. `get_filter_options(...)`

职责：

- 解析 dashboard filter 配置
- 映射 filter 到 dataset / column
- 合并 dataset detail 里的字段元信息
- 统一返回前端可消费的结构

## 9.3 `catalog_routes.py` 需要新增路由

建议新增：

1. `GET /dashboards/<int:dashboard_id>/filters`
2. `GET /filters/options`

## 9.4 `data_routes.py` 需要扩展

在现有 `load_dataset()` 中新增 `filters` 处理逻辑。

建议处理流程：

1. 读取 `dataset_id`
2. 获取 dataset detail
3. 获取允许字段列表
4. 校验 `filters` 中的字段和操作符
5. 拼接 `WHERE` 条件
6. 在 `base_sql` 外层生成：

```sql
SELECT *
FROM (
  <base_sql>
) AS _src
WHERE ...
LIMIT <row_limit>
```

## 10. 结构化 filter 数据模型建议

前后端建议统一使用结构化 filters，而不是直接传 SQL。

推荐结构：

```ts
interface DatasetFilter {
  column: string;
  operator:
    | 'IN'
    | 'NOT_IN'
    | 'EQ'
    | 'NEQ'
    | 'GT'
    | 'GTE'
    | 'LT'
    | 'LTE'
    | 'BETWEEN'
    | 'LIKE'
    | 'ILIKE'
    | 'IS_NULL'
    | 'IS_NOT_NULL';
  value?: string | number | boolean | Array<string | number> | [string, string];
}
```

这样做的好处：

- 安全
- 易校验
- 易扩展
- 前端表单更容易映射

## 11. 筛选类型映射建议

建议第一版支持如下映射：

| Superset 筛选类型 | Data Formulator 控件 | 说明 |
|---|---|---|
| Select | 单选下拉 | 候选值按需加载 |
| Select + multiple | 多选下拉 | 候选值按需加载 |
| Text | 文本输入框 | 支持 `LIKE` / `ILIKE` |
| Numeric | 操作符 + 数值输入 | 支持比较运算 |
| Time | 时间范围选择器 | 支持 `BETWEEN` |

不建议第一版立即支持：

- 复杂层级联动
- 多 dataset 交叉映射
- 运行时动态 filter dependency

## 12. 风险与注意事项

## 12.1 Superset 版本差异

不同版本中：

- `json_metadata` 内字段命名可能不同
- native filter 配置结构可能有差异
- distinct values 接口参数可能不完全一致

因此建议：

- 先在当前实际部署的 Superset 版本上抓一次真实返回
- 再确定最终解析逻辑

## 12.2 高基数字段

如果字段候选值很多：

- 不要一次性拉全量
- 必须支持 limit
- 尽量支持关键词搜索
- 必要时只允许手输，不显示完整下拉

## 12.3 多 dataset 作用域

一个 dashboard 的 filter 未必对当前展开的 dataset 生效。  
因此后端在返回 filters 时，建议：

- 只返回与当前 dataset 明确相关的筛选项
- 或明确标出 `applicable: true/false`

## 12.4 SQL 安全

绝不能把前端输入的自由 SQL 直接拼接执行。  
必须使用：

- 白名单字段
- 白名单操作符
- 参数化或严格转义

## 13. 推荐实施顺序

## Phase 1：打通定义读取

1. 新增 dashboard detail client
2. 解析 native filter 配置
3. 返回当前 dashboard 的可用筛选项

## Phase 2：打通候选值读取

1. 新增 distinct values client
2. 做候选值按需加载
3. 支持 limit + keyword

## Phase 3：打通条件加载

1. 扩展 `load-dataset`
2. 将结构化 filters 转换为 `WHERE`
3. 实现按条件导入 DuckDB

## Phase 4：前端体验优化

1. 增加 cache
2. 候选值搜索防抖
3. 错误提示
4. 空结果提示

## 14. 最终结论

本方案是可行的，并且很适合当前项目阶段。

它实现的是：

- 读取 dashboard 允许的筛选项
- 动态列出这些筛选项
- 在用户选择某个筛选项时，再按需读取可选值
- 由用户在 Data Formulator 中重新设置条件
- 再按条件加载 dataset

这个方案虽然不复用 dashboard 当前页面的运行时筛选状态，但已经能显著提升“从 Superset 仪表盘加载数据”的准确性和可理解性，同时实现边界清晰、风险可控、适合渐进迭代。
