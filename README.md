# SF-AgentBench

**A Specialized Benchmarking Framework for Evaluating AI Agents on Salesforce Development**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

---

## Overview

SF-AgentBench is a rigorous benchmarking framework designed to evaluate AI agents—such as Claude Code, Codex, or Gemini Orchestrator—on their ability to design and build Salesforce solutions. While existing benchmarks like SWE-bench effectively assess code generation in file-based languages (Python, Java), they fail to capture the architectural complexity of Platform-as-a-Service (PaaS) environments like Salesforce.

Salesforce development is a hybrid practice requiring:
- **Declarative metadata** orchestration
- **Proprietary programming languages** (Apex, SOQL, LWC)
- **Stateful database interactions** within a multi-tenant environment
- **Strict execution limits** (Governor Limits)

SF-AgentBench addresses these unique challenges with a purpose-built evaluation framework.

## ✨ Features

### 🖥️ Interactive Terminal UI

A beautiful, user-friendly terminal interface built with [Textual](https://textual.textualize.io/):

```
┌─────────────────────────────────────────────────────────────────┐
│                    🚀 SF-AgentBench Dashboard                    │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐            │
│  │    5     │ │    2     │ │    2     │ │    1     │            │
│  │  Total   │ │  Tier 1  │ │  Tier 2  │ │  Tier 3  │            │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘            │
│  ─────────────────────────────────────────────────────────────  │
│  [Browse Tasks] [Run Benchmark] [View Results] [Configuration]  │
└─────────────────────────────────────────────────────────────────┘
│ D Dashboard │ T Tasks │ R Run │ S Results │ C Config │ Q Quit   │
└─────────────────────────────────────────────────────────────────┘
```

**5 Interactive Screens:**
| Screen | Key | Description |
|--------|-----|-------------|
| Dashboard | `D` | Overview stats, quick actions, getting started |
| Tasks | `T` | Browse tasks by tier, view requirements |
| Run | `R` | Execute benchmarks with real-time progress |
| Results | `S` | Score history, layer breakdown, CSV export |
| Config | `C` | Edit all settings with tabbed interface |

### 🎯 Curriculum-Aligned Evaluation

Grounded in official Salesforce certifications:
- **Administrator (ADM-201)** — Schema, automation, security
- **Platform Developer I & II (PD1/PD2)** — Apex, integrations, LWC

### 🏆 Superbadge Methodology

Uses complex, scenario-based problem solving as the gold standard—moving beyond atomic code generation to holistic solution architecture.

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

### 📊 5-Layer Evaluation Pipeline

| Layer | Weight | Metric | Description |
|-------|--------|--------|-------------|
| **1** | 20% | Deployment | Can the solution deploy without errors? |
| **2** | 40% | Functional Tests | Do Apex tests pass? What's the coverage? |
| **3** | 10% | Static Analysis | Code quality via PMD/Code Analyzer |
| **4** | 15% | Metadata Diff | Semantic comparison against golden config |
| **5** | 15% | LLM Rubric | Design patterns, bulkification, best practices |

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     SF-AgentBench Harness                       │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │   Task      │  │   Agent     │  │      Evaluation         │  │
│  │   Loader    │  │   Runner    │  │      Pipeline           │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│                    Agent-Computer Interface (ACI)               │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐   │
│  │sf_deploy │ │sf_query  │ │sf_test   │ │sf_scan_code      │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘   │
├─────────────────────────────────────────────────────────────────┤
│                     Salesforce CLI (sf)                         │
├─────────────────────────────────────────────────────────────────┤
│                   Ephemeral Scratch Org Pool                    │
└─────────────────────────────────────────────────────────────────┘
```

## 📁 Project Structure

```
sf-agentbench/
├── README.md
├── LICENSE
├── pyproject.toml              # Python package configuration
├── requirements.txt
├── sf-agentbench.yaml          # Main configuration file
├── docs/
│   └── development/
│       ├── Salesforce AI Benchmark Design.md
│       └── Salesforce AI Benchmark Design.pdf
├── src/sf_agentbench/
│   ├── __init__.py
│   ├── cli.py                  # CLI entry point
│   ├── config.py               # Configuration management
│   ├── models.py               # Data models (Task, Result, etc.)
│   ├── aci/                    # Agent-Computer Interface
│   │   ├── base.py             # Base tool class
│   │   ├── deploy.py           # sf_deploy, sf_retrieve
│   │   ├── apex.py             # sf_run_apex_tests, sf_run_anonymous
│   │   ├── data.py             # sf_query, sf_create_record, sf_import_data
│   │   ├── analysis.py         # sf_scan_code
│   │   └── org.py              # Scratch org management
│   ├── harness/                # Benchmark orchestration
│   │   ├── runner.py           # BenchmarkHarness
│   │   ├── task_loader.py      # Task discovery
│   │   └── org_manager.py      # Scratch Org lifecycle
│   ├── evaluators/             # 5-layer evaluation
│   │   ├── pipeline.py         # Main pipeline
│   │   ├── deployment.py       # Layer 1
│   │   ├── functional.py       # Layer 2
│   │   ├── static_analysis.py  # Layer 3
│   │   ├── metadata_diff.py    # Layer 4
│   │   └── rubric.py           # Layer 5
│   └── tui/                    # Terminal User Interface
│       ├── app.py              # Main TUI application
│       └── screens/            # Dashboard, Tasks, Run, Results, Config
├── tasks/                      # Benchmark tasks
│   ├── tier-1/
│   └── tier-2/
├── results/                    # Run outputs
└── tests/                      # Test suite
```

## 🚀 Getting Started

### Prerequisites

- **Python 3.10+**
- **Salesforce CLI** (`sf`) — [Install Guide](https://developer.salesforce.com/tools/salesforcecli)
- **DevHub-enabled Org** — Required for Scratch Org creation

### Installation

```bash
# Clone the repository
git clone https://github.com/bhanudas/sf-agentbench.git
cd sf-agentbench

# Install in development mode
pip install -e .

# Initialize with sample tasks
sf-agentbench init
```

### Quick Start

#### Launch the Terminal UI (Recommended)

```bash
sf-agentbench-tui
```

Navigate with keyboard shortcuts:
- `D` - Dashboard
- `T` - Browse Tasks
- `R` - Run Benchmark
- `S` - View Results
- `C` - Configuration
- `Q` - Quit

#### Use the CLI

```bash
# List available tasks
sf-agentbench list-tasks

# Show task details
sf-agentbench show-task lead-scoring-validation

# Run a specific task
sf-agentbench run lead-scoring-validation --agent claude-code

# Validate your setup
sf-agentbench validate
```

## ⚙️ Configuration

Edit `sf-agentbench.yaml` to configure:

```yaml
# Agent configuration
agent:
  id: claude-code
  type: claude
  model: claude-sonnet-4-20250514
  api_key_env: ANTHROPIC_API_KEY

# Salesforce settings
devhub_username: admin@mydevhub.org

# Evaluation weights (must sum to 1.0)
evaluation_weights:
  deployment: 0.20
  functional_tests: 0.40
  static_analysis: 0.10
  metadata_diff: 0.15
  rubric: 0.15
```

## 📋 Task Difficulty Tiers

| Tier | Complexity | Example | Skills Tested |
|------|------------|---------|---------------|
| **Tier 1** | Single-domain, declarative | Validation Rule + Flow | Schema, Validation Rules, Flows |
| **Tier 2** | Multi-domain, declarative + code | Screen Flow + Apex Action | Screen Flow, Invocable Apex, Testing |
| **Tier 3** | Complex code, async processing | Apex Specialist Superbadge | Triggers, Queueable, Bulkification |
| **Tier 4** | Full-stack, LWC, integrations | LWC Specialist Superbadge | LWC, Apex Services, Wire, Callouts |

## 📈 Scoring Methodology

The composite score combines all evaluation layers:

```
Final_Score = (
    0.20 × deployment_success +
    0.40 × apex_test_pass_rate +
    0.10 × (1 - pmd_penalty) +
    0.15 × metadata_accuracy +
    0.15 × rubric_score
)
```

Score indicators:
- 🟢 **Excellent**: ≥ 0.80
- 🟡 **Good**: ≥ 0.60
- 🔴 **Needs Work**: < 0.60

## 🗺️ Roadmap

### Phase 1: Foundation ✅
- [x] ACI tool wrappers for core `sf` commands
- [x] Basic harness for task loading and evaluation
- [x] 5-layer evaluation pipeline
- [x] Terminal UI with Textual
- [x] Sample Tier 1 & 2 tasks

### Phase 2: Expansion
- [ ] DevHub setup with Scratch Org pool management
- [ ] PMD/Code Analyzer deep integration
- [ ] 10 Tier 3 tasks
- [ ] Baseline runs with leading AI agents

### Phase 3: Maturity
- [ ] LLM-as-a-Judge with multiple providers
- [ ] 5 Tier 4 tasks
- [ ] Public leaderboard
- [ ] Research paper submission

## 📚 Documentation

- [Technical Design Document](docs/development/Salesforce%20AI%20Benchmark%20Design.md) — Comprehensive framework architecture and methodology

## 🤝 Contributing

Contributions are welcome! Areas for contribution:
- New benchmark tasks (especially Tier 3 & 4)
- ACI tool enhancements
- Evaluation metric refinements
- Documentation improvements

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Inspired by [SWE-bench](https://www.swebench.com/) and [SWE-agent](https://swe-agent.com/)
- Task methodology adapted from [Salesforce Trailhead Superbadges](https://trailhead.salesforce.com/superbadges)
- Built for the AI agent research community

---

<p align="center">
  <strong>SF-AgentBench</strong> — Bridging AI Agents and Enterprise Platform Development
</p>
