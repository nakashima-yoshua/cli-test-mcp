# 開発計画

## 目的
AI/人が上流でテスト計画・条件・期待結果を決め、MCP経由で定義・実行・結果取得できる汎用CLIテスト基盤を作る。Test Engineは判断せず、定義に従い複数ケース・複数バッチを自動実行する。

## 対象
- CLIバッチ、引数、環境変数、既存設定ファイル、入力ファイル、許可済みテストDB準備
- Suite → Case → Attempt → Batch の階層
- 複数ログ、stdout/stderr、出力ファイルを試行単位で収集
- 保存確認後のみ指定ログをリセット
- 合否・実行状態・証跡状態・リセット状態を別々に返却
- MCPを使わないCLI単独実行

## 対象外（初期）
GUI、分散実行、任意コマンドの無制限実行、本番環境変更、AIをエンジンに内蔵すること。

## Phase 1: Engine
1. Suite/Case/Result JSON Schemaと定義検証
2. 許可済みターゲット、入力状態準備、複数バッチ逐次実行
3. 複数ログ・試行別証跡、SHA-256検証、条件付きログリセット
4. 期待値照合、結果JSON、CLI入口
**完了条件**：AIなしで複数ケースを実行し、再試行でも証跡を上書きしない。保存失敗時はログをリセットしない。

## Phase 2: MCP
inspect_target / save_test_definition / validate_test_definition / run_tests / get_test_status / get_test_results / get_evidence。
**完了条件**：MCPクライアントから定義登録→検証→実行→結果取得が可能。

## Phase 3: AIループ
結果をAIが分析し、次の定義を更新して再実行。変更理由と履歴を保持。AIが期待結果を勝手に緩めて不具合を隠さない。
**完了条件**：複数試行の結果と証跡を追跡可能。

## Phase 4: 拡張
HTML/Excelエビデンス、feature-map-workflow連携。

## 開発順
契約 → Runner → 初期状態 → 証跡・リセット → 照合 → CLI → MCP → AI運用。

## 未決事項
DB初期化方式、子プロセスとログ書込終了の確認、途中停止の復旧、共有ログ排他制御。
