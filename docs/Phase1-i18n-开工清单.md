# Phase 1 i18n 开工清单

> 用途：这是一份执行中的工作清单，配合 `docs/UPGRADE-PLAN.md` 中的 Phase 1 使用。  
> 使用方式：开发过程中持续勾选、补充备注、记录阻塞项，不要求一次写完。

---

## 一、当前目标

- [ ] 基于 `0.7/dev` 接通 `react-i18next` 运行时国际化
- [ ] 复用 `0.6` 已有翻译资源
- [ ] 优先完成壳层 UI 的中英文切换
- [ ] 保证国际化改动不影响图表生成、数据处理、模型调用
- [ ] 将改动范围控制在 `src/i18n/` 和前端 UI 文件

## 二、开发边界

### 2.1 本阶段要做

- [ ] 接通 `i18n` 基础设施
- [ ] 补齐依赖
- [ ] 初始化入口接线
- [ ] 翻译首页、菜单、弹窗、提示消息
- [ ] 翻译配置面板、会话管理、上传入口等高频 UI
- [ ] 人工验证中英文切换

### 2.2 本阶段不要做

- [ ] 不修改 `src/lib/agents-chart/**`
- [ ] 不翻译图表模板名、内部枚举值、语义类型字符串
- [ ] 不翻译测试数据、测试断言、示例 spec
- [ ] 不翻译发给后端或模型的 prompt / payload / 结构化字段
- [ ] 不把运行时国际化重构成复杂中间层

## 三、基础设施清单

### 3.1 目录与文件确认

- [ ] `src/i18n/index.ts` 已存在
- [ ] `src/i18n/locales/index.ts` 已存在
- [ ] `src/i18n/locales/en/index.ts` 已存在
- [ ] `src/i18n/locales/zh/index.ts` 已存在
- [ ] `src/i18n/locales/en/*.json` 已复制
- [ ] `src/i18n/locales/zh/*.json` 已复制

### 3.2 依赖接入

- [ ] `package.json` 已添加 `i18next`
- [ ] `package.json` 已添加 `react-i18next`
- [ ] `package.json` 已添加 `i18next-browser-languagedetector`
- [ ] 安装依赖后项目可正常启动

### 3.3 初始化接线

- [ ] `src/index.tsx` 已增加 `import './i18n'`
- [ ] `src/i18n/index.ts` 已设置 `fallbackLng: 'en'`
- [ ] 检测顺序已设置为 `localStorage -> navigator`
- [ ] 语言缓存已设置到 `localStorage`
- [ ] 在未修改任何业务页面前，应用可正常启动

## 四、翻译资源迁移清单

### 4.1 0.6 资源复用

- [ ] `common.json` 已检查
- [ ] `navigation.json` 已检查
- [ ] `messages.json` 已检查
- [ ] `upload.json` 已检查
- [ ] `model.json` 已检查
- [ ] `chart.json` 已检查
- [ ] `encoding.json` 已检查

### 4.2 资源迁移原则

- [ ] 暂不重构 key 体系，优先复用 0.6 现有结构
- [ ] 0.7 新增文案补到最接近的 namespace
- [ ] 先保留未确认是否使用的旧 key
- [ ] 新增 key 命名保持可读、可追溯
- [ ] 动态文案优先使用插值参数而不是拼接字符串

## 四点五、0.6 历史改动复查结论

> 复查范围说明：这里只参考你确认过的提交边界，即从 `488efc1` 开始之后的中文提交历史；更早的提交不纳入本次迁移参考。

### 4.5.1 直接与 i18n 相关的历史提交

- [ ] `14ce30b feat(i18n): 添加多语言支持，实现中英文国际化`
- [ ] `332cfb4 feat(i18n): 添加新的国际化文本并更新相关组件`
- [ ] `8441438 feat(i18n): 添加图表模板名称和分组的国际化支持`
- [ ] `10a8317 feat(i18n): 添加报告模块的多语言支持`
- [ ] `50fc547 feat(国际化): 添加行数限制选项并更新国际化配置`

### 4.5.2 与 i18n 间接相关、需要一并关注的提交

- [ ] `4f41c04 refactor(MessageSnackbar): 优化消息提示组件样式和逻辑`
- [ ] `18c9f60 fix: 修复跨域请求时CORS问题，移除未使用的国际化代码`

### 4.5.3 0.6 中已实际接入过国际化的文件

#### 基础设施

