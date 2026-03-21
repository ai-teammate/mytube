---
name: dmtools-agents
description: >
  Setup, configuration, and customization of dmtools GraalJS agents
  (smAgent, configLoader, unit tests). Use this when asked to configure
  agents for a project, add a new project config, write agent rules,
  customize branch/commit/PR formats, set up per-project SM schedules,
  or run/write agent unit tests.
---

# DMTools Agents — Integration & Customization Guide

## Overview

The `agents/` directory (git submodule → `IstiN/dmtools-agents`) contains
GraalJS scripts and JSON configs that orchestrate AI automation via dmtools.

Key files:
```
agents/
  js/
    smAgent.js          — SM orchestrator (JSRunner entry point)
    configLoader.js     — config discovery, merging, template utilities
    config.js           — shared constants (STATUSES, LABELS, ISSUE_TYPES…)
    unit-tests/         — test framework + test files
  sm.json               — SM rules config (JSRunner)
  sm_merge.json         — SM merge-phase rules
  *.json                — individual agent configs (Teammate/Expert/etc.)
  instructions/         — shared instruction markdown files
  prompts/              — shared prompt markdown files
```

---

## Quick Setup: New Project

### Step 1 — Create `.dmtools/config.js` at the repo root

```js
// .dmtools/config.js
module.exports = {
  // GitHub repository (required for SM to trigger workflows)
  repository: {
    owner: 'my-org',
    repo: 'my-repo'
  },

  // Jira project (required for JQL interpolation)
  jira: {
    project: 'MYPROJ',
    parentTicket: 'MYPROJ-1'   // epic/parent for {parentTicket} in JQLs
  },

  // Git defaults
  git: {
    baseBranch: 'main'
  }
};
```

### Step 2 — Run the SM agent

```bash
dmtools run agents/sm.json
```

`{jiraProject}` and `{parentTicket}` in all JQL rules are automatically
replaced from config. `owner`/`repo` from config override sm.json defaults.

---

## Multi-Project Setup (per-folder structure)

For repos with multiple Jira projects under separate folders
(e.g. `projects/ALPHA/`, `projects/BETA/`):

### Option A — `agentConfigsDir` (recommended, zero-maintenance)

Each project folder gets:
```
projects/ALPHA/
  sm.json                  ← minimal launcher
  .dmtools/config.js       ← all project config + rules
  StoryAgent.json          ← agent JSON configs
  BugCreation.json
```

**`projects/ALPHA/sm.json`** — identical template for every project:
```json
{
  "name": "JSRunner",
  "params": {
    "jsPath": "agents/js/smAgent.js",
    "jobParams": { "agentConfigsDir": "projects/ALPHA" }
  }
}
```

**`projects/ALPHA/.dmtools/config.js`** — all project logic lives here:
```js
module.exports = {
  repository: { owner: 'my-org', repo: 'alpha-repo' },
  jira: { project: 'ALPHA', parentTicket: 'ALPHA-1' },
  git: { baseBranch: 'main' },

  // Path to this folder — used to resolve short configFile names in rules
  agentConfigsDir: 'projects/ALPHA',

  // SM rules — configFile is a SHORT name, resolved to agentConfigsDir/name
  smRules: [
    {
      description: 'Generate test cases',
      jql: "project = {jiraProject} AND status = 'Ready For Testing'",
      configFile: 'TestCasesGenerator.json',   // resolves to projects/ALPHA/TestCasesGenerator.json
      skipIfLabel: 'sm_tc_triggered',
      addLabel: 'sm_tc_triggered'
    },
    {
      description: 'Review stories',
      jql: "project = {jiraProject} AND status = 'In Review'",
      configFile: 'StoryAgent.json',
      enabled: true
    }
  ]
};
```

Adding a new project = create new folder with sm.json + config.js. Nothing else changes.

### Option B — Per-rule `configPath` in a single SM

One shared `sm.json` targeting multiple projects:
```json
{
  "name": "JSRunner",
  "params": {
    "jsPath": "agents/js/smAgent.js",
    "jobParams": {
      "rules": [
        {
          "jql": "project = {jiraProject} AND status = 'Ready'",
          "configFile": "agents/story_development.json",
          "configPath": "projects/ALPHA/.dmtools/config.js"
        },
        {
          "jql": "project = {jiraProject} AND status = 'Ready'",
          "configFile": "agents/story_development.json",
          "configPath": "projects/BETA/.dmtools/config.js"
        }
      ]
    }
  }
}
```

Each rule loads its own config. `{jiraProject}` resolves independently per rule.

---

## Config File Reference

All fields and their merge behavior:

