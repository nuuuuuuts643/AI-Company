# P001 AI会社 基盤構築

## 概要
Claudeを秘書として、アイデアと指示を分類・管理するAI会社の基盤を作る

## 構成
```
ai-company/
├── inbox/
│   ├── raw-ideas.md        # 未整理のアイデア
│   ├── incubating-ideas.md # 育成中のアイデア
│   └── proposal-queue.md   # 提案待ち
├── projects/               # 進行中案件
├── dashboard/              # 会社状況
│   ├── active-projects.md
│   ├── next-actions.md
│   └── decisions.md
└── company/                # ルール・設定
```

## 運用フロー
1. 社長が入力
2. 秘書（Claude）が分類（Idea / Directive / Mixed）
3. 該当ファイルに格納
4. dashboardを更新

## ステータス
- [x] ファイル構造作成
- [x] 分類ルール整備
- [ ] 運用テスト
