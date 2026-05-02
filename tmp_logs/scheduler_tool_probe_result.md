# Scheduler Tool Probe Result
- 実行時刻: 2026-05-02T00:01:02+0000
- whoami: eloquent-amazing-wright
- uname: Linux claude 6.8.0-106-generic #106~22.04.1-Ubuntu SMP PREEMPT_DYNAMIC Fri Mar 6 08:19:05 UTC aarch64 aarch64 aarch64 GNU/Linux

## start_code_task 直接 ToolSearch 結果
ToolSearch query: `select:start_code_task`, max_results=1
結果: `No matching deferred tools found`
→ scheduled session 環境では `start_code_task` ツールは登録されていない（deferred tool 一覧に存在しない）。

## "code task spawn session start" 検索結果 (max=10)
キーワード検索で返ってきたツール（関連度順）:
- TaskCreate (built-in タスクリスト作成)
- TaskGet
- TaskUpdate
- TaskStop
- mcp__scheduled-tasks__create_scheduled_task
- mcp__scheduled-tasks__update_scheduled_task
- mcp__6cc776ac-8de4-414f-907d-fe8512fdad29__add_code_connect_map  (Figma)
- mcp__6cc776ac-8de4-414f-907d-fe8512fdad29__get_code_connect_suggestions  (Figma)
- mcp__6cc776ac-8de4-414f-907d-fe8512fdad29__get_context_for_code_connect  (Figma)
- mcp__6cc776ac-8de4-414f-907d-fe8512fdad29__send_code_connect_mappings  (Figma)

→ `start_code_task` 系のコードセッション起動ツールは1件も見つからなかった。
   ヒットしたのは built-in TaskList / scheduled-tasks / Figma Code Connect のみで、
   いずれも Cowork から別コードセッションを spawn する用途のものではない。

## "cowork dispatch" 検索結果 (max=10)
キーワード検索で返ってきたツール:
- mcp__cowork__create_artifact
- mcp__cowork__list_artifacts
- mcp__cowork__allow_cowork_file_delete
- mcp__cowork__present_files
- mcp__cowork__read_widget_context
- mcp__cowork__request_cowork_directory
- mcp__cowork__update_artifact
- mcp__cowork-onboarding__show_onboarding_role_picker
- mcp__scheduled-tasks__create_scheduled_task
- mcp__scheduled-tasks__update_scheduled_task

→ `mcp__cowork__*` 系（artifact/present_files/request_cowork_directory 等）は使えるが、
   コードセッション dispatch（spawn）系のツールは存在しない。

## 結論
- start_code_task: **利用不可**（scheduled session 環境では deferred tool として登録されていない）
- fallback の必要性: **必要**
  scheduled session から直接コードセッションを起動することはできない。
  代替案として考えられるのは:
    (a) `mcp__scheduled-tasks__create_scheduled_task` で fireAt= 数分後の one-time task を作り、
        prompt にコードセッション相当の作業内容を全部書く（ただし scheduled session 同士の
        chain なので、結局「コードセッションを直接 spawn」する手段にはならない）
    (b) Dispatch（Cowork web/desktop）側からのみ start_code_task を呼ぶ前提で運用設計する
    (c) ファイル経由の queue（例: TASKS.md / WORKING.md）に「次に Dispatch が拾うべき指示」を
        書き出して、人間 or Cowork セッション側がトリガする
- 推測: scheduled session 環境は Cowork web/desktop と **異なる** ツールセット
  - 共通: mcp__cowork__*, mcp__scheduled-tasks__*, ToolSearch, Bash, Write/Edit, MCP 各種
  - scheduled session に**ない**: start_code_task（コードセッション spawn 用ツール）
  - つまり p003-dispatch-auto を scheduled session で走らせても、
    そこから自動でコードセッションを spawn することは現状できない。
    Dispatch の自動化は「Cowork 側で start_code_task を呼べるセッション」が必要。
