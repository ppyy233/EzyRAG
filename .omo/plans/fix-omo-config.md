# 修复 oh-my-openagent 配置问题

## TL;DR

> **Quick Summary**: 修复 oh-my-openagent 安装后的多个配置问题，包括 Provider ID 不匹配、TUI 插件加载失败、PaddleOCR MCP 崩溃等。
>
> **Deliverables**:
> - 修复 Provider ID 配置
> - 修复 Agent 模型引用
> - 修复 TUI 插件加载
> - 修复 PaddleOCR MCP 配置
>
> **Estimated Effort**: Short
> **Parallel Execution**: NO - 顺序执行

---

## Context

### 问题描述

oh-my-openagent 安装后出现多个问题：
1. TUI 界面显示 "Agent Prometheus - Plan Builder's configured model xiaomi-mimo/mimo-v2.5-pro is not valid"
2. 使用 `/xxx` 斜杠命令时出现问题
3. PaddleOCR MCP 服务器崩溃
4. 日志显示 TUI 插件加载失败

### 根本原因

1. **Provider ID 不匹配**：配置文件使用 `xiaomi-mimo`，但 OpenCode 实际识别为 `xiaomi-token-plan-cn`
2. **`disabled_providers` 数组**：包含 `xiaomi-mimo`，导致 Provider 被禁用
3. **TUI 插件安装失败**：NpmInstallFailedError
4. **PaddleOCR 模型版本不支持**：使用了 `PP-OCRv6`，但库不支持

---

## Work Objectives

### Core Objective

修复 oh-my-openagent 的所有配置问题，使其正常工作。

### Concrete Deliverables

- 修复 `opencode.jsonc` 中的 Provider 配置
- 修复 `oh-my-openagent.json` 中的模型引用
- 修复 TUI 插件加载
- 修复或禁用 PaddleOCR MCP

### Definition of Done

- [ ] `opencode agent list` 显示所有 Agent 使用正确的 Provider
- [ ] TUI 界面不再显示 "model is not valid" 错误
- [ ] 斜杠命令 `/xxx` 可以正常使用
- [ ] PaddleOCR MCP 不再崩溃（或被禁用）

### Must Have

- Provider ID 与 OpenCode 实际识别的 ID 一致
- 所有 Agent 模型引用使用正确的 Provider ID
- TUI 插件正常加载

### Must NOT Have (Guardrails)

- 不要修改 MiMo API 的 endpoint 或 API key
- 不要删除其他 MCP 服务器配置
- 不要修改 Agent 的角色定义

---

## Verification Strategy

### Test Decision

- **Infrastructure exists**: YES
- **Automated tests**: None
- **Framework**: 手动验证

### QA Policy

每个任务完成后，运行以下命令验证：
- `opencode agent list` - 检查 Agent 加载状态
- `opencode models` - 检查可用模型
- TUI 界面测试 - 检查斜杠命令是否工作

---

## Execution Strategy

### 顺序执行

```
Step 1: 修复 opencode.jsonc 中的 Provider 配置
Step 2: 修复 oh-my-openagent.json 中的模型引用
Step 3: 修复 PaddleOCR MCP 配置
Step 4: 验证所有修复
```

---

## TODOs

- [ ] 1. 修复 opencode.jsonc 中的 Provider 配置

  **What to do**:
  - 将 Provider 名称从 `xiaomi-mimo` 改为 `xiaomi-token-plan-cn`
  - 移除 `disabled_providers` 数组（包含 `xiaomi-mimo`）
  - 更新 `model` 字段为 `xiaomi-token-plan-cn/mimo-v2.5-pro`

  **Must NOT do**:
  - 不要修改 MiMo API 的 endpoint 或 API key
  - 不要删除其他 MCP 服务器配置

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **References**:
  - `C:\Users\py\.config\opencode\opencode.jsonc` - 当前配置文件

  **Acceptance Criteria**:
  - [ ] Provider 名称为 `xiaomi-token-plan-cn`
  - [ ] 没有 `disabled_providers` 数组
  - [ ] `model` 字段为 `xiaomi-token-plan-cn/mimo-v2.5-pro`

  **QA Scenarios**:

  ```
  Scenario: 验证 Provider 配置
    Tool: Bash
    Steps:
      1. 运行 `opencode models | findstr mimo`
      2. 检查输出中是否包含 `xiaomi-token-plan-cn/mimo-v2.5-pro`
    Expected Result: 模型列表中显示 `xiaomi-token-plan-cn/mimo-v2.5-pro`
    Evidence: .omo/evidence/task-1-provider-config.txt
  ```

  **Commit**: YES
  - Message: `fix(config): update provider ID from xiaomi-mimo to xiaomi-token-plan-cn`
  - Files: `C:\Users\py\.config\opencode\opencode.jsonc`