- [ ] `package.json`
- [ ] `src/index.tsx`
- [ ] `src/i18n/index.ts`
- [ ] `src/i18n/locales/index.ts`
- [ ] `src/i18n/locales/en/*.json`
- [ ] `src/i18n/locales/zh/*.json`

#### 第一批高优先级页面

- [ ] `src/app/App.tsx`
- [ ] `src/views/DataFormulator.tsx`
- [ ] `src/views/About.tsx`
- [ ] `src/views/MessageSnackbar.tsx`
- [ ] `src/views/ModelSelectionDialog.tsx`
- [ ] `src/views/UnifiedDataUploadDialog.tsx`
- [ ] `src/views/ReportView.tsx`
- [ ] `src/views/VisualizationView.tsx`

#### 第二批已在 0.6 做过、0.7 可按需恢复的页面

- [ ] `src/views/AgentRulesDialog.tsx`
- [ ] `src/views/ChatDialog.tsx`
- [ ] `src/views/ConceptCard.tsx`
- [ ] `src/views/DBTableManager.tsx`
- [ ] `src/views/DataLoadingThread.tsx`
- [ ] `src/views/DataThread.tsx`
- [ ] `src/views/EncodingBox.tsx`
- [ ] `src/views/RefreshDataDialog.tsx`
- [ ] `src/views/SelectableDataGrid.tsx`
- [ ] `src/views/EncodingShelfCard.tsx`
- [ ] `src/views/MultiTablePreview.tsx`

#### 图表名称 / 分组相关

- [ ] `src/components/ChartTemplates.tsx`
- [ ] `src/i18n/locales/en/chart.json`
- [ ] `src/i18n/locales/zh/chart.json`

#### Superset 相关文案

- [ ] `src/views/SupersetCatalog.tsx`
- [ ] `src/views/SupersetDashboards.tsx`

### 4.5.4 基于历史提交得出的迁移优先级

- [ ] P0：先恢复基础设施和最早一批已验证过的页面
- [ ] P1：优先恢复 `App`、`DataFormulator`、`About`、`MessageSnackbar`
- [ ] P1：优先恢复 `ModelSelectionDialog`、`UnifiedDataUploadDialog`、`ReportView`
- [ ] P2：再恢复 `VisualizationView`、`SelectableDataGrid`、`DataThread` 等深层页面
- [ ] P3：最后处理 `ChartTemplates`、Superset 文案和新增 0.7 页面

### 4.5.5 从历史记录中提炼的注意事项

- [ ] `MessageSnackbar` 既有国际化改动，也有结构重构，迁移时不要只拷字符串
- [ ] `ReportView` 在 0.6 中被多次修改，i18n 迁移时要连同报告多语言一起复查
- [ ] `UnifiedDataUploadDialog` 在 0.6 中多次触达，后续容易成为文案遗漏点
- [ ] `VisualizationView` 与 `ChartTemplates` 有图表名称/分组翻译，需确认 0.7 是否仍沿用同样展示方式
- [ ] `SupersetCatalog` / `SupersetDashboards` 在 0.6 后期有新增国际化条目，若 0.7 也要保留 Superset 功能，需要一并补齐

## 四点六、关键提交到 0.7 的落点映射

> 这一节是“最实用的对照表”：开发时优先按这里找 0.7 应该改哪些文件。

### 4.6.1 `14ce30b feat(i18n): 添加多语言支持，实现中英文国际化`

#### 0.6 关键文件

- [ ] `package.json`
- [ ] `src/index.tsx`
- [ ] `src/i18n/index.ts`
- [ ] `src/i18n/locales/**`
- [ ] `src/app/App.tsx`
- [ ] `src/views/DataFormulator.tsx`
- [ ] `src/views/About.tsx`
- [ ] `src/views/MessageSnackbar.tsx`

#### 0.7 目标文件

- [ ] `package.json`
- [ ] `src/index.tsx`
- [ ] `src/i18n/index.ts`
- [ ] `src/i18n/locales/**`
- [ ] `src/app/App.tsx`
- [ ] `src/views/DataFormulator.tsx`
- [ ] `src/views/About.tsx`
- [ ] `src/views/MessageSnackbar.tsx`

#### 迁移判断

- [ ] 这是 Phase 1 的起点提交，优先恢复依赖、初始化和首批页面接线
- [ ] 0.7 已有 `src/i18n/**` 骨架，但 `src/index.tsx` 仍未接线
- [ ] `App.tsx` 不能整文件覆盖，只能逐段迁移文案与 `t()`

