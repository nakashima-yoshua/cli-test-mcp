# 証跡・リセット・安全性

## 保存構造
```text
results/RUN-001/
  summary.json
  TC001/
    ATTEMPT-001/
      manifest.json
      inputs/
      batches/
        A/{stdout.log,stderr.log,result.json}
        B/{stdout.log,stderr.log,result.json}
      logs/
      outputs/
      result.json
    ATTEMPT-002/
```

Attemptごとの証跡は不変・非上書き。manifestには日時、対象、引数、入力ハッシュ、収集元、収集時点、サイズ、SHA-256、照合結果、リセット結果を記録する。

## 複数ログ
ログごとにpath/glob、必須/任意、収集時点（each_batch/attempt）、リセット（none/truncate/delete）を指定する。stdout/stderrは各バッチで常時取得する。

## リセット条件
1. 対象プロセスと関連子プロセスの書込が終了。
2. 必須ログの収集と保存検証が成功。
3. リセット対象が許可済みパスに収まる。
4. 条件が成立した場合のみtruncate/delete。失敗したら次の試行を停止する。
共有ログ、稼働中ログ、ワークスペース外へのシンボリックリンクはリセット不可。

## セキュリティ
- AI生成JSONは不信入力。登録済みターゲットIDだけ実行。
- 任意シェル実行を許可しない。ファイル・DB操作は明示的許可範囲内。
- 機密情報をログ・証跡・Gitへ混入させない。必要なマスキングを行う。
- 初期版はローカルstdio MCPと逐次実行。
- CIは無害なダミーバッチのみを実行する。

## テスト観点
正常/異常終了、タイムアウト、複数ログ、欠落ログ、保存失敗、リセット失敗、再試行非上書き、パス逸脱、未許可ターゲット、子プロセス継続。
