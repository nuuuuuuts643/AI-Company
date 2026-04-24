# 帰宅後チェックリスト（2026-04-24更新）

## すぐやること（順番通りに）

```bash
cd ~/ai-company

# 1. 全変更をpush（エージェント停止・AdSenseコード・CLAUDE.md整理等）
git add -A && git commit -m "fix: エージェント全停止・状態整理" && git push

# 2. Notion進捗更新
python3 scripts/notion_sync.py

# 3. auto-push設定（これで外出先からも自動デプロイ可能に）
brew install fswatch
chmod +x scripts/auto-push.sh
cp scripts/com.aicompany.autopush.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.aicompany.autopush.plist

# 4. AI要約を有効化（重要）
aws lambda update-function-configuration \
  --function-name p003-processor \
  --region ap-northeast-1 \
  --environment 'Variables={S3_BUCKET=p003-news-946554699567,TABLE_NAME=p003-topics,REGION=ap-northeast-1,SITE_URL=https://flotopic.com,ANTHROPIC_API_KEY=<ここにAPIキー>}'

# 5. P002動作確認
cd ~/ai-company/projects/P002-flutter-game
flutter pub get && flutter run
```

## 状況サマリー
- P003 Flotopic: 本番稼働中（AI要約だけ未動作）
- P001/P004/P005: 保留中（インフラあり）
- エージェント: 全スケジュール停止済み
- AdSense: 申請済み・審査待ち
- auto-push: スクリプト作成済み・LaunchAgent未登録
