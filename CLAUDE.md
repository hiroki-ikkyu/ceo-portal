# CLAUDE.md — Hiroki's WebApp Ecosystem

> Claude Code への引き継ぎ用ドキュメント。
> 全アプリの構成・設計方針・データ連携計画をまとめている。

---

## オーナー

- GitHub: `hiroki-ikkyu`
- ホスティング: GitHub Pages (`hiroki-ikkyu.github.io/*`)
- IDE: Cursor（個人PC・Windows）
- 全アプリは同一ドメイン上にデプロイ → localStorage 共有可能

---

## アプリ一覧

| アプリ名 | リポジトリ名（想定） | 内容 | 状態 |
|---------|-------------------|------|------|
| CEO Portal | `ceo-portal` | Morning Brief + CEOページ（アプリハブ） | 稼働中 |
| 家計簿（Expense Tracker） | `kakeibo` | ¥3,000/日予算・サブスク・収入管理 | 稼働中 |
| Routine Tracker | `routine-tracker` | タイムライン型日課チェック・ジャーナル | 稼働中 |
| Study Tracker | `study-tracker` | USCPA・簿記2級の勉強時間記録 | 稼働中 |
| Goal Manager | `goal-manager` | キャリア・資格・スキル目標管理 | 稼働中 |
| Wardrobe Manager | `wardrobe-manager` | 服の管理・ウィッシュリスト | 稼働中 |

> **初回タスク**: `gh repo list hiroki-ikkyu --limit 30` で正確なリポジトリ名を確認し、この表を更新すること。

---

## 統一デザインシステム

- **フォント**: DM Sans（英数字）, Noto Sans JP（日本語）
- **カラー**: モノクロアクセント（#1D1D1F / #6E6E73 / #AEAEB2）、白〜ライトグレー背景
- **Border Radius**: 16px（カード）, 10-12px（小要素）
- **トーン**: Apple風ミニマル、モバイルファースト、max-width 420px
- **構成**: HTML SPA（1ファイル構成）、ビルドツール不要

---

## データ連携の仕組み

### 目的

各アプリが独立して持っている日次データを、CEOポータルの「CEO」ページに集約表示する。

### SharedStore（shared-store.js）

全アプリが読み込む共有データライブラリ。同一ドメインの localStorage を使ってアプリ間でデータを共有する。

**配置場所**: `ceo-portal` リポジトリのルート
**読み込みURL**: `https://hiroki-ikkyu.github.io/ceo-portal/shared-store.js`

### localStorage キー設計

```
shared:expense:YYYY-MM-DD   → { spent, budget, items, updatedAt }
shared:study:YYYY-MM-DD     → { sessions: [{minutes, subject, loggedAt}], totalMinutes, updatedAt }
shared:routine:YYYY-MM-DD   → { completed, total, items, updatedAt }
```

`shared:` プレフィックスが付くキーだけがアプリ間共有データ。
各アプリ固有の localStorage キーには触れない。

### データの流れ

```
Expense Tracker → SharedStore.expense.logDay() → localStorage に書き込み
Study Tracker   → SharedStore.study.logSession() → localStorage に書き込み
Routine Tracker → SharedStore.routine.logDay() → localStorage に書き込み
      ↓
CEO Portal の CEOページ → SharedStore.getTodaySummary() で読み取り・表示
```

### スコアリング（ゲーミフィケーション）

1日最大3点:
- 予算内（Expense）→ +1
- 勉強30分以上（Study）→ +1
- ルーティン80%以上（Routine）→ +1

---

## 各アプリへの組み込み方法

### Step 1: script タグ追加

各アプリの `index.html` の `<head>` 内に1行追加：

```html
<script src="https://hiroki-ikkyu.github.io/ceo-portal/shared-store.js"></script>
```

### Step 2: データ書き込みコードの追加

各アプリの既存データ保存処理の近くに追加する。
`SharedStore` が読み込めない場合のガード付き。

#### 家計簿（kakeibo）

支出記録の保存処理を見つけて、その直後に追加：

```javascript
if (typeof SharedStore !== 'undefined') {
  SharedStore.expense.logDay({
    spent: todayTotal,    // その日の合計支出額
    budget: dailyBudget,  // 1日の予算（3000）
  });
}
```

#### Study Tracker

勉強セッション終了時の保存処理を見つけて、その直後に追加：

```javascript
if (typeof SharedStore !== 'undefined') {
  SharedStore.study.logSession({
    minutes: sessionMinutes,  // セッションの勉強時間
    subject: currentSubject,  // 'FAR', 'AUD', 'REG', 'BAR', '簿記2級' 等
  });
}
```

#### Routine Tracker

チェック状態変更時の保存処理を見つけて、その直後に追加：

```javascript
if (typeof SharedStore !== 'undefined') {
  SharedStore.routine.logDay({
    completed: checkedCount,  // チェック済みの数
    total: totalCount,        // ルーティン総数
  });
}
```

### Step 3: CEOページにサマリー表示を追加

`ceo-portal` の `index.html` を読んで、CEOページ（アプリ一覧のハブ画面）を見つける。
各アプリカードの中に、SharedStore.getTodaySummary() で取得したデータを表示する。

例：
- Expense Tracker カード → 「今日 ¥2,400 / ¥3,000」
- Study Tracker カード → 「今日 45分 · FAR」
- Routine Tracker カード → 「4/6 完了 (67%)」

---

## コーディング規約

- HTML SPA（1ファイル構成）: index.html に CSS・JS を全部含める
- React 使用時: CDN 版（unpkg）、Babel standalone でブラウザ内変換
- PWA 化: manifest.json + service worker（sw.js）
- デプロイ: GitHub Pages（main ブランチ直接）
- npm / Vite 等のビルドツールは使わない
- 共有データは `shared:` プレフィックスで localStorage に書く
- 各アプリ固有のデータ構造は変更しない

---

## 将来の拡張

### Phase 2: クラウド同期（未着手）
- Supabase 等を導入し、SharedStore の内部実装を差し替え
- デバイス間データ同期が可能に

### Phase 3: 高度な連携（未着手）
- Expense → Routine: 予算達成 → 自動チェック
- Study → Expense: 勉強目標達成 → ご褒美予算追加
- Goal Manager → 各アプリ: KPI 自動取得
- Research Portal → Bloomberg API（6月以降）
