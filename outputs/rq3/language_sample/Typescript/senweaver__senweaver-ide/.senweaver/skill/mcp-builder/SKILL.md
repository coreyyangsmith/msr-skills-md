---
name: mcp-builder
description: "MCP服务器开发：FastMCP/TypeScript SDK、工具设计、外部API集成。关键词：MCP、MCP服务器、MCP工具、集成外部API、创建插件、Model Context Protocol"
---

# MCP 服务器开发指南

## 概述

MCP (Model Context Protocol) 服务器使 LLM 能通过精心设计的工具与外部服务交互。服务器质量取决于它能多好地帮助 LLM 完成真实世界的任务。

---

## 开发流程

### 阶段 1：调研与规划

#### 1.1 理解现代 MCP 设计

**API 覆盖 vs 工作流工具:**
平衡全面的 API 端点覆盖与专业化工作流工具。不确定时优先选择全面覆盖。

**工具命名与可发现性:**
清晰、描述性的名称帮助 Agent 快速找到正确工具。使用一致前缀和动作导向命名：
```
github_create_issue
github_list_repos
slack_send_message
```

**上下文管理:**
设计工具返回聚焦、相关的数据。支持过滤/分页。

**可操作的错误信息:**
错误信息应引导 Agent 找到解决方案，提供具体建议和下一步操作。

#### 1.2 学习 MCP 协议

关键概念：
- **传输机制**: Streamable HTTP（远程）、stdio（本地）
- **工具定义**: 输入 Schema、输出 Schema、描述
- **资源与提示**: 静态数据暴露和提示模板

MCP 规范文档: `https://modelcontextprotocol.io/sitemap.xml`

#### 1.3 选择技术栈

**推荐**: TypeScript（SDK 支持好、类型安全、AI 生成代码质量高）

| 语言 | 框架 | 适用场景 |
|------|------|---------|
| TypeScript | MCP SDK | 远程服务器、复杂集成 |
| Python | FastMCP | 快速原型、数据处理 |

#### 1.4 规划实现

1. 审查目标服务 API 文档
2. 识别关键端点、认证要求、数据模型
3. 列出要实现的工具，从最常用操作开始

---

### 阶段 2：实现

#### 2.1 项目结构

**TypeScript:**
```
my-mcp-server/
├── src/
│   ├── index.ts          # 入口点
│   ├── tools/            # 工具实现
│   │   ├── create.ts
│   │   ├── read.ts
│   │   └── update.ts
│   ├── client.ts         # API 客户端
│   └── utils.ts          # 工具函数
├── package.json
├── tsconfig.json
└── README.md
```

**Python:**
```
my-mcp-server/
├── server.py             # 入口点
├── tools/                # 工具实现
├── client.py             # API 客户端
├── utils.py              # 工具函数
├── pyproject.toml
└── README.md
```

#### 2.2 核心基础设施

创建共享工具：
- API 客户端（含认证）
- 错误处理辅助函数
- 响应格式化（JSON/Markdown）
- 分页支持

#### 2.3 实现工具

每个工具需要：

**输入 Schema:**
```typescript
// TypeScript - 使用 Zod
const schema = z.object({
  query: z.string().describe("搜索查询"),
  limit: z.number().optional().default(10).describe("返回结果数量"),
});
```

```python
# Python - 使用 Pydantic
class SearchInput(BaseModel):
    query: str = Field(description="搜索查询")
    limit: int = Field(default=10, description="返回结果数量")
```

**工具描述:**
- 简洁的功能摘要
- 参数描述
- 返回类型说明

**实现要点:**
- Async/await 处理 I/O
- 正确的错误处理和可操作错误信息
- 支持分页
- 返回文本内容和结构化数据

**注解:**
```typescript
annotations: {
  readOnlyHint: true,      // 只读操作
  destructiveHint: false,   // 非破坏性
  idempotentHint: true,     // 幂等
  openWorldHint: false,     // 封闭世界
}
```

---

### 阶段 3：审查与测试

#### 3.1 代码质量
- 无重复代码（DRY 原则）
- 一致的错误处理
- 完整的类型覆盖
- 清晰的工具描述

#### 3.2 构建与测试

**TypeScript:**
```bash
npm run build          # 验证编译
npx @modelcontextprotocol/inspector  # MCP Inspector 测试
```

**Python:**
```bash
python -m py_compile server.py  # 验证语法
# MCP Inspector 测试
```

---

### 阶段 4：评估

创建 10 个评估问题验证 MCP 服务器效果：

每个问题要求：
- **独立**: 不依赖其他问题
- **只读**: 只需非破坏性操作
- **复杂**: 需要多次工具调用
- **真实**: 基于实际用例
- **可验证**: 有明确可验证的答案
- **稳定**: 答案不会随时间变化

输出格式：
```xml
<evaluation>
  <qa_pair>
    <question>具体问题</question>
    <answer>明确答案</answer>
  </qa_pair>
</evaluation>
```

---

## 最佳实践

### 工具设计
- 每个工具做一件事，做好
- 名称清晰描述功能
- 参数有完整的描述和示例
- 返回足够但不过多的数据

### 错误处理
- 提供可操作的错误信息
- 包含错误码和建议的下一步
- 区分客户端错误和服务端错误

### 安全
- 不在代码中硬编码凭据
- 使用环境变量或配置文件
- 最小权限原则
- 验证所有输入

### 文档
- README 包含快速开始指南
- 每个工具有使用示例
- 记录认证要求和配置步骤