### 4.6.2 `332cfb4 feat(i18n): 添加新的国际化文本并更新相关组件`

#### 0.6 关键文件

- [ ] `src/i18n/locales/en/*.json`
- [ ] `src/i18n/locales/zh/*.json`
- [ ] `src/views/UnifiedDataUploadDialog.tsx`
- [ ] `src/views/ModelSelectionDialog.tsx`
- [ ] `src/views/VisualizationView.tsx`
- [ ] `src/views/EncodingShelfCard.tsx`
- [ ] `src/views/MultiTablePreview.tsx`
- [ ] `src/views/MessageSnackbar.tsx`

#### 0.7 目标文件

- [ ] `src/i18n/locales/en/*.json`
- [ ] `src/i18n/locales/zh/*.json`
- [ ] `src/views/UnifiedDataUploadDialog.tsx`
- [ ] `src/views/ModelSelectionDialog.tsx`
- [ ] `src/views/VisualizationView.tsx`
- [ ] `src/views/EncodingShelfCard.tsx`
- [ ] `src/views/MultiTablePreview.tsx`
- [ ] `src/views/MessageSnackbar.tsx`

#### 迁移判断

- [ ] 这是“字典扩容 + 第二批页面铺量”提交
- [ ] 迁移时按文件逐个 cherry-pick 文案，不整文件回拷
- [ ] 如果 0.7 对应页面结构已变化，优先复用 key，再重接组件

### 4.6.3 `8441438 feat(i18n): 添加图表模板名称和分组的国际化支持`

#### 0.6 关键文件

- [ ] `src/components/ChartTemplates.tsx`
- [ ] `src/i18n/locales/en/chart.json`
- [ ] `src/i18n/locales/zh/chart.json`
- [ ] `src/views/VisualizationView.tsx`
- [ ] `src/views/ReportView.tsx`

#### 0.7 目标文件

- [ ] `src/components/ChartTemplates.tsx`
- [ ] `src/i18n/locales/en/chart.json`
- [ ] `src/i18n/locales/zh/chart.json`
- [ ] `src/views/VisualizationView.tsx`
- [ ] `src/views/ChartGallery.tsx`
- [ ] `src/app/chartRecommendation.ts`
- [ ] `src/lib/agents-chart/test-data/index.ts`

#### 迁移判断

- [ ] `chart.json` 中模板名称与分组 key 可高度复用
- [ ] `ChartTemplates.tsx` 在 0.7 架构已变化，必须按新实现重接，不能覆盖旧文件
- [ ] 0.7 新增 `ChartGallery`，图表名称/分组显示要一起纳入国际化

### 4.6.4 `10a8317 feat(i18n): 添加报告模块的多语言支持`

#### 0.6 关键文件

- [ ] `src/views/ReportView.tsx`
- [ ] `src/i18n/locales/en/common.json`
- [ ] `src/i18n/locales/zh/common.json`

#### 0.7 目标文件

- [ ] `src/views/ReportView.tsx`
- [ ] `src/i18n/locales/en/common.json`
- [ ] `src/i18n/locales/zh/common.json`
- [ ] `src/i18n/locales/en/navigation.json`
- [ ] `src/i18n/locales/zh/navigation.json`

#### 迁移判断

- [ ] 报告模块文案可复用 0.6 key 体系
- [ ] 迁移时只搬 UI 层字符串，不直接套用旧逻辑分支
- [ ] 如果 0.7 报告流程增加了新操作按钮或状态提示，需要补新 key

### 4.6.5 `50fc547 feat(国际化): 添加行数限制选项并更新国际化配置`

#### 0.6 关键文件

- [ ] `src/views/SupersetCatalog.tsx`
- [ ] `src/views/SupersetDashboards.tsx`
- [ ] `src/i18n/locales/en/common.json`
- [ ] `src/i18n/locales/zh/common.json`

#### 0.7 目标文件

- [ ] 如保留 Superset 功能：对应扩展目录下的 `SupersetCatalog.tsx`
- [ ] 如保留 Superset 功能：对应扩展目录下的 `SupersetDashboards.tsx`
- [ ] `src/i18n/locales/en/common.json`
- [ ] `src/i18n/locales/zh/common.json`

#### 迁移判断

