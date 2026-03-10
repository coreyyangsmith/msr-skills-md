---
name: react-expert
description: "React 19开发：Server Components、hooks、状态管理、性能优化、Suspense。关键词：React、组件、hooks、useState、useEffect、Next.js、Zustand、Redux、前端组件"
---

# React 专家

深度掌握 React 19 和现代 React 生态，构建高性能、可访问的生产级应用。

## 使用内置工具

- **`read_file`** — 阅读组件代码，理解组件树和数据流
- **`edit_file`** — 修改组件、添加 hooks、优化渲染
- **`run_command`** — `npm run build`（检查构建）、`npx tsc --noEmit`（类型检查）
- **`browser_action`** — 使用内置浏览器预览和测试 React 应用
- **`grep`** — 搜索组件使用、状态管理模式、依赖关系

## 组件设计模式

### 函数组件 + TypeScript
```tsx
interface UserCardProps {
  user: User;
  onEdit?: (id: string) => void;
  className?: string;
}

function UserCard({ user, onEdit, className }: UserCardProps) {
  return (
    <div className={className}>
      <h3>{user.name}</h3>
      <p>{user.email}</p>
      {onEdit && (
        <button onClick={() => onEdit(user.id)}>编辑</button>
      )}
    </div>
  );
}
```

### 复合组件模式
```tsx
// 灵活的 API，让消费者控制布局
function Select({ children, value, onChange }: SelectProps) {
  return (
    <SelectContext.Provider value={{ value, onChange }}>
      <div role="listbox">{children}</div>
    </SelectContext.Provider>
  );
}

Select.Option = function Option({ value, children }: OptionProps) {
  const ctx = useContext(SelectContext);
  return (
    <div
      role="option"
      aria-selected={ctx.value === value}
      onClick={() => ctx.onChange(value)}
    >
      {children}
    </div>
  );
};

// 使用
<Select value={selected} onChange={setSelected}>
  <Select.Option value="a">选项 A</Select.Option>
  <Select.Option value="b">选项 B</Select.Option>
</Select>
```

### 自定义 Hook
```tsx
// 封装数据获取逻辑
function useUser(id: string) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    fetchUser(id)
      .then(data => { if (!cancelled) setUser(data); })
      .catch(err => { if (!cancelled) setError(err); })
      .finally(() => { if (!cancelled) setLoading(false); });

    return () => { cancelled = true; };
  }, [id]);

  return { user, loading, error };
}

// 封装 localStorage
function useLocalStorage<T>(key: string, initialValue: T) {
  const [value, setValue] = useState<T>(() => {
    try {
      const stored = localStorage.getItem(key);
      return stored ? JSON.parse(stored) : initialValue;
    } catch {
      return initialValue;
    }
  });

  useEffect(() => {
    localStorage.setItem(key, JSON.stringify(value));
  }, [key, value]);

  return [value, setValue] as const;
}
```

## 状态管理决策树

```
状态的作用范围是？
├── 单个组件 → useState / useReducer
├── 父子组件共享 → 提升状态 + props
├── 跨多层组件 → useContext
├── 全局应用状态 → Zustand / Redux Toolkit
└── 服务端数据 → TanStack Query / SWR
```

### Zustand（推荐的轻量方案）
```tsx
import { create } from 'zustand';

interface AuthStore {
  user: User | null;
  login: (credentials: Credentials) => Promise<void>;
  logout: () => void;
}

const useAuthStore = create<AuthStore>((set) => ({
  user: null,
  login: async (credentials) => {
    const user = await authApi.login(credentials);
    set({ user });
  },
  logout: () => set({ user: null }),
}));

// 使用（自动细粒度订阅）
function Header() {
  const user = useAuthStore(state => state.user);
  return <span>{user?.name}</span>;
}
```

### TanStack Query（服务端状态）
```tsx
function UserList() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['users'],
    queryFn: () => fetch('/api/users').then(r => r.json()),
    staleTime: 5 * 60 * 1000, // 5分钟内不重新获取
  });

  if (isLoading) return <Spinner />;
  if (error) return <ErrorMessage error={error} />;

  return (
    <ul>
      {data.map(user => <UserItem key={user.id} user={user} />)}
    </ul>
  );
}
```

## 性能优化

### React.memo（避免不必要的重渲染）
```tsx
// 只有当 props 变化时才重渲染
const ExpensiveList = React.memo(function ExpensiveList({ items }: Props) {
  return items.map(item => <Item key={item.id} {...item} />);
});
```

