---
name: eval-harness
description: pass@kメトリクスでAIコード生成の品質を評価。Capability/Regression評価をサポート。
license: MIT
version: 1.1.0
triggers:
  - /eval
  - 機能評価
  - 回帰テスト
---

# Eval Harness

> **要約**: AIコード生成の品質を定量的に評価。pass@kメトリクスと複数の評価タイプをサポート。

## 📊 評価タイプ

### 1. Capability Eval (REQ-EH-001)

**WHEN** 新機能の品質評価が必要  
**DO** 以下のフォーマットで定義

```markdown
[CAPABILITY EVAL: <feature-name>]
Task: <達成タスク>
Success Criteria:
  - [ ] 基準1
  - [ ] 基準2
  - [ ] 基準3
Expected Output: <期待出力>
Test Command: <テストコマンド>
```

---

### 2. Regression Eval (REQ-EH-002)

**WHEN** 既存機能の品質維持を確認  
**DO** 以下のフォーマットで定義

```markdown
[REGRESSION EVAL: <feature-name>]
Baseline: <Git SHA / チェックポイント>
Tests:
  - test-1: PASS/FAIL
  - test-2: PASS/FAIL
Result: X/Y passed (previously Y/Y)
Regression: Yes/No
```

---

## 📈 pass@k Metrics (REQ-EH-003)

| メトリクス | 定義 | 用途 |
|-----------|------|------|
| **pass@1** | 初回試行成功率 | 基本信頼度 |
| **pass@3** | 3回中1回以上成功 | 一般ターゲット |
| **consecutive@3** | 3回連続成功 | クリティカルパス |

**計算**:
```
pass@1 = 成功数 / 試行数
pass@k = 1 - C(n-c, k) / C(n, k)
consecutive@3 = 連続成功シーケンス数 / 可能シーケンス数
```

**レポート例**:
```
📊 Eval Report: user-auth
━━━━━━━━━━━━━━━━━━━━
pass@1: 80% (8/10)
pass@3: 95% 
consecutive@3: 60%
━━━━━━━━━━━━━━━━━━━━
Status: ✅ Meets target
```

---

## 🔍 Grader Types (REQ-EH-004/005)

| タイプ | 説明 | 使用場面 |
|--------|------|---------|
| **Code-Based** | コマンド実行で判定 | 決定的な検証 |
| **Model-Based** | LLMで判定 | 自由形式の評価 |
| **Human** | 人手で判定 | 主観的品質評価 |

### Human Grader Template

```markdown
[HUMAN GRADE: <feature>]
Reviewer: @username
Checklist:
  - [ ] 仕様を満たしている
  - [ ] エッジケース考慮
  - [ ] API互換性維持
  - [ ] セキュリティ問題なし
Verdict: PASS/FAIL
Notes: [コメント]
```

---

## トレーサビリティ

- REQ-EH-001: Capability Eval Definition
- REQ-EH-002: Regression Eval Definition
- REQ-EH-003: pass@k Metrics
- REQ-EH-004: Grader Types
- REQ-EH-005: Human Grader Support
