# React Statistics Dashboard

一个使用React最佳实践构建的现代化统计仪表板。

## 特性

### ✅ React最佳实践
- **组件化设计**: 单一职责原则，每个组件专注一个功能
- **性能优化**: 
  - `React.memo` - 避免不必要的重渲染
  - `useMemo` - 缓存计算结果
  - `useCallback` - 缓存回调函数
- **自定义Hooks**: 复用状态逻辑 (`useStatistics`)
- **正确的副作用处理**: 使用`useEffect`和清理函数

### 🎨 现代化UI
- 响应式设计（移动端和桌面端）
- 深色/浅色主题切换
- 平滑动画和过渡效果
- 卡片式布局

### 🌍 国际化
- 支持中文、英文、西班牙语
- 语言切换无需刷新页面

### 📊 数据可视化
- 折线图 - 每日货量趋势
- 柱状图 - 周环比对比
- 饼图 - 货物类型分布

## 技术栈

- **React 18** - 使用Hooks和函数组件
- **Chart.js** - 数据可视化
- **Vite** - 快速的构建工具
- **CSS3** - 现代化样式和动画

## 项目结构

```
react-dashboard/
├── index.html              # HTML入口
├── package.json            # 依赖配置
├── vite.config.js          # Vite配置
└── src/
    ├── main.jsx            # React入口
    ├── App.jsx             # 主应用组件
    ├── components/         # React组件
    │   ├── StatisticsDashboard.jsx  # 仪表板容器
    │   ├── DashboardHeader.jsx      # 头部组件
    │   ├── StatsCard.jsx            # 统计卡片
    │   └── ChartCard.jsx            # 图表卡片
    ├── hooks/              # 自定义Hooks
    │   └── useStatistics.js         # 数据获取Hook
    ├── utils/              # 工具函数
    │   ├── api.js                   # API调用
    │   └── formatters.js            # 数据格式化
    └── styles/             # 样式文件
        └── dashboard.css            # 主样式
```

## 安装和运行

### 1. 安装依赖
```bash
cd static/react-dashboard
npm install
```

### 2. 开发模式
```bash
npm run dev
```
访问: http://localhost:3000

### 3. 生产构建
```bash
npm run build
```

## React最佳实践应用

### 1. 组件组合
```jsx
// 使用组合而非继承
<StatisticsDashboard>
  <DashboardHeader />
  <StatsCard />
  <ChartCard />
</StatisticsDashboard>
```

### 2. 性能优化
```jsx
// React.memo 避免不必要的重渲染
const StatsCard = memo(({ title, value }) => {
  // ...
})

// useMemo 缓存计算结果
const stats = useMemo(() => {
  return calculateStats(data)
}, [data])

// useCallback 缓存回调函数
const handleRefresh = useCallback(() => {
  refetch()
}, [refetch])
```

### 3. 自定义Hooks
```jsx
// 复用状态逻辑
const { data, loading, error, refetch } = useStatistics(dateRange)
```

### 4. 副作用处理
```jsx
useEffect(() => {
  fetchData()
  
  // 清理函数防止内存泄漏
  return () => {
    cleanup()
  }
}, [dependencies])
```

## API集成

仪表板通过`/api/stats`端点获取数据：

```javascript
// 请求
GET /api/stats?start=2024-01-01&end=2024-01-31

// 响应
{
  "total_pieces": 100000,
  "total_vehicles": 5000,
  "pieces_trend": 5.2,
  "vehicles_trend": 3.1,
  "daily_stats": [...],
  "weekly_comparison": [...],
  "category_stats": [...]
}
```

## 主题支持

仪表板支持深色和浅色主题，使用CSS变量实现：

```css
[data-theme="light"] {
  --bg-color: #f5f5f5;
  --text-color: #333;
}

[data-theme="dark"] {
  --bg-color: #1a1a1a;
  --text-color: #fff;
}
```

## 响应式设计

- **桌面端** (>768px): 3列网格布局
- **平板** (768px): 2列网格布局
- **移动端** (<480px): 单列布局

## 浏览器兼容性

- Chrome/Edge (最新版)
- Firefox (最新版)
- Safari (最新版)

## 许可证

MIT