### useMemo / useCallback
```tsx
function SearchResults({ query, filters }: Props) {
  // 缓存计算结果
  const filteredResults = useMemo(
    () => results.filter(r => matchesFilters(r, filters)),
    [results, filters]
  );

  // 缓存回调引用（传给 memo 化的子组件时）
  const handleSelect = useCallback((id: string) => {
    setSelected(id);
  }, []);

  return <List items={filteredResults} onSelect={handleSelect} />;
}
```

### 虚拟化长列表
```tsx
import { useVirtualizer } from '@tanstack/react-virtual';

function VirtualList({ items }: { items: Item[] }) {
  const parentRef = useRef<HTMLDivElement>(null);
  const virtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 50,
  });

  return (
    <div ref={parentRef} style={{ height: '400px', overflow: 'auto' }}>
      <div style={{ height: `${virtualizer.getTotalSize()}px`, position: 'relative' }}>
        {virtualizer.getVirtualItems().map(virtualRow => (
          <div
            key={virtualRow.key}
            style={{
              position: 'absolute',
              top: 0,
              transform: `translateY(${virtualRow.start}px)`,
              height: `${virtualRow.size}px`,
            }}
          >
            {items[virtualRow.index].name}
          </div>
        ))}
      </div>
    </div>
  );
}
```

### 代码分割
```tsx
// 路由级代码分割
const Dashboard = lazy(() => import('./pages/Dashboard'));
const Settings = lazy(() => import('./pages/Settings'));

function App() {
  return (
    <Suspense fallback={<PageSkeleton />}>
      <Routes>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/settings" element={<Settings />} />
      </Routes>
    </Suspense>
  );
}
```

## 错误边界
```tsx
class ErrorBoundary extends React.Component<
  { fallback: ReactNode; children: ReactNode },
  { hasError: boolean; error?: Error }
> {
  state = { hasError: false, error: undefined };

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('ErrorBoundary caught:', error, info);
  }

  render() {
    if (this.state.hasError) return this.props.fallback;
    return this.props.children;
  }
}

// 使用
<ErrorBoundary fallback={<p>出错了，请刷新页面</p>}>
  <UserProfile />
</ErrorBoundary>
```

## 无障碍 (a11y) 要点

| 要点 | 实践 |
|------|------|
| 语义化 HTML | 使用 `<button>` 而非 `<div onClick>` |
| ARIA 属性 | `aria-label`、`aria-expanded`、`role` |
| 键盘导航 | 所有交互元素可用 Tab/Enter 操作 |
| 焦点管理 | 模态框打开时聚焦、关闭时恢复 |
| 颜色对比度 | WCAG AA 最低 4.5:1 |
| 图片替代文本 | 所有 `<img>` 有 `alt` 属性 |

## React 19 新特性

### use() Hook
```tsx
// 在组件中读取 Promise（替代 useEffect + useState）
function UserProfile({ userPromise }: { userPromise: Promise<User> }) {
  const user = use(userPromise);
  return <h1>{user.name}</h1>;
}
```

### useActionState（表单处理）
```tsx
function LoginForm() {
  const [state, formAction, isPending] = useActionState(
    async (prevState, formData: FormData) => {
      const email = formData.get('email') as string;
      const password = formData.get('password') as string;
      try {
        await login(email, password);
        return { success: true };
      } catch {
        return { success: false, error: '登录失败' };
      }
    },
    { success: false }
  );

  return (
    <form action={formAction}>
      <input name="email" type="email" />
      <input name="password" type="password" />
      <button disabled={isPending}>
        {isPending ? '登录中...' : '登录'}
      </button>
      {state.error && <p className="error">{state.error}</p>}
    </form>
  );
}
```

## 编码原则

### 必须做
- 使用 TypeScript strict 模式
- 实现错误边界
- 正确使用 `key` 属性（稳定、唯一的标识符）
- 清理 useEffect 副作用（返回清理函数）
- 语义化 HTML + ARIA 无障碍
- 传递回调/对象给 memo 化子组件时使用 useMemo/useCallback
- 使用 Suspense 包裹异步操作

### 绝不做
- 直接修改 state
- 动态列表用数组索引作为 key
- 在 JSX 中内联创建函数/对象（导致重渲染）
- 忘记 useEffect 清理（内存泄漏）
- 忽略 React strict mode 警告
- 生产环境不用错误边界

## 知识参考

React 19、Server Components、use() hook、Suspense、TypeScript、TanStack Query、Zustand、Redux Toolkit、React Router、React Testing Library、Vitest/Jest、Next.js App Router、无障碍（WCAG）
