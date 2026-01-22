# SF-AgentBench

**A Specialized Benchmarking Framework for Evaluating AI Agents on Salesforce Development**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Version](https://img.shields.io/badge/version-0.2.0-green.svg)](https://github.com/bhanudas/sf-agentbench)

---

## Overview

SF-AgentBench is a rigorous benchmarking framework designed to evaluate AI agents—such as Claude Code, Gemini CLI, or Aider—on their ability to design and build Salesforce solutions. While existing benchmarks like SWE-bench effectively assess code generation in file-based languages (Python, Java), they fail to capture the architectural complexity of Platform-as-a-Service (PaaS) environments like Salesforce.

Salesforce development is a hybrid practice requiring:
- **Declarative metadata** orchestration
- **Proprietary programming languages** (Apex, SOQL, LWC)
- **Stateful database interactions** within a multi-tenant environment
- **Strict execution limits** (Governor Limits)

SF-AgentBench addresses these unique challenges with a purpose-built evaluation framework.

## ✨ What's New in v0.2.0

- **🎮 Interactive REPL Mode** — Claude Code-style terminal with real-time log streaming
- **📚 Q&A Benchmarking** — Test LLM knowledge on Salesforce concepts
- **⚖️ LLM Judges** — Impartial code evaluation with configurable rubrics
- **🔄 Parallel Execution** — Worker pools with resource-aware scheduling
- **💰 Cost Tracking** — Token usage and USD estimation per run
- **📊 Multi-Model Comparison** — Side-by-side analysis across providers

## ✨ Features

### 🎮 Interactive REPL Mode

A Claude Code-style interface for real-time benchmark monitoring:

```bash
sf-agentbench interactive --workers 4
```

```
╭─ SF-AgentBench REPL ────────────────────────────────────────╮
│ Workers: 4 active │ Queue: 12 pending │ Cost: $0.42        │
├─────────────────────────────────────────────────────────────┤
│ [14:32:01] ✓ gemini-2.0-flash completed Q001 (0.8s)        │
│ [14:32:02] → claude-sonnet-4 processing Q002...            │
│ [14:32:03] ✓ gemini-2.0-flash completed Q003 (1.2s)        │
╰─────────────────────────────────────────────────────────────╯
> status
> logs claude
> pause
> help
```

**Available Commands:**
| Command | Description |
|---------|-------------|
| `status` | Show current benchmark status |
| `logs [agent]` | Filter logs by agent |
| `pause [id]` | Pause work unit(s) |
| `resume [id]` | Resume paused work |
| `cancel <id>` | Cancel a work unit |
| `costs` | Show cost breakdown |
| `workers` | Show worker status |
| `quit` | Exit the REPL |

### 📚 Q&A Benchmarking

Test LLM knowledge on Salesforce certification topics:

```bash
# List available test banks
sf-agentbench qa-list

# Run Q&A tests against a model
sf-agentbench qa-run salesforce_admin_test_bank.json -m gemini-2.0-flash

# Compare model performance
sf-agentbench qa-compare

# Replay exact prompts and responses
sf-agentbench qa-playback <run-id>
```

**Sample Output:**
```
Q&A Benchmark Results: gemini-2.0-flash
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Questions: 50 │ Correct: 42 │ Score: 84.0%

By Domain:
  Security & Access:    90.0% (9/10)
  Data Management:      85.0% (17/20)
  Automation:           80.0% (8/10)
  Reports & Dashboards: 80.0% (8/10)

Estimated Cost: $0.0234
```

### ⚖️ LLM Judges with Rubric Scoring

Impartial evaluation of agent-generated code using LLMs like Claude Opus 4.5:

```yaml
# rubrics/salesforce_best_practices.yaml
name: Salesforce Best Practices
version: "1.0"
judge_model: claude-opus-4-20250514

criteria:
  - name: Bulkification
    weight: 2.0
    description: Code handles bulk operations efficiently
    scoring_guide:
      1.0: All DML/SOQL in loops eliminated, uses collections
      0.5: Partial bulkification, some operations still in loops
      0.0: No bulkification, SOQL/DML queries inside loops

  - name: Governor Limit Awareness
    weight: 1.5
    description: Proper handling of Salesforce limits
```

**Multi-Judge Consensus:**
```python
from sf_agentbench.judges import ConsensusJudge, ClaudeJudge, GeminiJudge

judges = [ClaudeJudge("claude-opus-4"), GeminiJudge("gemini-2.5-pro")]
consensus = ConsensusJudge(judges, method="average")
result = consensus.evaluate(code, requirements, rubric)
```

### 🖥️ CLI-Based Agent Testing

Run real AI coding assistants against Salesforce tasks:

```bash
# List available CLI agents
sf-agentbench list-cli-agents

# Run a benchmark with Claude Code
sf-agentbench run-cli claude-code lead-scoring-validation

# Run with Gemini CLI
sf-agentbench run-cli gemini-cli case-escalation-flow
```

**Supported CLI Agents:**
| Agent | Command | Description |
|-------|---------|-------------|
| Claude Code | `claude` | Anthropic's coding assistant |
| Gemini CLI | `gemini` | Google's AI assistant |
| Aider | `aider` | Open-source AI pair programmer |

### 🎯 Curriculum-Aligned Evaluation

Grounded in official Salesforce certifications:
- **Administrator (ADM-201)** — Schema, automation, security
- **Platform Developer I & II (PD1/PD2)** — Apex, integrations, LWC

### 📊 5-Layer Evaluation Pipeline

| Layer | Weight | Metric | Description |
|-------|--------|--------|-------------|
| **1** | 20% | Deployment | Can the solution deploy without errors? |
| **2** | 40% | Functional Tests | Do Apex tests pass? What's the coverage? |
| **3** | 10% | Static Analysis | Code quality via PMD/Code Analyzer |
| **4** | 15% | Metadata Diff | Semantic comparison against golden config |
| **5** | 15% | LLM Rubric | Design patterns, bulkification, best practices |

### 🔧 Agent-Computer Interface (ACI)

11 tools wrapping the Salesforce CLI (`sf`) with structured JSON I/O:

| Tool | Description |
|------|-------------|
| `sf_deploy` | Deploy metadata to Scratch Org |
| `sf_retrieve` | Retrieve metadata from org |
| `sf_run_apex_tests` | Execute Apex tests with coverage |
| `sf_run_anonymous` | Run anonymous Apex code |
| `sf_query` | Execute SOQL queries |
| `sf_create_record` | Create sObject records |
| `sf_import_data` | Import data from plan files |
| `sf_scan_code` | Run PMD static analysis |
| `sf_org_create` | Create Scratch Orgs |
| `sf_org_delete` | Delete Scratch Orgs |
| `sf_org_open` | Get org login URL |

## 🏗️ Architecture

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
│                    │  Event Bus  │                                  │
│                    └──────┬──────┘                                  │
│         ┌─────────────────┼─────────────────┐                       │
│         ▼                 ▼                 ▼                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │ QA Executor  │  │   Coding     │  │  Validator   │              │
│  │              │  │  Executor    │  │              │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
│         │                 │                 │                       │
│         └─────────────────┴─────────────────┘                       │
│                           │                                         │
│                    ┌──────▼──────┐                                  │
│                    │  Unified    │                                  │
│                    │   Storage   │                                  │
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

## 📁 Project Structure

```
sf-agentbench/
├── README.md
├── LICENSE
├── pyproject.toml
├── requirements.txt
├── sf-agentbench.yaml              # Main configuration
│
├── docs/
│   ├── data/                       # Q&A test banks
│   │   └── salesforce_admin_test_bank.json
│   └── development/
│       └── Salesforce AI Benchmark Design.md
│
├── rubrics/                        # LLM Judge rubrics
│   ├── salesforce_best_practices.yaml
│   ├── security_audit.yaml
│   └── qa_accuracy.yaml
│
├── src/sf_agentbench/
│   ├── __init__.py
│   ├── cli.py                      # CLI entry point
│   ├── config.py                   # Configuration management
│   ├── models.py                   # Legacy data models
│   │
│   ├── domain/                     # Core domain models (v0.2)
│   │   ├── models.py               # Benchmark, Test, Agent, WorkUnit
│   │   ├── costs.py                # Token usage & cost tracking
│   │   └── metrics.py              # Performance metrics
│   │
│   ├── events/                     # Event-driven architecture
│   │   ├── bus.py                  # Pub/sub event bus
│   │   └── types.py                # Event type definitions
│   │
│   ├── workers/                    # Parallel execution
│   │   ├── pool.py                 # Worker pool management
│   │   ├── scheduler.py            # Priority scheduling
│   │   └── base.py                 # Worker base class
│   │
│   ├── executors/                  # Test executors
│   │   ├── qa_executor.py          # Q&A test execution
│   │   ├── coding_executor.py      # CLI agent execution
│   │   └── validator.py            # Result validation
│   │
│   ├── judges/                     # LLM-as-a-Judge
│   │   ├── base.py                 # Judge interface & Rubric
│   │   ├── claude_judge.py         # Claude implementation
│   │   ├── gemini_judge.py         # Gemini implementation
│   │   ├── consensus.py            # Multi-judge voting
│   │   └── logging.py              # Verbose judge logging
│   │
│   ├── repl/                       # Interactive terminal
│   │   ├── console.py              # REPL main loop
│   │   ├── commands.py             # Command parsing
│   │   └── renderer.py             # Log & status rendering
│   │
│   ├── reports/                    # Report generation
│   │   ├── generator.py            # Multi-format reports
│   │   └── comparison.py           # Model comparison views
│   │
│   ├── storage/                    # Data persistence
│   │   ├── store.py                # Legacy SQLite store
│   │   └── unified.py              # Unified storage (v0.2)
│   │
│   ├── aci/                        # Agent-Computer Interface
│   ├── harness/                    # Benchmark orchestration
│   ├── evaluators/                 # 5-layer evaluation
│   ├── agents/                     # API-based agents
│   ├── qa/                         # Q&A framework
│   └── auth/                       # Authentication
│
├── tasks/                          # Benchmark tasks
│   ├── tier-1/
│   └── tier-2/
│
├── results/                        # Run outputs
│   ├── benchmark_results.db
│   └── runs/
│
└── tests/
    ├── e2e/                        # End-to-end tests
    │   └── test_runner.py
    └── fixtures/                   # Test fixtures
        ├── sample_code/
        ├── rubrics/
        └── qa/
```

## 🚀 Getting Started

### Prerequisites

- **Python 3.10+**
- **Salesforce CLI** (`sf`) — [Install Guide](https://developer.salesforce.com/tools/salesforcecli)
- **DevHub-enabled Org** — Required for Scratch Org creation
- **API Keys** (optional) — For LLM-based features

### Installation

```bash
# Clone the repository
git clone https://github.com/bhanudas/sf-agentbench.git
cd sf-agentbench

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install in development mode
pip install -e .

# Initialize with sample tasks
sf-agentbench init
```

### Authentication Setup

```bash
# Set up API keys for LLM providers
sf-agentbench auth set anthropic
sf-agentbench auth set google

# Or use environment variables
export ANTHROPIC_API_KEY="sk-..."
export GOOGLE_API_KEY="AIza..."
```

### Quick Start

#### 1. Run Q&A Benchmarks

```bash
# Test LLM knowledge on Salesforce topics
sf-agentbench qa-run salesforce_admin_test_bank.json -m gemini-2.0-flash

# Compare multiple models
sf-agentbench qa-run salesforce_admin_test_bank.json -m claude-sonnet-4-20250514
sf-agentbench qa-compare
```

#### 2. Run Coding Benchmarks

```bash
# List available tasks
sf-agentbench list-tasks

# Run with a CLI agent
sf-agentbench run-cli claude-code lead-scoring-validation

# Run with an API-based agent
sf-agentbench benchmark lead-scoring-validation -m gemini-2.0-flash
```

#### 3. Interactive Mode

```bash
# Launch the REPL for real-time monitoring
sf-agentbench interactive --workers 4
```

#### 4. Run E2E Tests

```bash
# Verify the system is working
sf-agentbench e2e-test -v
```

## 🤖 Supported Models

### Anthropic (Claude)
| Model ID | Name | Context |
|----------|------|---------|
| `claude-sonnet-4-20250514` | Claude Sonnet 4 | 200K |
| `claude-opus-4-20250514` | Claude Opus 4 | 200K |

### Google (Gemini)
| Model ID | Name | Context |
|----------|------|---------|
| `gemini-2.0-flash` | Gemini 2.0 Flash | 1M |
| `gemini-2.5-pro` | Gemini 2.5 Pro | 1M |
| `gemini-3.0-thinking` | Gemini 3.0 Thinking | 2M |

### OpenAI
| Model ID | Name | Context |
|----------|------|---------|
| `gpt-4o` | GPT-4o | 128K |
| `o1` | OpenAI o1 | 200K |

List all models: `sf-agentbench list-models`

## ⚙️ Configuration

Edit `sf-agentbench.yaml`:

```yaml
# Active model
model: gemini-2.5-pro

# Salesforce settings
devhub_username: admin@mydevhub.org

# Worker configuration
workers:
  qa_workers: 8          # Parallel Q&A workers
  coding_workers: 2      # Parallel coding workers

# Cost tracking
cost_tracking:
  enabled: true
  warn_threshold_usd: 1.0

# Judge configuration
judges:
  default_model: claude-opus-4-20250514
  verbose_logging: true
  consensus_method: average

# Evaluation weights
evaluation_weights:
  deployment: 0.20
  functional_tests: 0.40
  static_analysis: 0.10
  metadata_diff: 0.15
  rubric: 0.15
```

## 📊 Reports

Generate comprehensive reports:

```bash
# Markdown report
sf-agentbench report --format markdown -o report.md

# HTML report with charts
sf-agentbench report --format html -o report.html

# JSON for programmatic access
sf-agentbench report --format json -o report.json
```

**Report Contents:**
- Model comparison tables
- Score breakdowns by category
- Cost analysis
- Rubric drill-down with criterion scores
- Trend analysis over time

## 📋 CLI Reference

```bash
sf-agentbench --help

Commands:
  # Core Benchmarking
  run              Run a single benchmark task
  run-all          Run all benchmark tasks
  run-cli          Run with CLI-based AI agent
  run-parallel     Run multiple benchmarks in parallel
  benchmark        Run with API-based agent

  # Q&A Testing
  qa-list          List available test banks
  qa-run           Run Q&A tests against an LLM
  qa-compare       Compare model performance
  qa-domains       Analyze by domain
  qa-playback      Replay prompts and responses
  qa-history       Show run history
  qa-export        Export results to CSV

  # Interactive
  interactive      Launch REPL mode

  # Information
  list-tasks       List all benchmark tasks
  list-models      List supported AI models
  list-cli-agents  List CLI-based agents
  show-task        Show task details

  # Configuration
  init             Initialize project
  validate         Validate configuration
  auth             Manage API authentication

  # Testing
  e2e-test         Run end-to-end tests
```

## 🗺️ Roadmap

### Phase 1: Foundation ✅
- [x] ACI tool wrappers for core `sf` commands
- [x] Basic harness for task loading and evaluation
- [x] 5-layer evaluation pipeline
- [x] Sample Tier 1 & 2 tasks

### Phase 2: Intelligence ✅ (v0.2.0)
- [x] Q&A benchmarking framework
- [x] LLM-as-a-Judge with rubric scoring
- [x] Multi-model support (Claude, Gemini, OpenAI)
- [x] Interactive REPL mode
- [x] Parallel execution with worker pools
- [x] Cost tracking and estimation
- [x] Multi-judge consensus

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

## 🧪 Testing

```bash
# Run unit tests
pytest tests/

# Run E2E tests
sf-agentbench e2e-test -v

# Run specific category
sf-agentbench e2e-test --category judges
```

## 📚 Documentation

- [Technical Design Document](docs/development/Salesforce%20AI%20Benchmark%20Design.md)
- [Q&A Test Bank Schema](docs/data/README.md)
- [Rubric Configuration Guide](rubrics/README.md)

## 🤝 Contributing

Contributions are welcome! Areas for contribution:
- New benchmark tasks (especially Tier 3 & 4)
- Additional LLM provider integrations
- Rubric templates for different use cases
- Documentation improvements

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Inspired by [SWE-bench](https://www.swebench.com/) and [SWE-agent](https://swe-agent.com/)
- Task methodology adapted from [Salesforce Trailhead Superbadges](https://trailhead.salesforce.com/superbadges)
- Built for the AI agent research community

---

<p align="center">
  <strong>SF-AgentBench v0.2.0</strong> — Bridging AI Agents and Enterprise Platform Development
</p>
