# 型付き入出力エビデンス

このPRでは既存の逐次CLIエンジンに「宣言した入出力の原本保存と索引」を追加する。
**SQL/HTTP/GUIを新たに実行するアダプターは含まない**。SQL文・バインド値・
実行結果、HTTPリクエスト・レスポンス、画面画像はテストプログラムが
試行ワークスペースに実際に記録する必要がある。AIによる推測・再構成は禁止。

## 契約例（Case JSON の追加フィールド）

```json
{
  "verification_points": [
    {"id": "VP-DB", "description": "登録結果", "expected": "対象が1件"}
  ],
  "assertions": [
    {"type": "file_exists", "path": "db/result.csv",
     "verification_point_ids": ["VP-DB"]}
  ],
  "evidence": [
    {"id": "db-after", "kind": "sql", "capture_after": "attempt",
     "verification_point_ids": ["VP-DB"],
     "artifacts": {
       "statement": "db/executed.sql",
       "parameters": "db/params.json",
       "result": "db/result.csv"
     }}
  ]
}
```

上記の `file_exists` は存在チェックだけであり、SQL結果の内容が正しいことは
別途期待値比較のアサーションで検証する。証跡だけでは合格にしない。
従来Case定義への追加フィールドはすべて任意で互換性を維持する。

| kind | 必須ロール | 用途 |
| --- | --- | --- |
| file | content | 設定・入力・出力ファイル |
| sql | statement, result | 実行SQLと結果（parameters任意） |
| http | request, response | 外部システムとの要求・応答 |
| screenshot | image | Playwright/FlaUI等で撮影した画像 |
| process | 自動取得 | 全バッチのstdout/stderr、終了状態 |

各グループの `capture_after` は `setup`, `each_batch`, `attempt`。
省略時は `attempt`。パスは作業スロット相対、同一IDはケース内で一意。
必須グループの不足は実行ERRORとしスロットを残す。
任意グループの欠落は明示的に `missing` とする。
`result.json` と `manifest.json` に種別・検証観点・相対パス・サイズ・SHA-256を保存する。
検証観点に紐づくアサーションがなければ `not_evaluated` とし、
PASSにしない。

## セキュリティと後続対応

収集対象はテスト実行環境に限定する。機密情報、認証トークン、個人情報を含む
設定・通信・ログを指定しない。取得アダプター側で秘匿値を除外する。
この実装はマスキングやOS隔離を提供しない。
SQL・HTTPの原本が本当に送受信されたことは、接続アダプターや相関IDの
追加なしには保証できない。納品用「1シナリオ1枚」のPDF/Excel生成は後続PRとする。
