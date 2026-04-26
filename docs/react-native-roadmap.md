# Flotopic React Native 移行ロードマップ

> 作成日: 2026-04-22  
> 対象プロジェクト: P003 Flotopic (flotopic.com)  
> ステータス: 計画段階（PWAフェーズ稼働中）

---

## 概要

Flotopicの現在のバックエンド構成（S3 + CloudFront + Lambda + DynamoDB）は、設計段階からAPIとWebが分離されているため、**モバイルアプリのバックエンドとしてそのまま流用できる**。追加インフラなしにReact Native対応が可能な点は、コスト面・スピード面で大きな優位性となる。

移行は段階的に実施する。現時点ではPWAとして提供し、PVが一定規模に達した段階でReact Native（Expo）への移行を進める。

---

## Section 1: なぜReact Nativeか

### iOS / Android を一つのコードベースでカバー

ネイティブアプリをSwift / Kotlinでそれぞれ開発するとリソースが2倍以上かかる。React Nativeは単一コードベースで両OSに対応でき、少人数（またはAIチーム）での開発に適している。

### 既存ロジックの流用

現在の `app.js` に実装されているAPI呼び出し、Google OAuth連携、お気に入り管理（LocalStorage）は、React Native上でほぼそのまま使用可能。書き直しが必要なのは**UIコンポーネント層のみ**。

### Expoによるストア申請の簡略化

[Expo](https://expo.dev/) を使うことで、ビルド・署名・ストア申請がCLIから完結する。XcodeやAndroid Studioの複雑なセットアップを省略でき、AIエージェントによる自動化とも相性が良い。

---

## Section 2: バックエンドの互換性

| コンポーネント | 現在の実装 | モバイル対応方法 |
|---|---|---|
| APIエンドポイント | Lambda Function URLs | そのままモバイルAPIとして使用（変更不要） |
| 認証 | Google OAuth（ブラウザリダイレクト） | `expo-auth-session` に差し替え |
| データ | DynamoDB（topics / comments / analytics） | スキーマ変更不要 |
| プッシュ通知 | 未実装 | AWS SNS + Expo Push Notifications に移行 |
| 広告 | 忍者AdMax（Web） | AdMob（`react-native-google-mobile-ads`）に切り替え |

Lambda Function URLsは認証なしのHTTPSエンドポイントとして公開されているため、モバイルアプリからも同じURLで呼び出せる。バックエンドコストの増加は**ゼロ**。

---

## Section 3: 移行ステップ（フェーズ別）

| フェーズ | 移行条件 | 主な作業内容 |
|---|---|---|
| **PWA**（現在） | 今すぐ | ホーム画面追加対応、Service Worker によるオフラインキャッシュ（実装済み） |
| **RN α** | 月5,000 PV超 | Expo プロジェクト作成、Lambda API連携、Google OAuth移植、お気に入り機能移植 |
| **RN β** | 月20,000 PV超 | App Store / Google Play 申請、プッシュ通知（AWS SNS連携）、AdMob広告組み込み |
| **RN 正式** | 月50,000 PV超 | プレミアムフィルター、サブスク課金（RevenueCat）、パーソナライズ推薦 |

### RN α フェーズの具体的な作業

```bash
# Expoプロジェクト作成
npx create-expo-app flotopic-app --template blank-typescript

# 主要パッケージのインストール
npx expo install expo-auth-session expo-web-browser
npx expo install @react-native-async-storage/async-storage
npx expo install expo-notifications
```

APIエンドポイントは現行のまま使用できるため、`fetch()` 呼び出しをそのままコピーして動作する。

---

## Section 4: 推定コスト

| 項目 | コスト | 備考 |
|---|---|---|
| Expo | 無料〜$99/月 | 無料プランでビルド月30回まで |
| Apple Developer Account | $99 / 年 | App Store申請に必須 |
| Google Play Developer | $25 / 一回 | 登録料のみ |
| AWS追加コスト | **なし** | 既存LambdaをそのままAPIとして流用 |
| AdMob | 収益分配のみ | 出費なし、月$100〜の収益見込み（RN β以降） |

**初期投資の目安: 約$124（Apple + Google）**  
既存インフラを流用するため、通常のモバイルアプリ開発と比べて初期コストを大幅に抑えられる。

---

## Section 5: 現在できる準備

移行に備えて、PWAフェーズのうちに以下を整備しておく。

### APIレスポンス形式の統一

現在の `topics.json` 形式（`{ topic, articles[], summary, score }` 構造）はReact Nativeでそのまま使用可能。変更は不要だが、**バージョニング**（`/v1/topics`）を追加しておくと将来の破壊的変更に対応しやすい。

### Google OAuth: バンドル識別子の追加

現在のGoogle Cloud ConsoleにiOS / Androidの認証情報を追加する必要がある。

1. [Google Cloud Console](https://console.cloud.google.com/) → 認証情報 → OAuthクライアント
2. 「iOSアプリ」を追加 → Bundle ID: `com.flotopic.app`
3. 「Androidアプリ」を追加 → パッケージ名: `com.flotopic.app`

### アイコン・スプラッシュ素材の準備

`docs/ICONS-NEEDED.md` を参照。最低限必要な素材：

- アプリアイコン: 1024×1024px（PNG、透過なし）
- スプラッシュ画面: 1284×2778px（iPhone 14 Pro Max基準）
- 通知アイコン: 96×96px（Android用、白抜きシルエット）

---

## Section 6: 競合との差別化

### 既存ニュースアプリとの比較

| サービス | 強み | Flotopicとの違い |
|---|---|---|
| SmartNews | 記事量・速報性 | トレンドの「盛り上がり」可視化がない |
| グノシー | パーソナライズ推薦 | 話題の時系列追跡ができない |
| Flipboard | デザイン・雑誌体験 | AI要約・クラスタリングがない |

### Flotopicの差別化ポイント

- **AIによる時系列トレンド追跡**: 同じ話題が数日〜数週間でどう展開したか一覧で把握できる
- **話題の盛り上がり可視化**: スコア（記事数・更新頻度）でトレンドの勢いを定量表示
- **ノイズの少ない要約**: 重複記事をUnion-Findでクラスタリングし、代表要約のみ表示
- **ライトな情報収集体験**: 重いパーソナライズ設定不要で、すぐに使い始められる

---

## まとめ

FlotopicはバックエンドがすでにモバイルAPIとして機能するため、**React Native移行のハードルは低い**。現フェーズでPWAとして品質を磨きながらユーザー数を積み上げ、月5,000 PV到達を目標にRN αフェーズへの移行を判断する。

> 次のアクション: Google Cloud ConsoleへのiOS/Android認証情報追加（home PCで実施）、アイコン素材の発注または生成