- [ ] 当前官方 0.7 主树中没有 `Superset*.tsx`，这部分不属于上游直接落点
- [ ] 若后续合并你的 Superset 扩展，需要一起迁移对应文案
- [ ] 若当前只做纯 0.7 官方前端 i18n，可先跳过 TSX，保留 JSON 预留

### 4.6.6 建议执行顺序

- [ ] 先做 `14ce30b`：依赖、入口、基础页面接线
- [ ] 再做 `332cfb4`：第二批高频页面
- [ ] 再做 `10a8317`：报告模块
- [ ] 再做 `8441438`：图表模板/图库/图表类型显示
- [ ] 最后按是否保留 Superset 决定 `50fc547`

## 四点七、0.7 新增或明显增强、需要补充 i18n 的范围

> 这一节是“0.6 没有，但 0.7 有”的补充清单。迁移时不能只看旧提交，还要覆盖这些新增范围。

### 4.7.1 高优先级补充范围

- [ ] `src/index.tsx`
  - 0.7 未接 `import './i18n'`，这是所有国际化生效的前置条件
- [ ] `src/app/App.tsx`
  - 0.7 增加了 `Session` 保存/加载/导入导出、`Settings`、`Gallery`、`Exit Session`、外链 Tooltip、错误页文案
- [ ] `src/views/DataFormulator.tsx`
  - 0.7 首页引导、示例会话、loading/backdrop、入口按钮与说明文案明显增多
- [ ] `src/views/DataThread.tsx`
  - 0.7 线程/聊天/推荐/规则集成更多，属于文案密集区
- [ ] `src/views/ChatThreadView.tsx`
  - 0.7 新文件，空态、运行态、维度缩写、图片 alt 等需要新建 key
- [ ] `src/views/SimpleChartRecBox.tsx`
  - 0.7 新文件，Agent working、推荐区提示、按钮文案需要单独建词条
- [ ] `src/views/ModelSelectionDialog.tsx`
  - 虽然 0.6 已做过，但 0.7 功能更强，仍要重点复查
- [ ] `src/views/UnifiedDataUploadDialog.tsx`
  - 两版都存在，但 0.7 上传/工作区/身份相关提示更多，必须单独比对

### 4.7.2 中优先级补充范围

- [ ] `src/views/ChartGallery.tsx`
  - 0.7 新页面，需要补 `gallery` 相关文案
- [ ] `src/lib/agents-chart/test-data/index.ts`
  - 0.7 画廊分区标题和展示 label 来源之一
- [ ] `src/app/tokens.ts`
  - `Color Theme` 下的 palette name 是用户可见文案
- [ ] `src/app/chartRecommendation.ts`
  - 图表类型展示名若对用户可见，需要统一 i18n 策略
- [ ] `src/views/DataThreadCards.tsx`
  - 0.7 新抽层，若含按钮/Tooltip/标签，需要补 key
- [ ] `src/views/RefreshDataDialog.tsx`
  - 与 0.7 新的数据刷新逻辑一起复查提示文案

### 4.7.3 可延后范围

- [ ] `src/views/ChartRenderService.tsx`
  - 偏服务组件，用户可见文案很少
- [ ] `src/app/identity.ts`
  - 以逻辑为主，UI 暴露少
- [ ] `src/components/chartUtils.ts`
  - 工具层为主，暂不作为 Phase 1 重点

### 4.7.4 需要标记为“0.6 专有，0.7 不直接迁移”的范围

- [ ] `src/views/LoginView.tsx`
- [ ] `src/views/ConceptShelf.tsx`
- [ ] `src/views/SupersetCatalog.tsx`
- [ ] `src/views/SupersetDashboards.tsx`
- [ ] `src/views/SupersetPanel.tsx`

> 说明：这些页面在当前官方 0.7 主树里不存在或不在主路径下，不能默认作为 Phase 1 的直接迁移目标。

## 五、按阶段执行的待办

### 5.1 Step 1：跑通最小骨架

- [ ] 安装依赖
- [ ] 接通 `src/index.tsx`
- [ ] 启动项目确认不报错
- [ ] 确认默认语言逻辑符合预期
- [ ] 确认切换语言后页面能刷新显示

### 5.2 Step 2：优先翻壳层 UI

#### 第一批文件

- [ ] `src/app/App.tsx`
- [ ] `src/views/DataFormulator.tsx`
- [ ] `src/views/About.tsx`
- [ ] `src/views/MessageSnackbar.tsx`
- [ ] `src/views/ModelSelectionDialog.tsx`
- [ ] `src/views/UnifiedDataUploadDialog.tsx`

