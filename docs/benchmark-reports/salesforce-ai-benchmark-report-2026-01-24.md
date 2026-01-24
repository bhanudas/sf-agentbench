# Salesforce AI Benchmark Report - January 24, 2026

**SF-AgentBench v0.2.1**

## Executive Summary

This report presents benchmark results for evaluating AI models on Salesforce development tasks, including both Q&A knowledge testing and hands-on coding challenges.

### Key Results

| Category | Best Model | Score |
|----------|-----------|-------|
| Q&A Accuracy | Claude Opus 4 | 94.7% |
| Coding (Tier-2) | Gemini 2.0 Flash | 97.7% |
| Fastest Q&A | Gemini 2.0 Flash | 0.12s/question |
| Most Efficient Coding | Gemini 2.0 Flash | 17,830 tokens |

---

## Q&A Benchmark Results

**Test Bank:** `salesforce_admin_test_bank.json`
**Questions:** 75
**Domains:** 6
**Workers:** 4 (parallel)

### Overall Accuracy

| Model | Correct | Total | Accuracy | Duration | Tokens | Est. Cost |
|-------|---------|-------|----------|----------|--------|-----------|
| **Claude Opus 4** | 71 | 75 | **94.7%** | 28.5s | 9,641 | $0.0008 |
| Claude Sonnet 4 | 70 | 75 | 93.3% | 38.8s | 9,641 | $0.0008 |
| Gemini 2.0 Flash | 68 | 75 | 90.7% | 8.9s | 8,600 | $0.0007 |

### Accuracy by Domain

| Domain | Claude Opus 4 | Claude Sonnet 4 | Gemini 2.0 Flash |
|--------|---------------|-----------------|------------------|
| Reports & Dashboards | 100% (10/10) | 100% (10/10) | 100% (10/10) |
| Sales & Service Cloud | 100% (10/10) | 100% (10/10) | 100% (10/10) |
| Platform Developer I | 96% (24/25) | 96% (24/25) | 88% (22/25) |
| Automation | 90% (9/10) | 90% (9/10) | 90% (9/10) |
| Data Management | 90% (9/10) | 80% (8/10) | 90% (9/10) |
| Security & Access | 90% (9/10) | 90% (9/10) | 80% (8/10) |

### Answer Distribution Analysis

After rebalancing the test bank, the answer distribution is now:
- A: 25.3% (19 questions)
- B: 25.3% (19 questions)
- C: 24.0% (18 questions)
- D: 25.3% (19 questions)

**Previous distribution (v0.2.0):** A=8%, B=52%, C=28%, D=12%

This eliminates the positional bias that could have inflated scores for models with B-preference.

---

## Coding Benchmark Results

**Evaluation Layers:**
1. Deployment Validation (20%)
2. Functional Testing (40%)
3. Static Analysis (10%)
4. Metadata Diff (15%)
5. LLM-as-Judge Rubric (15%)

### Task: Opportunity Discount Calculator (Tier-2)

| Model | Final Score | Deploy | Tests | Static | Meta | Rubric | Iterations | Tokens | Duration |
|-------|-------------|--------|-------|--------|------|--------|------------|--------|----------|
| **Gemini 2.0 Flash** | **97.7%** | 100% | 100% | 100% | 100% | 84.5% | 7 | 17,830 | 65.7s |
| Claude Sonnet 4 | 94.6% | 100% | 100% | 100% | 100% | 64.0%* | 19 | 89,087 | 114.7s |

### Task: Account Territory Trigger (Tier-2)

| Model | Final Score | Deploy | Tests | Static | Meta | Rubric | Iterations | Tokens | Duration |
|-------|-------------|--------|-------|--------|------|--------|------------|--------|----------|
| Claude Sonnet 4 | 94.6% | 100% | 100% | 100% | 100% | 64.0%* | 22 | 86,040 | 142.2s |
| Gemini 2.0 Flash | 94.6% | 100% | 100% | 100% | 100% | 64.0%* | 10 | 19,403 | 64.0s |

### Task: Lead Scoring Validation (Tier-1)

| Model | Final Score | Deploy | Tests | Static | Meta | Rubric | Iterations | Tokens | Duration |
|-------|-------------|--------|-------|--------|------|--------|------------|--------|----------|
| Claude Sonnet 4 | 94.0% | 100% | 100% | 100% | 100% | 60.0%* | 36 | 220,635 | 230.9s |
| Gemini 2.0 Flash | 0.0% | 0% | - | - | - | - | 17 | 70,011 | 204.0s |

