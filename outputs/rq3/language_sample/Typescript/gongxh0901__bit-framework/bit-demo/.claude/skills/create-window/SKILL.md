---
name: create-window
description: 创建符合项目规范的 UI 窗口类，自动读取 FGUI 工程 XML 获取节点结构
user-invocable: true
argument-hint: [窗口名] [FGUI包名] [窗口组名]
allowed-tools: Read(*), Write(*), Glob(*), Grep(*)
---

# 创建 UI 窗口

根据 FGUI 工程中的界面定义，生成符合项目规范的 Window 子类。

## 参数解析
- `$ARGUMENTS[0]` = 窗口类名（如 ShopWindow）
- `$ARGUMENTS[1]` = FGUI 包名（如 Shop）
- `$ARGUMENTS[2]` = 窗口组名（默认 "Window"）

## 执行步骤

### 1. 读取 FGUI 节点结构
读取 XML 文件：`FguiCreator3.8/assets/$ARGUMENTS[1]/$ARGUMENTS[0].xml`

从 `<displayList>` 中提取：
- 所有节点的 `name` 和类型
- 识别按钮节点（含 `<Button/>` 扩展的 `<component>`）
- 识别文本节点（`<text>`）
- 识别图片节点（`<image>`）
- 识别 controller 和 transition

### 2. 参考现有代码风格
读取以下文件了解项目代码风格：
- `assets/script/header.ts` — import 风格
- 在 `assets/script/` 下找 1-2 个现有 Window 文件参考

### 3. 生成窗口代码

```typescript
import { UI, FGUI, CORE } from "相对路径/header";
const { uiclass, uiclick, uiprop } = UI._uidecorator;

@uiclass("窗口组名", "FGUI包名", "窗口名")
export class 窗口名 extends UI.Window {
    // @uiprop 属性（根据 XML 节点生成）
    @uiprop private _节点名!: FGUI.类型;

    protected onInit(): void {
        this.adapterType = UI.AdapterType.Bang;
        this.type = UI.WindowType.Normal;
    }

    protected onShow(_userdata?: unknown): void {
    }

    protected onClose(): void {
    }

    // @uiclick 方法（根据按钮节点生成）
    @uiclick
    private onXxx(): void {
    }
}
```

### 4. 确定保存路径
- 根据窗口组名和包名确定合适的目录
- 如果不确定，询问用户保存位置

### 5. 节点类型映射规则
| XML 节点 | 代码类型 |
|----------|---------|
| `<text>` | `FGUI.GTextField` |
| `<graph>` | `FGUI.GGraph` |
| `<image>` | `FGUI.GImage` |
| `<component>` + `<Button/>` | `FGUI.GButton` |
| `<component>` + `<Label/>` | `FGUI.GLabel` |
| `<component>` + `<Slider/>` | `FGUI.GSlider` |
| `<component>` + `<ProgressBar/>` | `FGUI.GProgressBar` |
| `<component>` + `<ComboBox/>` | `FGUI.GComboBox` |
| `<component>`（其他） | `FGUI.GComponent` |