#### 第一批要覆盖的文案类型

- [ ] 菜单文字
- [ ] 按钮文字
- [ ] Tooltip
- [ ] 对话框标题
- [ ] 错误提示 / 成功提示
- [ ] 空状态文案
- [ ] 导航入口文案

### 5.3 Step 3：补高频交互模块

#### 第二批文件

- [ ] `src/views/ReportView.tsx`
- [ ] `src/views/ChartGallery.tsx`
- [ ] `src/views/RefreshDataDialog.tsx`
- [ ] `src/views/TableSelectionView.tsx`
- [ ] `src/views/VisualizationView.tsx`
- [ ] `src/views/EncodingShelfCard.tsx`
- [ ] `src/views/MultiTablePreview.tsx`

#### 第二批检查点

- [ ] 上传流程按钮与提示已翻译
- [ ] 模型选择与状态提示已翻译
- [ ] 图库入口和说明文案已翻译
- [ ] 配置/刷新类对话框已翻译

### 5.4 Step 4：处理深层交互页面

- [ ] `src/views/DataView.tsx`
- [ ] `src/views/SelectableDataGrid.tsx`
- [ ] `src/views/ChatDialog.tsx`
- [ ] `src/views/ChatThreadView.tsx`
- [ ] `src/views/DataThreadCards.tsx`
- [ ] `src/views/SimpleChartRecBox.tsx`
- [ ] `src/views/DataThread.tsx`
- [ ] `src/views/DataLoadingThread.tsx`
- [ ] `src/views/EncodingBox.tsx`
- [ ] `src/views/ConceptCard.tsx`
- [ ] `src/views/AgentRulesDialog.tsx`
- [ ] `src/views/DBTableManager.tsx`

### 5.5 Step 5：统一清理

- [ ] 清理重复翻译 key
- [ ] 清理明显未使用 key
- [ ] 统一相同语义文案表述
- [ ] 检查英文、中文命名是否一致
- [ ] 整理需要保留英文原文的场景

## 六、重点文件逐项检查

### 6.1 `src/app/App.tsx`

- [ ] Session 菜单已翻译
- [ ] Save / Load / Export / Import 相关文案已翻译
- [ ] Settings 面板文案已翻译
- [ ] About / App / Gallery 导航已翻译
- [ ] Tooltip 与 `aria-label` 已翻译
- [ ] Snackbar 消息调用已改为可翻译形式

### 6.2 `src/views/DataFormulator.tsx`

- [ ] 首页标题与说明已翻译
- [ ] 空状态引导文案已翻译
- [ ] 示例入口文案已翻译
- [ ] 模型推荐提示已翻译

### 6.3 `src/views/About.tsx`

- [ ] 静态介绍文案已翻译
- [ ] 外链入口提示已翻译
- [ ] 页面段落文案已翻译

### 6.4 `src/views/UnifiedDataUploadDialog.tsx`

- [ ] 上传页签文案已翻译
- [ ] 数据源选择提示已翻译
- [ ] 校验错误提示已翻译

### 6.5 `src/views/ModelSelectionDialog.tsx`

- [ ] 模型名称展示策略已确认
- [ ] 用户可见状态文案已翻译
- [ ] 内部状态值未被误翻译

### 6.6 `src/views/ReportView.tsx`

- [ ] 报告模块文案已翻译
- [ ] 执行摘要 / 标题 / 操作文案已翻译
- [ ] 与报告多语言能力相关的旧改动已复查

### 6.7 `src/views/VisualizationView.tsx`

- [ ] 图表名称展示文案已翻译
- [ ] 图表模板分组文案已翻译
- [ ] 没有误翻译内部图表 spec / 逻辑字段

### 6.8 `src/views/UnifiedDataUploadDialog.tsx`

- [ ] 已对照历史提交复查新增文案点
- [ ] 上传流程、拖拽、错误提示文案已翻译
- [ ] 数据源入口、切换入口文案已翻译

### 6.9 `src/views/SupersetCatalog.tsx` / `src/views/SupersetDashboards.tsx`

- [ ] 如保留 Superset 功能，则补齐 0.6 后期新增国际化文案
- [ ] 工具提示、行数限制、筛选/加载类文案已复查

## 七、代码实现注意事项

- [ ] 只翻译“展示给用户看的文案”
- [ ] 不翻译逻辑值、状态值、枚举值、后端协议字段
- [ ] 模板字符串改为 `t('key', { ...params })`
- [ ] 不在一个提交里混入无关重构
- [ ] 一次只改一小批文件，便于回滚和 review
- [ ] 改完一个页面就立刻人工验证