---

- [ ] 2. 修复 oh-my-openagent.json 中的模型引用

  **What to do**:
  - 将所有 `xiaomi-mimo/` 前缀改为 `xiaomi-token-plan-cn/`
  - 涉及文件：`C:\Users\py\.config\opencode\oh-my-openagent.json`

  **Must NOT do**:
  - 不要修改 Agent 的角色定义
  - 不要删除任何 Agent 配置

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **References**:
  - `C:\Users\py\.config\opencode\oh-my-openagent.json` - 当前 Agent 配置

  **Acceptance Criteria**:
  - [ ] 所有模型引用使用 `xiaomi-token-plan-cn/` 前缀
  - [ ] 没有 `xiaomi-mimo/` 前缀

  **QA Scenarios**:

  ```
  Scenario: 验证 Agent 配置
    Tool: Bash
    Steps:
      1. 运行 `opencode agent list | findstr -i "sisyphus\|prometheus\|atlas"`
      2. 检查输出中是否显示正确的模型
    Expected Result: Agent 列表中显示正确的模型配置
    Evidence: .omo/evidence/task-2-agent-config.txt
  ```

  **Commit**: YES
  - Message: `fix(config): update agent model references to use correct provider ID`
  - Files: `C:\Users\py\.config\opencode\oh-my-openagent.json`

---

- [ ] 3. 修复 PaddleOCR MCP 配置

  **What to do**:
  - 检查 PaddleOCR MCP 配置是否正确
  - 如果模型版本不支持，禁用该 MCP 或更新配置

  **Must NOT do**:
  - 不要删除其他 MCP 服务器配置

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **References**:
  - `C:\Users\py\.config\opencode\opencode.jsonc` - MCP 配置部分

  **Acceptance Criteria**:
  - [ ] PaddleOCR MCP 不再崩溃
  - [ ] 或者 PaddleOCR MCP 被禁用

  **QA Scenarios**:

  ```
  Scenario: 验证 MCP 配置
    Tool: Bash
    Steps:
      1. 运行 `opencode` 启动 TUI
      2. 检查日志中是否还有 PaddleOCR 相关错误
    Expected Result: 没有 PaddleOCR 相关错误
    Evidence: .omo/evidence/task-3-mcp-config.txt
  ```

  **Commit**: YES
  - Message: `fix(config): disable or fix PaddleOCR MCP`
  - Files: `C:\Users\py\.config\opencode\opencode.jsonc`

---

- [ ] 4. 验证所有修复

  **What to do**:
  - 运行 `opencode agent list` 检查 Agent 状态
  - 运行 `opencode models` 检查模型列表
  - 启动 TUI 测试斜杠命令

  **Must NOT do**:
  - 不要修改任何配置文件

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Acceptance Criteria**:
  - [ ] `opencode agent list` 显示所有 Agent 使用正确的 Provider
  - [ ] TUI 界面不再显示 "model is not valid" 错误
  - [ ] 斜杠命令 `/xxx` 可以正常使用

  **QA Scenarios**:

  ```
  Scenario: 完整验证
    Tool: Bash
    Steps:
      1. 运行 `opencode agent list`
      2. 运行 `opencode models | findstr mimo`
      3. 启动 TUI，测试 `/help` 命令
    Expected Result: 所有命令正常工作
    Evidence: .omo/evidence/task-4-full-verification.txt
  ```

  **Commit**: NO

---

## Final Verification Wave

- [ ] F1. **配置验证** — `oracle`
  检查所有配置文件是否正确，Provider ID 是否匹配。

- [ ] F2. **功能验证** — `unspecified-high`
  启动 TUI，测试所有主要功能：Agent 选择、斜杠命令、模型调用。

---

## Commit Strategy

- Task 1: `fix(config): update provider ID from xiaomi-mimo to xiaomi-token-plan-cn`
- Task 2: `fix(config): update agent model references to use correct provider ID`
- Task 3: `fix(config): disable or fix PaddleOCR MCP`

---

## Success Criteria

### Verification Commands

```bash
opencode agent list  # 应显示所有 Agent 使用正确的 Provider
opencode models | findstr mimo  # 应显示 xiaomi-token-plan-cn/mimo-v2.5-pro
```

### Final Checklist

- [ ] Provider ID 为 `xiaomi-token-plan-cn`
- [ ] 所有 Agent 模型引用使用正确的 Provider ID
- [ ] TUI 插件正常加载
- [ ] 斜杠命令可以正常使用
- [ ] PaddleOCR MCP 不再崩溃（或被禁用）