```js
module.exports = {
  // ── Repository ──────────────────────────────────────────────────────────
  repository: {
    owner: 'my-org',          // GitHub org/user
    repo: 'my-repo'           // Repository name
  },

  // ── Jira ────────────────────────────────────────────────────────────────
  jira: {
    project: 'MYPROJ',        // Used in {jiraProject} JQL placeholder
    parentTicket: 'MYPROJ-1', // Used in {parentTicket} JQL placeholder

    // FULL REPLACEMENT when provided (not merged with defaults)
    statuses: { IN_REVIEW: 'In Review', DONE: 'Done', /* ... */ },
    issueTypes: {
      STORY: 'Story', BUG: 'Bug', TASK: 'Task',
      TEST_CASE: 'Test Case'   // customize if your Jira uses e.g. 'XRay Test'
    }
  },

  // ── Git ─────────────────────────────────────────────────────────────────
  git: {
    baseBranch: 'main',
    authorName: 'AI Teammate',
    authorEmail: 'agent@example.com',
    branchPrefix: {
      development: 'ai',
      test: 'test',
      feature: 'feature'
    }
  },

  // ── Commit & PR formats ─────────────────────────────────────────────────
  formats: {
    commitMessage: {
      development:    '{ticketKey} {ticketSummary}',
      testAutomation: '{ticketKey} test: automate {ticketSummary}',
      rework:         '{ticketKey} Rework: address PR review comments'
    },
    prTitle: {
      development:    '{ticketKey} {ticketSummary}',
      rework:         '{ticketKey} {ticketSummary} (rework)'
    }
  },

  // ── Labels ───────────────────────────────────────────────────────────────
  // FULL REPLACEMENT when provided
  labels: {
    AI_GENERATED: 'ai_generated',
    AI_DEVELOPED: 'ai_developed'
    // … add project-specific labels
  },

  // ── Confluence URL overrides ─────────────────────────────────────────────
  confluence: {
    templateStory:         'https://my-wiki/pages/123/Story-Template',
    templateJiraMarkdown:  'https://my-wiki/pages/456/Jira-Markdown',
    templateSolutionDesign:'https://my-wiki/pages/789/Solution-Design',
    templateQuestions:     'https://my-wiki/pages/101/Questions'
  },

  // ── SM Rules (FULL REPLACEMENT when provided) ────────────────────────────
  agentConfigsDir: 'projects/MYPROJ',  // base dir for short configFile names
  smRules: [ /* ... see above ... */ ],
  smMergeRules: [ /* ... */ ],

  // ── Instruction overrides ────────────────────────────────────────────────
  // additionalInstructions: appended to agent's base instructions
  additionalInstructions: {
    story_description: [
      'https://my-wiki/pages/story-template'
    ],
    story_solution: [
      'https://my-wiki/pages/solution-design',
      './instructions/custom-rules.md'
    ]
  },

  // instructionOverrides: REPLACES the agent's entire instructions array
  instructionOverrides: {
    story_development: [
      'https://my-wiki/pages/dev-guide',
      './agents/instructions/development/implementation_instructions.md'
    ]
  }
};
```

---

## Rule Fields Reference

```js
{
  jql:            "project = {jiraProject} AND status = 'Ready'",  // required
  configFile:     "StoryAgent.json",      // required — short name (+ agentConfigsDir) or full path
  configPath:     "projects/X/.dmtools/config.js",  // optional — per-rule config override
  description:    "Develop stories",     // optional — shown in logs
  targetStatus:   "In Development",      // optional — transition before triggering
  workflowFile:   "ai-teammate.yml",     // optional — default: ai-teammate.yml
  workflowRef:    "main",                // optional — default: main
  skipIfLabel:    "sm_dev_triggered",    // optional — idempotency: skip if ticket has label
  addLabel:       "sm_dev_triggered",    // optional — add after trigger
  enabled:        true,                  // optional — false to disable without deleting
  limit:          10,                    // optional — max tickets per run
  localExecution: false                  // optional — run postJSAction in-process (no GitHub trigger)
}
```

---

## Config Discovery Order

`configLoader.loadProjectConfig(params)` searches in this order:

1. `params.configPath` — explicit path in jobParams
2. `params.customParams.configPath` — from agent JSON customParams
3. `params.agentConfigsDir + "/.dmtools/config.js"` — when agentConfigsDir is set
4. `../.dmtools/config.js` — submodule layout (agents/ is a submodule)
5. `.dmtools/config.js` — co-located layout (agents/ in same repo)
6. Built-in defaults

The resolved `_configPath` is propagated into `encoded_config.customParams.configPath`
when smAgent triggers downstream workflows — so postJSAction scripts also find
the correct project config automatically.

---

## Customizing Branch, Commit, and PR Formats

Override in `.dmtools/config.js`:

```js
git: {
  branchPrefix: { development: 'feature', test: 'test' },
  baseBranch: 'develop'
},
formats: {
  commitMessage: {
    development: 'feat({ticketKey}): {ticketSummary}'
  },
  prTitle: {
    development: '[{ticketKey}] {ticketSummary}'
  }
}
```

Available template variables: `{ticketKey}`, `{ticketSummary}`, `{result}`.

---

## Running Unit Tests

```bash
# All tests
dmtools run agents/js/unit-tests/run_all.json

# configLoader only
dmtools run agents/js/unit-tests/run_configLoader.json

# smAgent only
dmtools run agents/js/unit-tests/run_smAgent.json
```