## 八、验证清单

### 8.1 功能验证

- [ ] 默认英文显示正常
- [ ] 切换中文后显示正常
- [ ] 刷新页面后语言偏好可保留
- [ ] 不因翻译导致页面报错
- [ ] 不因翻译导致按钮功能失效
- [ ] 不因翻译导致会话保存/加载异常
- [ ] 不因翻译导致模型相关逻辑异常

### 8.2 页面走查

- [ ] 首页
- [ ] About
- [ ] Gallery
- [ ] Session 菜单
- [ ] Settings 对话框
- [ ] 上传弹窗
- [ ] 模型选择弹窗
- [ ] 报告页
- [ ] 数据页
- [ ] 聊天页

### 8.3 回归关注点

- [ ] 语言切换后没有残留明显英文
- [ ] Tooltip 与空状态文案没有遗漏
- [ ] Snackbar 消息格式正确
- [ ] 插值变量显示正确
- [ ] 复数、数量、日期类文案没有明显错误

## 九、阻塞项记录

> 有问题就补在这里，便于后续回看。

| 日期 | 文件/模块 | 问题描述 | 当前判断 | 是否阻塞 |
|------|-----------|----------|----------|----------|
| 待补充 | 待补充 | 待补充 | 待补充 | 否 |

## 十、待确认问题

- [ ] 是否需要在 UI 中提供显式语言切换入口
- [ ] 是否保留浏览器自动探测语言
- [ ] 是否需要把 message 文案进一步统一封装
- [ ] `About` 页面中的专有名词哪些保留英文
- [ ] 模型名称、图表类型名称是否保持英文展示
- [ ] 后续是否需要抽离“翻译 key 命名规范”
- [ ] `ChartGallery` 是否面向终端用户；若是，则提前纳入 Phase 1
- [ ] 图表类型名称是否与 `ChartTemplates` / `chartRecommendation` 共用同一套 key
- [ ] `Session`、`Settings`、`DataThread` 是否需要拆独立 namespace
- [ ] Superset 相关页面本轮是否纳入 0.7 迁移范围

## 十一、提交建议

### 建议提交粒度

- [ ] 提交 1：依赖 + `i18n` 初始化接线
- [ ] 提交 2：`App.tsx` + `DataFormulator.tsx`
- [ ] 提交 3：`About.tsx` + `MessageSnackbar.tsx`
- [ ] 提交 4：上传 / 模型 / 图库相关页面
- [ ] 提交 5：深层交互页面
- [ ] 提交 6：清理与统一

### 提交时自查

- [ ] 每个提交都可独立运行
- [ ] 每个提交都只做一类事情
- [ ] 没有误改内部逻辑字符串
- [ ] 没有混入无关格式化噪音

## 十二、开发日志

### 记录模板

```md
#### YYYY-MM-DD

- 完成：
- 修改文件：
- 新增 key：
- 遇到问题：
- 下一步：
```

### 本轮记录

#### 2026-03-20

- 完成：创建 Phase 1 i18n 开工清单文档
- 修改文件：`docs/Phase1-i18n-开工清单.md`
- 新增 key：无
- 遇到问题：无
- 下一步：从依赖接线和 `src/index.tsx` 初始化开始

#### 2026-03-20（历史复查补充）

- 完成：按 `488efc1` 之后的中文提交范围复查 0.6 历史国际化改动
- 修改文件：`docs/Phase1-i18n-开工清单.md`
- 新增 key：无
- 遇到问题：`0.6` 实际触达页面比初版清单更多，后续迁移需按优先级分批恢复
- 下一步：优先对照 `14ce30b / 332cfb4 / 8441438 / 10a8317 / 50fc547` 这几次提交梳理 0.7 的落点

#### 2026-03-20（0.7 对照补充）

- 完成：补充“关键提交 -> 0.7 落点映射”与“0.7 新增/增强功能的 i18n 补充范围”
- 修改文件：`docs/Phase1-i18n-开工清单.md`
- 新增 key：无
- 遇到问题：0.7 有一批 0.6 不存在的新页面和新交互，不能只按旧提交回放迁移
- 下一步：优先细化 `App.tsx`、`DataFormulator.tsx`、`DataThread.tsx`、`ChartGallery.tsx` 的 key 规划

