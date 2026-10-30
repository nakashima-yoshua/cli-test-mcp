# 入出力契約（設計草案）

JSONを正本とし、INI/XML/CSV/SQLなどの既存ファイルはそのまま参照する。パスは許可済みワークスペース相対。

## Suite
```json
{
  "schema_version": "1.0",
  "suite_id": "regression",
  "execution": {"mode": "sequential", "stop_on_failure": false},
  "cases": [{"id": "TC001", "definition": "cases/TC001.json"}]
}
```

## Case
```json
{
  "schema_version": "1.0",
  "case_id": "TC001",
  "setup": [{"type": "copy", "source": "fixtures/normal.ini", "destination": "work/app.ini"}],
  "batches": [
    {"id": "A", "target": "batch-a", "args": ["--mode", "normal"], "timeout_seconds": 120},
    {"id": "B", "target": "batch-b", "args": ["--input", "output-a.csv"], "timeout_seconds": 120}
  ],
  "logs": [
    {"id": "app", "path": "work/logs/app.log", "capture_after": "each_batch", "reset": "truncate", "required": true},
    {"id": "errors", "path": "work/logs/error*.log", "capture_after": "attempt", "reset": "delete", "required": false}
  ],
  "assertions": [
    {"type": "exit_code", "batch": "A", "equals": 0},
    {"type": "file_exists", "path": "work/output.csv"}
  ]
}
```

## MCPツール
| ツール | 入力 | 出力 |
| --- | --- | --- |
| inspect_target | target_id | 登録済み対象・設定・ログ候補 |
| save_test_definition | 定義ID、JSON | リビジョン |
| validate_test_definition | 定義ID | 検証結果 |
| run_tests | suite_id、case_ids?、attempts? | run_id、状態 |
| get_test_status | run_id | 進捗 |
| get_test_results | run_id、取得項目 | 合否・失敗箇所・証跡索引 |
| get_evidence | run_id、case_id?、attempt_id? | 証跡一覧・必要部分 |

run_testsは非同期でrun_idを返す。巨大ログを一括返却せず必要範囲だけ参照する。

## Result
```json
{
  "schema_version": "1.0",
  "run_id": "RUN-001",
  "status": "completed",
  "cases": [{
    "case_id": "TC001",
    "attempt_id": "ATTEMPT-001",
    "execution_status": "completed",
    "verdict": "passed",
    "evidence_status": "verified",
    "cleanup_status": "completed",
    "manifest": "runs/RUN-001/TC001/ATTEMPT-001/manifest.json"
  }]
}
```

JSON Schemaの詳細はPhase 1で確定する。上記は実装済みAPIではない。
