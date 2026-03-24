---
name: pptx
description: "PPT演示文稿处理：创建/编辑幻灯片、演示设计、模板、备注。关键词：.pptx、PPT、幻灯片、演示文稿、deck、PowerPoint"
---

# PPTX 创建、编辑与分析

## 快速参考

| 任务 | 方法 |
|------|------|
| 读取/分析内容 | 使用内置 `read_document` 工具 |
| 创建新演示文稿 | 使用内置 `create_document`（推荐），或 pptxgenjs/python-pptx |
| 编辑现有演示文稿 | 使用内置 `edit_document`（推荐），或解包→编辑XML→重打包 |
| 转换格式 | 使用内置 `document_convert` 工具 |
| 提取幻灯片为图片 | 使用内置 `document_extract` 工具 |

## 使用内置工具（推荐）

### 创建演示文稿
```xml
<create_document>
<type>ppt</type>
<file_path>/path/to/output.pptx</file_path>
<document_data>{"slides":[{"title":"封面标题","subtitle":"副标题","layout":"title"},{"title":"内容页","bullets":["要点一","要点二","要点三"],"layout":"content"},{"title":"双栏页","content":["左栏内容","右栏内容"],"layout":"two_column"}]}</document_data>
</create_document>
```

**注意**: `type` 必须是 `"ppt"`（不是 `"pptx"`）。支持的 layout: `title`、`content`、`two_column`、`image`、`blank`。

### 读取演示文稿
```xml
<read_document>
<uri>/path/to/presentation.pptx</uri>
</read_document>
```

### 转换为 PDF 或图片
```xml
<document_convert>
<input_file>/path/to/presentation.pptx</input_file>
<output_path>/path/to/presentation.pdf</output_path>
<format>pdf</format>
</document_convert>
```

### 提取幻灯片为图片（用于视觉 QA）
```xml
<document_extract>
<input_file>/path/to/presentation.pptx</input_file>
<output_dir>/path/to/slides/</output_dir>
<extract_type>slides</extract_type>
</document_extract>
```

---

## 设计理念

**不要创建无聊的幻灯片。** 白底加项目符号不会让人印象深刻。

### 开始之前

- **选择大胆的配色方案**: 配色应专为此主题设计
- **主次分明**: 一种颜色占主导(60-70%)，1-2种辅助色，一种强调色
- **深浅对比**: 标题/结论页用深色背景，内容页用浅色（"三明治"结构）
- **统一视觉元素**: 选择一个特色元素在全部幻灯片中贯穿

### 推荐配色方案

| 主题 | 主色 | 辅色 | 强调色 |
|------|------|------|--------|
| **午夜商务** | `1E2761` (海军蓝) | `CADCFC` (冰蓝) | `FFFFFF` (白) |
| **森林苔藓** | `2C5F2D` (森林绿) | `97BC62` (苔藓绿) | `F5F5F5` (奶油白) |
| **珊瑚活力** | `F96167` (珊瑚红) | `F9E795` (金色) | `2F3C7E` (海军蓝) |
| **暖赭石** | `B85042` (赭石) | `E7E8D1` (沙色) | `A7BEAE` (鼠尾草) |
| **海洋渐变** | `065A82` (深蓝) | `1C7293` (青色) | `21295C` (午夜蓝) |
| **炭灰极简** | `36454F` (炭灰) | `F2F2F2` (灰白) | `212121` (黑) |
| **青色信赖** | `028090` (青色) | `00A896` (海泡绿) | `02C39A` (薄荷) |
| **浆果奶油** | `6D2E46` (浆果) | `A26769` (灰玫瑰) | `ECE2D0` (奶油) |
| **鼠尾草宁静** | `84B59F` (鼠尾草) | `69A297` (桉树) | `50808E` (石板) |
| **樱桃醒目** | `990011` (樱桃) | `FCF6F5` (灰白) | `2F3C7E` (海军蓝) |

### 每页幻灯片设计要点

**每页都需要视觉元素** — 图片、图表、图标或形状。纯文字页面毫无记忆点。

**布局选项:**
- 双栏（左文右图）
- 图标+文字行（彩色圆中图标 + 粗体标题 + 描述）
- 2×2 或 2×3 网格
- 半出血图片（占满左/右半边）+ 内容叠加