Tests use `loadModule(path, requireFn, mocks)` from `testRunner.js` to isolate
modules and inject mock globals (`file_read`, `jira_search_by_jql`, etc.)
without touching the real environment.

See `agents/js/unit-tests/README.md` for how to write new tests.

---

## targetRepository — Trigger Workflows in a Different Repo

Use when the SM runs in repo A but should trigger workflows in repo B
(e.g. agents isolated repo triggering a product repo):

```js
// In .dmtools/config.js
// OR as customParams in encoded_config
{
  targetRepository: {
    owner: 'product-org',
    repo: 'product-repo',
    baseBranch: 'main',
    workingDir: 'product-repo'  // checkout dir in workflow
  }
}
```

---

## Submodule vs Co-located Layout

**Submodule layout** (agents in separate repo, checked out as submodule):
```
my-project/
  agents/          ← git submodule → IstiN/dmtools-agents
  .dmtools/
    config.js      ← discovered via ../agents → ../.dmtools/config.js
```

**Co-located layout** (agents and project in same repo):
```
my-project/
  agents/          ← copied or checked out here
  .dmtools/
    config.js      ← discovered via .dmtools/config.js
```

Both layouts are auto-discovered. No configuration needed.

---

## Jira Automation — Triggering Agents

Use Jira automation's **"Send web request"** action to trigger a GitHub Actions workflow.

The workflow (`ai-teammate.yml`) accepts three inputs:
- `config_file` — path to the agent JSON config inside the repo
- `concurrency_key` — ticket key for deduplication (e.g. `PROJ-123`)
- `encoded_config` — optional JSON override (URL-encoded) for `inputJql`, `configPath`, etc.

**Jira automation action → Send web request:**

```
POST https://api.github.com/repos/{repo-owner}/{repo}/actions/workflows/ai-teammate.yml/dispatches
```

Headers:
```
Authorization: Bearer {{YOUR_GITHUB_PAT}}
Content-Type: application/json
```

---

### Single repo / submodule layout

Agents live in the same repo as the product. Config is auto-discovered via `.dmtools/config.js`.

```json
{
  "ref": "main",
  "inputs": {
    "config_file": "agents/story_development.json",
    "concurrency_key": "{{issue.key}}",
    "encoded_config": "{{#urlEncode}}{
  \"params\": {
    \"inputJql\": \"key = {{issue.key}}\",
    \"initiator\": \"{{initiator.name}}\"
  }
}{{/urlEncode}}"
  }
}
```

---

### Multi-project layout (agents repo → N product repos)

Agents are in a dedicated repo. Each Jira project has its own folder with a `.dmtools/config.js`
that points to the target product repo. The Jira automation passes `agentConfigsDir` derived
from the Jira project key — one automation rule serves all projects.

```json
{
  "ref": "main",
  "inputs": {
    "config_file": "projects/{{issue.project.key}}/story_development.json",
    "concurrency_key": "{{issue.key}}",
    "encoded_config": "{{#urlEncode}}{
  \"params\": {
    \"inputJql\": \"key = {{issue.key}}\",
    \"initiator\": \"{{initiator.name}}\",
    \"customParams\": {
      \"agentConfigsDir\": \"projects/{{issue.project.key}}\"
    }
  }
}{{/urlEncode}}"
  }
}
```

How it resolves at runtime:
- `config_file` = `projects/ALPHA/story_development.json` — the agent to run
- `agentConfigsDir` = `projects/ALPHA` → discovers `projects/ALPHA/.dmtools/config.js`
- Config contains `repository.owner`/`repository.repo` of the target product repo

**Folder structure:**

```
agents-repo/
  projects/
    ALPHA/
      .dmtools/config.js       ← repository, jira config for ALPHA
      story_development.json   ← agent configs (can share or override shared ones)
      bug_creation.json
    BETA/
      .dmtools/config.js
      story_development.json
  agents/                      ← shared base agents (optional)
    story_development.json
```

Adding a new Jira project = create a new folder. Automation rule stays unchanged.

**`projects/ALPHA/.dmtools/config.js`:**
```js
module.exports = {
  repository: { owner: 'my-org', repo: 'alpha-repo' },
  jira: { project: 'ALPHA', parentTicket: 'ALPHA-1' },
  git: { baseBranch: 'main' },
  agentConfigsDir: 'projects/ALPHA'
};
```

---

### Trigger summary

| Scenario | `config_file` | `encoded_config` extras |
|---|---|---|
| Single repo, submodule | `agents/story_development.json` | `inputJql` only |
| Agents repo, fixed project | `agents/story_development.json` | `configPath: "path/to/.dmtools/config.js"` |
| Agents repo, N projects | `projects/{{issue.project.key}}/story_development.json` | `agentConfigsDir: "projects/{{issue.project.key}}"` |
| SM on schedule | — | GitHub Actions cron, no Jira automation needed |
