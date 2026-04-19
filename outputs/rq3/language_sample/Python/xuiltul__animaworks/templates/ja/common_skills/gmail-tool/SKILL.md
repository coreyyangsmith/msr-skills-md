---
name: gmail-tool
description: >-
  Gmail連携ツール。未読メール確認・本文読み取り・下書き作成。OAuth2認証でGmail APIに直接アクセス。
  「Gmail」「メール」「未読」「下書き」「受信」
tags: [communication, gmail, email, external]
---

# Gmail ツール

GmailのメールをOAuth2で直接操作する外部ツール。

## 呼び出し方法

**Bash**: `animaworks-tool gmail <サブコマンド> [引数]` で実行

## アクション一覧

### unread — 未読メール一覧
```bash
animaworks-tool gmail unread [-n 20]
```

### read_body — メール本文読み取り
```bash
animaworks-tool gmail read MESSAGE_ID
```

### draft — 下書き作成
```bash
animaworks-tool gmail draft --to ADDR --subject SUBJ --body BODY [--thread-id TID]
```

## CLI使用法

```bash
animaworks-tool gmail unread [-n 20]
animaworks-tool gmail read MESSAGE_ID
animaworks-tool gmail draft --to ADDR --subject SUBJ --body BODY [--thread-id TID]
```

## 注意事項

- 初回使用時にOAuth2認証フローが必要
- credentials.json と token.json が ~/.animaworks/ に配置されること
