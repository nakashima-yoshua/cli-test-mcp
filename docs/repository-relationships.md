# Related repositories / 関連リポジトリ

This list describes responsibilities and reference links, **not** automatically installed dependencies or implemented integrations. 本一覧は責務・参照先の説明であり、実行時依存や統合済み機能を意味しません。

| Repository | Relation | State / boundary |
| --- | --- | --- |
| [system-understanding-architecture](https://github.com/nakashima-yoshua/system-understanding-architecture) | System context and change scope inform test plans | Documentation only |
| [feature-map-workflow](https://github.com/nakashima-yoshua/feature-map-workflow) | Feature Map links to case IDs and evidence locations | Reference link; no mandatory runtime integration |
| [quality-gate](https://github.com/nakashima-yoshua/quality-gate) | Host may provide independently sealed native results for readiness checks | No automatic evidence sealing or runner invocation |
| [architecture-decision-system](https://github.com/nakashima-yoshua/architecture-decision-system) | Architecture decisions may identify required verification | Proposed handoff; no direct integration |

## Ownership and safety

Actual test definitions, execution and attempt evidence belong to this runner or the adopting project's native test platform. FMW owns durable per-feature links, quality-gate only evaluates separately anchored evidence, ADS owns reusable decision rules, and the adopting project owns accepted requirements and approvals. A test definition is not a test PASS. No other tool can grant production privileges or approve deployment.

Update these links when implemented contracts change, distinguishing implemented functionality from plans. Avoid duplicated documentation and cross-repository mandatory dependencies.
