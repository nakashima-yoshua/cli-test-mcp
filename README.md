# cli-test-mcp

AIがテスト定義を作成し、MCP経由でCLIバッチのテストを実行・結果取得するための汎用テスト基盤（設計段階）。

## 原則
- **AI/人（上流）**：対象分析、テスト計画・条件・期待結果の決定、結果分析、再試行判断。
- **MCP Adapter**：定義の保存・検証、実行指示、結果・証跡取得。
- **Test Engine**：定義どおりの環境準備、複数バッチ・複数ケース実行、機械的照合、複数ログ収集、証跡保存後のログリセット。
- **Suite → Case → Attempt → Batch**：試行ごとの独立証跡を保持。
- CLI単独実行可能。初期版はPython・JSON・ローカルstdio MCP・逐次実行。

## 設計文書
- [開発計画](docs/plan.md)
- [アーキテクチャ](docs/architecture.md)
- [入出力契約](docs/contracts.md)
- [証跡とセキュリティ](docs/evidence-security.md)

## 現状
設計登録済み。エンジン、MCP、JSON Schemaは未実装です。例示したJSONは設計草案です。
