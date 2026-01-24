# SF-AgentBench

**A Specialized Benchmarking Framework for Evaluating AI Agents on Salesforce Development**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Version](https://img.shields.io/badge/version-0.2.1-green.svg)](https://github.com/bhanudas/sf-agentbench)

---

## Table of Contents

- [Overview](#overview)
- [What's Included](#whats-included)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Running Benchmarks](#running-benchmarks)
- [Interactive Terminal Monitor](#interactive-terminal-monitor)
- [The Rubric System](#the-rubric-system)
- [Configuration](#configuration)
- [Extending the Framework](#extending-the-framework)
- [Architecture](#architecture)
- [CLI Reference](#cli-reference)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [Roadmap](#roadmap)
- [License](#license)

---

## Overview

SF-AgentBench is a rigorous benchmarking framework designed to evaluate AI agents—such as Claude Code, Gemini CLI, or Aider—on their ability to design and build Salesforce solutions. While existing benchmarks like SWE-bench effectively assess code generation in file-based languages (Python, Java), they fail to capture the architectural complexity of Platform-as-a-Service (PaaS) environments like Salesforce.

Salesforce development is a hybrid practice requiring:
- **Declarative metadata** orchestration
- **Proprietary programming languages** (Apex, SOQL, LWC)
- **Stateful database interactions** within a multi-tenant environment
- **Strict execution limits** (Governor Limits)

SF-AgentBench addresses these unique challenges with a purpose-built evaluation framework.

### ✨ What's New in v0.2.1

- **🔧 CLI Agent Improvements** — Phase-specific timeouts, Gemini/Aider-specific prompts, progressive timeout warnings
- **🤖 Multi-Provider LLM-as-Judge** — Auto-detection for Anthropic, Google, and OpenAI with fallback support
- **📚 Expanded Test Bank** — 75 questions across 6 domains (added Platform Developer I)
- **⚖️ Balanced Answer Distribution** — Eliminated positional bias (was 52% B, now ~25% per option)
- **🏗️ New Tier-2 Tasks** — Account Territory Trigger + Opportunity Discount Calculator

### What's in v0.2.0

- **🎮 Interactive REPL Mode** — Claude Code-style terminal with real-time log streaming
- **📚 Q&A Benchmarking** — Test LLM knowledge on Salesforce concepts
- **⚖️ LLM Judges** — Impartial code evaluation with configurable rubrics
- **🔄 Parallel Execution** — Worker pools with resource-aware scheduling
- **💰 Cost Tracking** — Token usage and USD estimation per run
- **📊 Multi-Model Comparison** — Side-by-side analysis across providers
- **🔗 Cross-Process Monitoring** — Watch benchmarks from separate terminals

---

## What's Included

### Test Banks (Q&A)

| Test Bank | Questions | Domains | Purpose |
|-----------|-----------|---------|---------|
| `salesforce_admin_test_bank.json` | 75 | 6 | Salesforce Admin & Developer certification topics |

**Domains covered:**
- Security & Access (CRUD, FLS, Sharing)
- Data Management (SOQL, DML, Data Loader)
- Automation (Flow, Process Builder, Triggers)
- Reports & Dashboards
- Sales & Service Cloud
- Platform Developer I (Apex, Triggers, Governor Limits, Testing)

### Coding Tasks

| Tier | Task | Description |
|------|------|-------------|
| **Tier 1** | `apex-contact-trigger` | Basic trigger with validation |
| **Tier 2** | `lead-scoring-validation` | Lead assignment with scoring logic |
| **Tier 2** | `case-escalation-flow` | Screen Flow with escalation rules |
| **Tier 2** | `account-territory-trigger` | Trigger + Handler pattern with region-based territory assignment |
| **Tier 2** | `opportunity-discount-calculator` | @InvocableMethod with tiered discount logic |

### Rubrics (LLM Judge Criteria)

| Rubric | Criteria | Purpose |
|--------|----------|---------|
| `salesforce_best_practices.yaml` | 6 | Bulkification, security, tests, readability |
| `security_audit.yaml` | 4 | CRUD/FLS, injection, hardcoded IDs |
| `qa_accuracy.yaml` | 2 | Answer correctness, reasoning quality |

### Supported Models

| Provider | Models | Best For |
|----------|--------|----------|
| **Anthropic** | `claude-sonnet-4-20250514`, `claude-opus-4-20250514` | Highest accuracy, code quality |
| **Google** | `gemini-2.0-flash`, `gemini-2.5-pro`, `gemini-3.0-thinking` | Fast Q&A, cost-effective |
| **OpenAI** | `gpt-4o`, `o1` | General purpose |

---

## Installation

### Prerequisites

| Requirement | Version | Required For |
|-------------|---------|--------------|
| Python | 3.10+ | Core framework |
| Salesforce CLI (`sf`) | Latest | Coding benchmarks |
| DevHub Org | - | Scratch org creation |
| API Keys | - | LLM features |

### Step 1: Clone & Setup Environment

```bash
# Clone the repository
git clone https://github.com/bhanudas/sf-agentbench.git
cd sf-agentbench

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install the package in development mode
pip install -e .
```

### Step 2: Verify Installation

```bash
# Check CLI is available
sf-agentbench --version
# Output: sf-agentbench, version 0.2.0

# List available commands
sf-agentbench --help
```

### Step 3: Configure API Keys

**Option A: Interactive Setup (Recommended)**
```bash
# Set up Anthropic (Claude) API key
sf-agentbench auth set anthropic
# Enter your API key when prompted

# Set up Google (Gemini) API key
sf-agentbench auth set google
# Enter your API key when prompted
```

**Option B: Environment Variables**
```bash
# Add to your shell profile (.bashrc, .zshrc, etc.)
export ANTHROPIC_API_KEY="sk-ant-api03-..."
export GOOGLE_API_KEY="AIzaSy..."
export OPENAI_API_KEY="sk-..."
```

**Option C: Configuration File**
```yaml
# sf-agentbench.yaml
api_keys:
  anthropic: "sk-ant-api03-..."
  google: "AIzaSy..."
```

### Step 4: Verify API Keys

```bash
sf-agentbench auth status
# Output:
#   ✓ Anthropic: Configured (keychain)
#   ✓ Google: Configured (environment)
#   ✗ OpenAI: Not configured
```

### Step 5: (Optional) Salesforce CLI Setup

Required only for coding benchmarks:

```bash
# Install Salesforce CLI
npm install -g @salesforce/cli

# Authenticate to DevHub
sf org login web --set-default-dev-hub --alias mydevhub

# Verify
sf org list
```

---

## Quick Start

### 1. Run Your First Q&A Benchmark

```bash
# Test Gemini's Salesforce knowledge (fastest)
sf-agentbench qa-run salesforce_admin_test_bank.json -m gemini-2.0-flash

# Test with 4 parallel workers for speed
sf-agentbench qa-run salesforce_admin_test_bank.json -m gemini-2.0-flash -w 4

# Test a subset (10 random questions)
sf-agentbench qa-run salesforce_admin_test_bank.json -m claude-sonnet-4-20250514 -n 10
```

### 2. Compare Multiple Models

```bash
# Run all models sequentially
for model in gemini-2.0-flash claude-sonnet-4-20250514 claude-opus-4-20250514; do
  sf-agentbench qa-run salesforce_admin_test_bank.json -m $model -o results/qa_${model}.json
done

# View comparison
sf-agentbench qa-compare
```

### 3. Launch Interactive Monitor

```bash
# Terminal 1: Start the monitor
sf-agentbench interactive --watch

# Terminal 2: Run benchmarks (activity appears in Terminal 1)
sf-agentbench qa-run salesforce_admin_test_bank.json -m gemini-2.0-flash -w 8
```

---

## Running Benchmarks

### Q&A Benchmarks (Knowledge Testing)

Test LLM knowledge on Salesforce certification topics.

```bash
# Basic usage
sf-agentbench qa-run <test_bank_file> [options]

# Options
  -m, --model TEXT     Model to use (e.g., gemini-2.0-flash)
  -n, --sample INT     Run only N random questions
  -d, --domain TEXT    Filter by domain (e.g., "Security & Access")
  -w, --workers INT    Parallel workers (default: 1)
  -v, --verbose        Show detailed output
  -o, --output PATH    Save results to JSON file
```

**Examples:**

```bash
# Full test bank with 8 parallel workers
sf-agentbench qa-run salesforce_admin_test_bank.json -m gemini-2.0-flash -w 8

# Only Security questions
sf-agentbench qa-run salesforce_admin_test_bank.json -m claude-opus-4-20250514 -d "Security & Access"

# Quick 10-question test
sf-agentbench qa-run salesforce_admin_test_bank.json -m gemini-2.0-flash -n 10 -v
```

**Output:**

```
Q&A Benchmark Results: gemini-2.0-flash
============================================================
  Questions: 50
  Correct:   45
  Accuracy:  90.0%
  Duration:  3.9s (0.58s/question)
  Tokens:    5,752 in / 100 out
  Est. Cost: $0.0005

By Domain:
┏━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━┳━━━━━━━━━━┓
┃ Domain                ┃ Correct ┃ Total ┃ Accuracy ┃
┡━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━╇━━━━━━━━━━┩
│ Automation            │       9 │    10 │      90% │
│ Data Management       │       7 │    10 │      70% │
│ Reports & Dashboards  │      10 │    10 │     100% │
│ Sales & Service Cloud │      10 │    10 │     100% │
│ Security & Access     │       9 │    10 │      90% │
└───────────────────────┴─────────┴───────┴──────────┘
```

### Coding Benchmarks

Test AI agents on Salesforce development tasks.

```bash
# List available tasks
sf-agentbench list-tasks

# Run with API-based agent
sf-agentbench benchmark lead-scoring-validation -m gemini-2.0-flash

# Run with CLI-based agent (Claude Code, Gemini CLI)
sf-agentbench run-cli claude-code lead-scoring-validation
```

### Rubric Evaluation (Standalone)

Evaluate code quality using LLM judges:

```python
from sf_agentbench.judges import Rubric, ClaudeJudge
from pathlib import Path

# Load rubric
rubric = Rubric.from_yaml(Path('rubrics/salesforce_best_practices.yaml'))

# Create judge
judge = ClaudeJudge(model='claude-sonnet-4-20250514')

# Evaluate code
result = judge.evaluate(
    code=your_apex_code,
    requirements="Create a bulkified trigger handler",
    rubric=rubric,
    agent_id="my-agent"
)

print(f"Score: {result.overall_score:.2f}")
for criterion in result.criteria:
    print(f"  {criterion.name}: {criterion.score:.2f}")
```

---

## Interactive Terminal Monitor

The REPL provides real-time monitoring of benchmarks running in any terminal.

### Two Modes

| Mode | Command | Use Case |
|------|---------|----------|
| **Interactive** | `sf-agentbench interactive` | Run commands in same terminal |
| **Watch** | `sf-agentbench interactive --watch` | Monitor benchmarks from another terminal |

### Starting the Monitor

```bash
# Interactive mode (type commands)
sf-agentbench interactive --workers 4

# Watch mode (auto-refresh, no input needed)
sf-agentbench interactive --watch
```

### Available Commands

| Command | Description |
|---------|-------------|
| `status` | Show current benchmark status |
| `logs [filter]` | Filter logs (e.g., `logs qa`, `logs claude`) |
| `costs` | Show cost breakdown by model |
| `workers` | Show worker pool status |
| `pause [id]` | Pause work unit(s) |
| `resume [id]` | Resume paused work |
| `cancel <id>` | Cancel a work unit |
| `rubric list` | List available rubrics |
| `rubric show <name>` | Show rubric details |
| `help` | Show all commands |
| `quit` | Exit |

### Cross-Process Monitoring

The monitor uses a shared SQLite event store to display activity from any `sf-agentbench` process:

```bash
# Terminal 1: Start monitor
sf-agentbench interactive --watch

# Terminal 2: Run benchmarks (appears in Terminal 1)
sf-agentbench qa-run salesforce_admin_test_bank.json -m gemini-2.0-flash -w 8
```

---

## The Rubric System

### How It Works

1. **Rubric Definition** — YAML files define weighted evaluation criteria
2. **LLM Judge** — Multi-provider support (Anthropic, Google, OpenAI) with auto-detection
3. **Scoring** — Each criterion gets 0.0-1.0, weighted average for overall
4. **Fallback** — Heuristic evaluation when API calls fail (supports Apex, Flows, Validation Rules)
5. **Logging** — Full prompts and responses stored for review

### Supported Providers

The rubric evaluator automatically detects the provider from the model name:

| Provider | Model Patterns | Example |
|----------|---------------|---------|
| **Anthropic** | `claude-*` | `claude-sonnet-4-20250514` |
| **Google** | `gemini-*` | `gemini-2.0-flash` |
| **OpenAI** | `gpt-*`, `o1*` | `gpt-4o`, `o1` |

Configure in `sf-agentbench.yaml`:
```yaml
rubric:
  model: claude-sonnet-4-20250514  # Auto-detects Anthropic
  provider: auto  # Or explicitly: anthropic, google, openai
  timeout_seconds: 120
  fallback_to_heuristic: true
```

### Rubric Structure

```yaml
# rubrics/salesforce_best_practices.yaml
name: Salesforce Best Practices
version: "1.0"
description: Evaluates Apex code against Salesforce development standards
judge_model: claude-opus-4-20250514

criteria:
  - name: Bulkification
    weight: 0.25
    description: |
      Are DML and SOQL operations performed on collections?
      Are there any queries or DML inside loops?
    scoring_guide:
      1.0: "All operations bulkified, no SOQL/DML in loops"
      0.7: "Minor issues, mostly bulkified"
      0.4: "Some SOQL/DML in loops"
      0.0: "Severe bulkification violations"

  - name: Security Best Practices
    weight: 0.20
    description: |
      Are CRUD/FLS checks present?
      Are hardcoded IDs avoided?
    scoring_guide:
      1.0: "Full CRUD/FLS checks, no hardcoded IDs"
      0.5: "Partial security checks"
      0.0: "No security considerations"
```

### Using Judges Programmatically

```python
from sf_agentbench.judges import ClaudeJudge, GeminiJudge, ConsensusJudge, Rubric

# Single judge
judge = ClaudeJudge(model='claude-sonnet-4-20250514', verbose=True)
result = judge.evaluate(code, requirements, rubric)

# Multi-judge consensus
judges = [
    ClaudeJudge('claude-sonnet-4-20250514'),
    ClaudeJudge('claude-opus-4-20250514'),
]
consensus = ConsensusJudge(judges, method='average')
result = consensus.evaluate(code, requirements, rubric)
```

### Judge Logging

Enable verbose logging to review judge reasoning:

```yaml
# sf-agentbench.yaml
judges:
  verbose_logging: true
  log_prompts: true
  log_responses: true
```

Logs are stored in the database and can be reviewed:

```bash
sf-agentbench judge-logs --last 10
```

---

## Configuration

### Main Configuration File

```yaml
# sf-agentbench.yaml

# Default model for benchmarks
model: gemini-2.0-flash

# Salesforce settings
devhub_username: admin@mydevhub.org
scratch_org_duration: 7  # days
cleanup_orgs: true

# Task directories
tasks_dir: ./tasks
results_dir: ./results

# Worker configuration
workers:
  max_workers: 8
  qa_workers: 8        # Parallel Q&A workers
  coding_workers: 2    # Parallel coding workers (resource-intensive)

# Cost tracking
cost_tracking:
  enabled: true
  warn_threshold_usd: 1.0
  budget_limit_usd: 10.0

# Judge configuration
judges:
  default_model: claude-opus-4-20250514
  verbose_logging: true
  consensus_method: average  # average, majority, min, max

# Evaluation weights (for coding benchmarks)
evaluation_weights:
  deployment: 0.20
  functional_tests: 0.40
  static_analysis: 0.10
  metadata_diff: 0.15
  rubric: 0.15

# Logging
logging:
  level: INFO
  file: logs/sf-agentbench.log
```

### Environment Variables

| Variable | Purpose | Example |
|----------|---------|---------|
| `ANTHROPIC_API_KEY` | Claude API access | `sk-ant-api03-...` |
| `GOOGLE_API_KEY` | Gemini API access | `AIzaSy...` |
| `OPENAI_API_KEY` | OpenAI API access | `sk-...` |
| `SF_DEVHUB_USERNAME` | Default DevHub org | `admin@mydevhub.org` |
| `SF_AGENTBENCH_CONFIG` | Config file path | `./custom-config.yaml` |

---

## Extending the Framework

### Adding New Test Banks (Q&A)

1. **Create JSON file** in `docs/data/`:

```json
{
  "id": "my_custom_test_bank",
  "name": "My Custom Test Bank",
  "description": "Custom questions for specific topics",
  "version": "1.0",
  "domains": ["Domain A", "Domain B"],
  "difficulty": ["easy", "medium", "hard"],
  "questions": [
    {
      "id": "Q001",
      "question": "What is the maximum number of records returned by a SOQL query?",
      "options": {
        "A": "10,000",
        "B": "50,000",
        "C": "100,000",
        "D": "Unlimited"
      },
      "correct_answer": "B",
      "explanation": "SOQL queries return a maximum of 50,000 records by default.",
      "domain": "Data Management",
      "difficulty": "easy",
      "source": "Salesforce Documentation"
    }
  ]
}
```

2. **Run tests:**

```bash
sf-agentbench qa-run my_custom_test_bank.json -m gemini-2.0-flash -n 5
```

### Adding New Coding Tasks

1. **Create task directory** in `tasks/tier-X/`:

```
tasks/tier-2/my-custom-task/
├── README.md              # Task description and requirements
├── sfdx-project.json      # Salesforce DX project config
├── config/
│   └── project-scratch-def.json  # Scratch org definition
├── force-app/
│   └── main/default/
│       ├── classes/       # Apex classes (starter or golden)
│       ├── triggers/      # Apex triggers
│       ├── flows/         # Flows
│       └── objects/       # Custom objects
├── data/
│   └── sample-data-plan.json  # Test data
└── golden/                # Reference solution (for evaluation)
    └── classes/
```

2. **Create task metadata** in `task.yaml`:

```yaml
id: my-custom-task
name: My Custom Task
description: Build a custom Salesforce solution
tier: 2
estimated_time_minutes: 30
skills_tested:
  - Apex Triggers
  - SOQL Queries
  - Bulkification
evaluation:
  rubric: salesforce_best_practices
  test_class: MyCustomTaskTest
  min_coverage: 75
```

3. **Verify task loads:**

```bash
sf-agentbench list-tasks
sf-agentbench show-task my-custom-task
```

### Adding New Rubrics

1. **Create YAML file** in `rubrics/`:

```yaml
# rubrics/my_custom_rubric.yaml
name: My Custom Rubric
version: "1.0"
description: Custom evaluation criteria
judge_model: claude-sonnet-4-20250514

criteria:
  - name: My Criterion
    weight: 0.5
    description: What this criterion evaluates
    scoring_guide:
      1.0: "Excellent implementation"
      0.7: "Good with minor issues"
      0.4: "Needs improvement"
      0.0: "Does not meet requirements"

  - name: Another Criterion
    weight: 0.5
    description: Another thing to evaluate
    scoring_guide:
      1.0: "Perfect"
      0.5: "Acceptable"
      0.0: "Unacceptable"
```

2. **Use in evaluations:**

```python
rubric = Rubric.from_yaml(Path('rubrics/my_custom_rubric.yaml'))
result = judge.evaluate(code, requirements, rubric)
```

### Adding New LLM Providers

1. **Create judge class** in `src/sf_agentbench/judges/`:

```python
# src/sf_agentbench/judges/my_provider_judge.py
from sf_agentbench.judges.base import Judge, JudgeResult, Rubric

class MyProviderJudge(Judge):
    """Judge implementation for My Provider."""
    
    def __init__(self, model: str, api_key: str | None = None, **kwargs):
        super().__init__(model=model, **kwargs)
        self.api_key = api_key or os.getenv("MY_PROVIDER_API_KEY")
        # Initialize your client
        
    def evaluate(
        self,
        code: str,
        requirements: str,
        rubric: Rubric,
        agent_id: str = "unknown",
    ) -> JudgeResult:
        # Build prompt using self._build_prompt(code, requirements, rubric)
        prompt = self._build_prompt(code, requirements, rubric)
        
        # Call your API
        response = self._call_api(prompt)
        
        # Parse response into JudgeResult
        return self._parse_response(response, rubric)
```

2. **Register in `__init__.py`:**

```python
# src/sf_agentbench/judges/__init__.py
from sf_agentbench.judges.my_provider_judge import MyProviderJudge
__all__ = [..., "MyProviderJudge"]
```

### Adding New Models to Existing Providers

Update the model registry in `src/sf_agentbench/qa/runner.py`:

```python
MODEL_PROVIDERS = {
    # Existing...
    "my-new-model": "google",  # or "anthropic", "openai"
}
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                      SF-AgentBench v0.2.0                           │
├─────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │    REPL      │  │   Worker     │  │      LLM Judges          │  │
│  │   Console    │  │    Pool      │  │  (Claude, Gemini)        │  │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘  │
│         │                 │                      │                  │
│         └─────────────────┴──────────────────────┘                  │
│                           │                                         │
│                    ┌──────▼──────┐                                  │
│                    │  Event Bus  │ ◄─── Cross-process SQLite        │
│                    └──────┬──────┘                                  │
│         ┌─────────────────┼─────────────────┐                       │
│         ▼                 ▼                 ▼                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │ QA Runner    │  │   Coding     │  │  Validator   │              │
│  │              │  │  Executor    │  │              │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
│         │                 │                 │                       │
│         └─────────────────┴─────────────────┘                       │
│                           │                                         │
│                    ┌──────▼──────┐                                  │
│                    │  Unified    │                                  │
│                    │   Storage   │ ◄─── SQLite + JSON               │
│                    └─────────────┘                                  │
├─────────────────────────────────────────────────────────────────────┤
│                    Agent-Computer Interface (ACI)                   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐       │
│  │sf_deploy │ │sf_query  │ │sf_test   │ │sf_scan_code      │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘       │
├─────────────────────────────────────────────────────────────────────┤
│                     Salesforce CLI (sf)                             │
├─────────────────────────────────────────────────────────────────────┤
│                   Ephemeral Scratch Org Pool                        │
└─────────────────────────────────────────────────────────────────────┘
```

### Key Components

| Component | Location | Purpose |
|-----------|----------|---------|
| **CLI** | `src/sf_agentbench/cli.py` | Command-line interface |
| **QA Runner** | `src/sf_agentbench/qa/runner.py` | Q&A test execution |
| **Judges** | `src/sf_agentbench/judges/` | LLM-as-a-Judge evaluation |
| **REPL** | `src/sf_agentbench/repl/` | Interactive terminal |
| **Events** | `src/sf_agentbench/events/` | Cross-process communication |
| **Workers** | `src/sf_agentbench/workers/` | Parallel execution pool |
| **Storage** | `src/sf_agentbench/storage/` | Results persistence |

---

## CLI Reference

```bash
sf-agentbench --help

Commands:
  # Core Benchmarking
  run              Run a single benchmark task
  run-all          Run all benchmark tasks
  run-cli          Run with CLI-based AI agent
  benchmark        Run with API-based agent

  # Q&A Testing
  qa-run           Run Q&A tests against an LLM
  qa-list          List available test banks
  qa-compare       Compare model performance
  qa-domains       Analyze by domain
  qa-playback      Replay prompts and responses
  qa-history       Show run history

  # Interactive
  interactive      Launch REPL mode
    --watch        Watch mode (auto-refresh, no input)
    --workers N    Number of workers

  # Information
  list-tasks       List all benchmark tasks
  list-models      List supported AI models
  show-task        Show task details

  # Configuration
  init             Initialize project
  auth set <provider>   Set API key
  auth status      Show authentication status

  # Testing
  e2e-test         Run end-to-end tests
```

---

## Troubleshooting

### Common Issues

#### "No API key found"

```bash
# Check authentication status
sf-agentbench auth status

# Set key interactively
sf-agentbench auth set anthropic

# Or use environment variable
export ANTHROPIC_API_KEY="sk-ant-..."
```

#### "Model not found"

```bash
# List available models
sf-agentbench list-models

# Use exact model ID
sf-agentbench qa-run test.json -m claude-sonnet-4-20250514  # Not "claude-sonnet"
```

#### "Thinking models return UNKNOWN"

Gemini "thinking" models (`gemini-2.5-pro`, `gemini-3.0-thinking`) return extended reasoning instead of direct answers. Use `gemini-2.0-flash` for Q&A testing.

#### "Q&A returns UNKNOWN with 0.0s response time"

This usually indicates missing Python dependencies for the LLM providers:

```bash
# Install required packages
pip install google-genai anthropic openai
```

#### "CLI agent deployment failures / timeouts"

CLI agents (Gemini CLI, Aider) may need longer timeouts and specific prompts. Configure in your agent config:

```yaml
cli_agents:
  gemini:
    phase_timeouts:
      build: 900    # 15 minutes for complex tasks
      deploy: 600   # 10 minutes for deployment
      test: 300     # 5 minutes for testing
    prompt_style: gemini  # Use Gemini-specific prompts
    extra_args:
      - "--sandbox=false"
```

#### "Cross-process monitoring not working"

Ensure both terminals are running from the same project directory:

```bash
# Both terminals should be in:
cd /path/to/sf-agentbench
source .venv/bin/activate
```

#### "Scratch org creation failed"

```bash
# Verify DevHub authentication
sf org list

# Re-authenticate if needed
sf org login web --set-default-dev-hub
```

### Debug Mode

```bash
# Enable verbose logging
export SF_AGENTBENCH_LOG_LEVEL=DEBUG
sf-agentbench qa-run test.json -m gemini-2.0-flash -v

# Check log files
tail -f logs/sf-agentbench.log
```

### Getting Help

1. Check the [Troubleshooting Guide](docs/troubleshooting.md)
2. Search [GitHub Issues](https://github.com/bhanudas/sf-agentbench/issues)
3. Open a new issue with:
   - Python version (`python --version`)
   - OS and version
   - Full error message
   - Steps to reproduce

---

## Contributing

We welcome contributions! Here's how to get started:

### Areas for Contribution

| Area | What's Needed |
|------|---------------|
| **Test Banks** | More Q&A questions, new certification domains |
| **Coding Tasks** | Tier 3 & 4 tasks, LWC challenges |
| **Rubrics** | Industry-specific evaluation criteria |
| **Providers** | New LLM integrations (Cohere, Mistral, etc.) |
| **Documentation** | Tutorials, examples, translations |

### Development Setup

```bash
# Clone and setup
git clone https://github.com/bhanudas/sf-agentbench.git
cd sf-agentbench
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run tests
pytest tests/

# Run linter
ruff check src/

# Run type checker
mypy src/
```

### Submitting Changes

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes
4. Add tests for new functionality
5. Run the test suite (`pytest tests/`)
6. Commit with clear messages
7. Push and open a Pull Request

---

## Roadmap

### Phase 1: Foundation ✅
- [x] ACI tool wrappers for core `sf` commands
- [x] Basic harness for task loading and evaluation
- [x] 5-layer evaluation pipeline
- [x] Sample Tier 1 & 2 tasks

### Phase 2: Intelligence ✅ (v0.2.0 - v0.2.1)
- [x] Q&A benchmarking framework
- [x] LLM-as-a-Judge with rubric scoring
- [x] Multi-model support (Claude, Gemini, OpenAI)
- [x] Interactive REPL mode
- [x] Parallel execution with worker pools
- [x] Cost tracking and estimation
- [x] Multi-judge consensus
- [x] Cross-process monitoring
- [x] **v0.2.1:** Multi-provider LLM-as-Judge (Anthropic, Google, OpenAI)
- [x] **v0.2.1:** CLI agent timeout handling with phase-specific configs
- [x] **v0.2.1:** Expanded test bank (75 questions, 6 domains)
- [x] **v0.2.1:** Balanced answer distribution (eliminated positional bias)
- [x] **v0.2.1:** Platform Developer I certification questions
- [x] **v0.2.1:** New Tier-2 coding tasks (territory trigger, discount calculator)

### Phase 3: Scale (Planned)
- [ ] Scratch Org pool management
- [ ] Distributed worker nodes
- [ ] Web dashboard
- [ ] Public leaderboard
- [ ] 10+ Tier 3 tasks

### Phase 4: Research (Planned)
- [ ] Agent behavior analysis
- [ ] Failure pattern detection
- [ ] Automated task generation
- [ ] Research paper submission

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

## Acknowledgments

- Inspired by [SWE-bench](https://www.swebench.com/) and [SWE-agent](https://swe-agent.com/)
- Task methodology adapted from [Salesforce Trailhead Superbadges](https://trailhead.salesforce.com/superbadges)
- Built for the AI agent research community

---

<p align="center">
  <strong>SF-AgentBench v0.2.1</strong> — Bridging AI Agents and Enterprise Platform Development
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> •
  <a href="#running-benchmarks">Run Benchmarks</a> •
  <a href="#extending-the-framework">Extend</a> •
  <a href="#contributing">Contribute</a>
</p>
