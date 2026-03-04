# Context Engineering 審查報告與優化計畫

## 審查結果

對 `_build_system_prompt`、`_prepare_messages`、`_get_workspace_context`、`_get_skill_instructions`、`_reasoning_loop` 以及 workspace/skill/subagent 子系統做了全面審查。以下按嚴重程度排列。

---

## P0：會導致 Runtime 失敗

### 1. 沒有 Context Window 管理 — conversation_history 無限增長

**位置**：`orchestrator.py` `_reasoning_loop` L1075

`conversation_history = []` 在 reasoning loop 裡只增不減。每次迭代加入 assistant message + tool results（bash 輸出可達 10KB）。`max_iterations=50` 下理論上可累積數十萬 tokens，**直接撞上 API 的 context limit 回傳 400 error**。

目前完全沒有：
- Token 計數
- Context window size 常量
- Sliding window / 摘要 / 截斷機制
- 接近上限時的預警

### 2. Workspace conversation 壓縮是 dead code

**位置**：`workspace/lifecycle.py` `compress_workspace()`

壓縮邏輯存在但**從未在 runtime 被呼叫**。`WorkspaceLifecycleManager` 只在 CLI 的 `workspace_purge` 指令中實例化，正常 orchestrator 運行時不會觸發。`workspace_conversation` list 無限增長。

---

## P1：影響輸出品質

### 3. System prompt 對不可用的 tool 給出完整指引

**位置**：`orchestrator.py` `_build_system_prompt` L1388-1434

不管什麼 mode，system prompt **永遠包含** `todo_list` 和 `task_decompose` 的完整操作指南（含 JSON 範例）。但：
- EXECUTE mode 封鎖了 `task_decompose`
- PLAN mode 封鎖了 `todo_list`

LLM 收到了不可用 tool 的詳細教學，浪費 tokens 且可能造成混淆。

### 4. Skill 匹配過於寬鬆

**位置**：`orchestrator.py` `_get_skill_instructions` L1651-1696，`skills/registry.py`

- Keyword 提取：取 task description 前 5 個字（含 stop words），幾乎所有 skill 都會命中
- Tool-based 匹配：只要 skill 需要的 tool 中有任何一個可用就匹配。因為 `bash` 和 `file_read` 幾乎永遠可用，大多數 skill 永遠命中
- 結果：3 個 SKILL.md 全文注入（每個 ~100 行），不管任務是否相關

### 5. Workspace context 中 recent tasks 和 related tasks 重複

**位置**：`orchestrator.py` `_get_workspace_context` L762-783

Recent Tasks（最近 3 個）和 Related Past Tasks（keyword 搜尋 top 2）可能包含相同的 task summary，沒有去重。

### 6. Dependency results 從未注入 — dead code

**位置**：`orchestrator.py` `_get_dependency_results` L953-973

方法存在但**沒有任何地方呼叫它**。當 Task B 依賴 Task A 時，B 的 LLM context 裡拿不到 A 的執行結果，Agent 無法根據前置任務的輸出做決策。

---

## P2：可以改善但非緊急

### 7. System prompt 資訊排序不佳

目前順序：base instruction → skills → mode instructions → **workspace context** → static boilerplate

Session memory（workspace context）被夾在中間，屬於低注意力區域。應放在更靠近開頭或結尾的位置。

### 8. Subagent 拿不到 parent 的中間結果

**位置**：`subagents/manager.py` `_run_subagent_task` L227-253

Subagent 只收到 parent task 的 **title**，不含 description 或已完成的 tool results。除非 caller 手動塞 `context_data`，否則 subagent 缺乏關鍵上下文。

### 9. `context["conversation_history"]` 永遠是空的

**位置**：`orchestrator.py` `_build_context` L740

`context` dict 裡的 `conversation_history` 永遠是 `[]`，實際對話歷史是 `_reasoning_loop` 的 local variable。同名不同物，造成混淆。

---

## 建議優化計畫（按優先度）

### Phase A：Context Window 保護（P0）

修改 `_reasoning_loop`，加入 conversation history 的 token-aware 管理：

1. **新增 token 估算工具**（`src/orchestrator/llm/token_utils.py`）
   - 用字元數 / 4 做粗估（不需要引入 tiktoken）
   - 定義 model context window 常量（Claude Sonnet = 200K）

2. **在 `_reasoning_loop` 每次迭代前檢查**
   - 估算 system_prompt + conversation_history + tools 的 token 數
   - 接近上限（例如 80%）時：摘要最早的對話輪次，替換成 "[Earlier: completed X steps, key results: ...]"
   - 超過上限時：truncate 最早的 tool results，保留 assistant messages

3. **啟用 runtime workspace compression**
   - 在 orchestrator `initialize()` 中實例化 `WorkspaceLifecycleManager`
   - 在每次 `process_input` 結束後呼叫 `compress_workspace()`

### Phase B：System Prompt 瘦身（P1）

修改 `_build_system_prompt`：

1. **條件化 tool 指引**：根據當前 mode 的 `blocked_tools` 過濾掉不可用 tool 的指引
2. **去重 workspace context**：related tasks 排除已出現在 recent tasks 的 summary
3. **注入 dependency results**：呼叫 `_get_dependency_results()` 並加入 context

### Phase C：Skill 匹配優化（P1）

修改 skill matching：

1. **過濾 stop words**：keyword 提取時排除常見 stop words
2. **要求 tool-based matching 至少匹配 2+ tools**，或 keyword + tool 雙重條件
3. **限制注入量**：只注入 skill description，不注入完整 SKILL.md 內容（除非 LLM 明確要求）

---

## 驗證

```bash
# 所有現有測試通過
pytest tests/unit/ -v

# 新增的 context management 測試
pytest tests/unit/test_context_management.py -v
```

手動測試：執行一個需要多輪迭代的複雜任務，觀察 log 中的 token 估算和 conversation history 管理行為。
