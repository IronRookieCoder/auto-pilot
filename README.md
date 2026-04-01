# Auto-Pilot: Long-Cycle TDD Coding Workflow Plugin

English / [中文](README_CN.md)

Auto-Pilot is a Claude Code plugin designed for long-running tasks. It persists workflow state to the `.workflow/` directory, ensuring controllability and traceability of AI execution through a structured state machine, TDD rhythm, and enforced gates.

## Installation

Place the `auto-pilot` directory in a plugin directory recognized by Claude Code, or specify it via:

```bash
claude --plugin-dir ./auto-pilot
```

## Usage

### One-Command Run

```text
/auto-pilot:run Implement a TODO app with CRUD and categorization
```

Execution order:

```text
init → user confirms spec → plan → user confirms plan → execute → verify → completed
```

### Step-by-Step

```bash
/auto-pilot:init
# Edit .workflow/spec.md, fill in goals and constraints
python tools/workflow_confirm.py spec

/auto-pilot:plan
# Review .workflow/plan.md, confirm milestone breakdown
python tools/workflow_confirm.py plan

/auto-pilot:execute
/auto-pilot:verify
```

### Standalone Commands

```bash
/auto-pilot:verify   # Verify current code quality at any time
/auto-pilot:status   # View workflow progress
```

## Skills

| Skill     | Command               | Description                                              |
| --------- | --------------------- | -------------------------------------------------------- |
| `init`    | `/auto-pilot:init`    | Initialize `.workflow/` directory and project memory      |
| `plan`    | `/auto-pilot:plan`    | Generate milestone plan based on `spec.md`               |
| `execute` | `/auto-pilot:execute` | Execute milestones following TDD rhythm                  |
| `verify`  | `/auto-pilot:verify`  | Run lint/typecheck/test/build and write to `verify.json` |
| `status`  | `/auto-pilot:status`  | Summarize current workflow state and progress             |
| `run`     | `/auto-pilot:run`     | One-command orchestration: init → plan → execute → verify |

---

## Phase Transitions

```text
init --[spec_approved]--> planning --[plan_approved]--> executing --> verifying --[final_verify=pass]--> completed
```

## TDD Rhythm

Each milestone progresses according to its `tdd_type`:

- **`standard`** (default): Define tests → Confirm RED → Write implementation → Verify GREEN → Pass gate → Mark complete
- **`setup`**: Execute scaffolding → Verify environment works → Pass gate (RED evidence optional)
- **`verification_only`**: Run verification → Confirm results → Pass gate (RED evidence optional)

> When tests fail, only implementation code may be modified — modifying tests to force a "pass" is prohibited.

## Interruption Recovery

The workflow supports resuming from saved structured state checkpoints:

- `run` / `execute` reads the `phase` field in `workflow.json` and continues from the last interrupted phase
- When `status=blocked/failed/paused`, you must first run `python tools/workflow_resume.py`
- `execute` preferentially reads `current_milestone_id` to resume the current milestone; as long as there are unresolved failed milestones, it will not proceed to the next pending one
- Completed milestones are not re-executed

---

## Core Design Principles

- Human-facing documents remain in Markdown: `spec.md` (goals & constraints), `plan.md` (execution plan)
- Machine-facing state is fully structured: `workflow.json`, `milestones.json`, `verify.json`, `events.jsonl`
- The `spec_approved` and `plan_approved` gates can only be triggered by manual user confirmation
- Only when `final_verify_overall=pass` is the `completed` phase allowed
- `blocked/failed/paused -> running` can only go through `workflow_resume.py`
- Critical state transitions must pass script validation, not just rely on prompt constraints
- Tracking IDs in `spec.md` (`FR-*`/`AC-*`/`IN-*`/`OUT-*`) and `spec_refs` in `milestones.json` form bidirectional traceability; lint automatically checks coverage completeness and out-of-scope references

## Directory Structure

```text
.workflow/
├── spec.md              # Human review: frozen goals, scope, and constraints
├── plan.md              # Human review: auto-generated from milestones.json
├── workflow.json        # Source of truth: global phase, gates, and verify commands
├── milestones.json      # Source of truth: milestone structure and execution state
├── verify.json          # Source of truth: verification run records
└── events.jsonl         # Source of truth: append-only event stream
```

## Tool Scripts

| Script                                         | Purpose                                                            |
| ---------------------------------------------- | ------------------------------------------------------------------ |
| `python tools/workflow_init.py`                | Reads `tools/schemas/*.json` to generate initialized `.workflow/` files |
| `python tools/workflow_lint.py [phase]`        | Validates schema, phase preconditions, cross-file consistency, and spec-plan coverage completeness; warnings do not block |
| `python tools/workflow_gate.py milestone <id>` | Milestone completion gate: checks dependencies, RED evidence, GREEN results, verification records |
| `python tools/plan_sync.py export`             | Exports `milestones.json` to `plan.md`                             |
| `python tools/plan_sync.py import`             | Imports `plan.md` back to `milestones.json`, including `tdd_type`/`test_files`/`spec_refs` |
| `python tools/workflow_confirm.py spec`        | User confirms `spec.md`, workflow advances to `planning` phase     |
| `python tools/workflow_confirm.py plan`        | User confirms `plan.md`, runs import + lint, then advances to `executing` |
| `python tools/workflow_resume.py`              | Resumes `blocked/failed/paused` workflow with lint and pre-resume validation |

## Schema Definitions

The authoritative definitions for structured state files are in [`tools/schemas/README.md`](tools/schemas/README.md):

- [`workflow.schema.json`](tools/schemas/workflow.schema.json)
- [`milestones.schema.json`](tools/schemas/milestones.schema.json)
- [`verify.schema.json`](tools/schemas/verify.schema.json)
- [`event.schema.json`](tools/schemas/event.schema.json)

`workflow_init.py` reads these schemas directly to derive initial JSON, with no need to maintain parallel hardcoded structures.

## Protection Hooks

The repository includes [`hooks/hooks.json`](hooks/hooks.json), which defines two types of automatic protection:

- **`PreToolUse`**: Invokes [`hooks/validate_workflow_write.py`](hooks/validate_workflow_write.py)
  - Blocks illegal direct writes to `.workflow/*.json`, `events.jsonl`, and `plan.md`
  - `spec_approved` / `plan_approved` cannot be written as `true` by AI during initial creation or subsequent edits
  - `plan.md` cannot be manually edited — it must be generated via `plan_sync.py export`

- **`PostSkill`**: Invokes [`hooks/post_skill_lint.py`](hooks/post_skill_lint.py)
  - Automatically runs `workflow_lint.py` after each `init / plan / execute / verify / run` completion
  - Blocks further progression if artifacts are inconsistent