**数据展示:**
- 大数字标注（60-72pt 大数字 + 小标签）
- 对比列（前后对比、优劣对比）
- 时间线或流程图（编号步骤、箭头）

### 排版规范

**选择有个性的字体搭配**，不要默认 Arial：

| 标题字体 | 正文字体 |
|----------|----------|
| Georgia | Calibri |
| Arial Black | Arial |
| Cambria | Calibri |
| Trebuchet MS | Calibri |
| Palatino | Garamond |

| 元素 | 字号 |
|------|------|
| 页面标题 | 36-44pt 粗体 |
| 小节标题 | 20-24pt 粗体 |
| 正文 | 14-16pt |
| 注释 | 10-12pt 淡色 |

### 间距
- 最小边距 0.5 英寸
- 内容块间距 0.3-0.5 英寸
- 留白呼吸——不要填满每一寸

### 常见错误（避免）

- **不要重复相同布局** — 在幻灯片间变化栏数、卡片和标注
- **不要居中正文** — 正文左对齐；仅标题居中
- **不要忽略字号对比** — 标题 36pt+，正文 14-16pt
- **不要默认蓝色** — 选择反映具体主题的颜色
- **不要创建纯文字页** — 添加图片、图标、图表等视觉元素
- **绝不使用标题下划线** — 这是 AI 生成幻灯片的典型特征；用留白或背景色代替

---

## 使用 pptxgenjs 创建（从头创建）

```javascript
const pptxgen = require('pptxgenjs');
const pres = new pptxgen();

// 设置幻灯片尺寸（默认16:9）
pres.defineLayout({ name: 'CUSTOM', width: 13.333, height: 7.5 });
pres.layout = 'CUSTOM';

// 添加幻灯片
const slide = pres.addSlide();

// 标题
slide.addText('演示标题', {
  x: 0.5, y: 0.5, w: '90%', h: 1.5,
  fontSize: 44, bold: true, color: '1E2761',
  align: 'center'
});

// 正文
slide.addText('内容文本', {
  x: 0.5, y: 2.5, w: '90%', h: 4,
  fontSize: 16, color: '333333'
});

// 图片
slide.addImage({ path: 'image.png', x: 7, y: 1, w: 5, h: 4 });

// 形状
slide.addShape(pres.ShapeType.rect, {
  x: 0, y: 0, w: '100%', h: 0.5,
  fill: { color: '1E2761' }
});

pres.writeFile({ fileName: 'output.pptx' });
```

---

## 使用 python-pptx 编辑

```python
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor

prs = Presentation('template.pptx')

# 遍历幻灯片
for slide in prs.slides:
    for shape in slide.shapes:
        if shape.has_text_frame:
            for paragraph in shape.text_frame.paragraphs:
                for run in paragraph.runs:
                    print(run.text)

# 修改文本
slide = prs.slides[0]
for shape in slide.shapes:
    if shape.has_text_frame:
        shape.text_frame.paragraphs[0].runs[0].text = "新标题"

# 添加幻灯片
blank_layout = prs.slide_layouts[6]
new_slide = prs.slides.add_slide(blank_layout)

prs.save('output.pptx')
```

---

## QA 质量检查（必须执行）

**假设存在问题，你的任务是找到它们。**

首次渲染几乎不会完美。QA 是找 bug，不是确认没问题。

### 内容 QA
- 检查内容缺失、错别字、顺序错误
- 检查模板中的占位符残留文本

### 视觉 QA 检查清单
- 元素重叠（文字穿过形状、线条穿过文字）
- 文字溢出或被截断
- 装饰线位置与多行文字不匹配
- 元素间距过近（< 0.3 英寸）
- 间距不均匀
- 边距不足（< 0.5 英寸）
- 低对比度文字或图标
- 文本框过窄导致过度换行

### 验证循环
1. 生成幻灯片 → 转图片 → 检查
2. **列出发现的问题**
3. 修复问题
4. **重新验证受影响的幻灯片** — 一个修复常常引入新问题
5. 重复直到完整检查无新问题

**至少完成一个修复-验证循环才能宣告完成。**