*Rubric scores marked with asterisk used heuristic fallback due to config issue (now fixed)

### Coding Benchmark Observations

1. **Test Pass Rate:** Both Claude and Gemini achieve 100% test pass rate when deployment succeeds
2. **Efficiency:** Gemini uses 4-5x fewer tokens and completes 2-3x faster than Claude
3. **Reliability:** Claude has higher deployment success rate (100% vs ~75% for Gemini)
4. **LLM-as-Judge:** After config fix, proper rubric evaluation yields 84.5% vs 60-64% heuristic

---

## Infrastructure & Configuration

### Test Environment
- **Framework Version:** SF-AgentBench v0.2.1
- **Platform:** macOS Darwin 25.2.0
- **Python:** 3.11
- **Salesforce CLI:** Latest
- **Scratch Org Edition:** Developer

### LLM-as-Judge Configuration
```yaml
rubric:
  enabled: true
  model: claude-sonnet-4-20250514
  provider: auto  # Anthropic, Google, OpenAI
  timeout_seconds: 120
  fallback_to_heuristic: true
```

### Evaluation Weights
```yaml
evaluation_weights:
  deployment: 0.20
  functional_tests: 0.40
  static_analysis: 0.10
  metadata_diff: 0.15
  rubric: 0.15
```

---

## Changes Since Last Report (v0.2.0)

### New in v0.2.1

1. **CLI Agent Improvements**
   - Phase-specific timeouts (build: 600s, deploy: 300s, test: 300s)
   - Gemini and Aider-specific prompt builders
   - Progressive timeout warnings (50%, 75%, 90%)

2. **LLM-as-Judge Multi-Provider Support**
   - Auto-detection for Anthropic, Google, OpenAI
   - Proper API integration (was falling back to heuristics)
   - Configurable timeout and fallback options

3. **Expanded Test Bank**
   - 75 questions (was 50)
   - 6 domains (added Platform Developer I)
   - Balanced answer distribution (was 52% B)

4. **New Tier-2 Coding Tasks**
   - `account-territory-trigger`: Trigger + Handler pattern
   - `opportunity-discount-calculator`: @InvocableMethod with discounting

---

## Recommendations

### For Q&A Testing
- **Best Accuracy:** Claude Opus 4 (94.7%)
- **Best Speed/Cost:** Gemini 2.0 Flash (90.7% at 3x speed, lower cost)
- **Balanced:** Claude Sonnet 4 (93.3%, good accuracy with reasonable speed)

### For Coding Tasks
- **Most Reliable:** Claude Sonnet 4 (100% deployment success)
- **Most Efficient:** Gemini 2.0 Flash (5x fewer tokens when successful)
- **Recommendation:** Use Claude for critical tasks, Gemini for bulk testing

### Next Steps
1. Add more Tier-3 tasks for advanced differentiation
2. Investigate Gemini deployment failures on Tier-1 tasks
3. Enable PMD static analysis for code quality scoring
4. Add more Platform Developer I questions to test bank

---

## Appendix: Detailed Test Results

### Q&A Incorrect Answers

**Claude Opus 4 (4 incorrect):**
- Q6: Expected B, Got C
- Q15: Expected C, Got B
- Q30: Expected B, Got C
- Q65: Expected B, Got C

**Claude Sonnet 4 (5 incorrect):**
- Q6: Expected B, Got C
- Q14: Expected B, Got C
- Q18: Expected B, Got C
- Q30: Expected B, Got C
- Q62: Expected D, Got B

**Gemini 2.0 Flash (7 incorrect):**
- Q1: Expected D, Got B
- Q6: Expected B, Got D
- Q19: Expected C, Got B
- Q22: Expected C, Got B
- Q62: Expected D, Got B
- Q72: Expected C, Got A
- Q75: Expected B, Got A

### Common Failure Patterns
- Q6 and Q30: Failed by all models (may need review)
- Q62: Failed by Claude Sonnet and Gemini (Platform Developer I)
- Models show slight B-preference despite rebalancing

---

*Report generated: January 24, 2026*
*SF-AgentBench v0.2.1*
