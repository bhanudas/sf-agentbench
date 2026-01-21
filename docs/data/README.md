# SF-AgentBench Test Banks

This directory contains Q&A test banks for evaluating LLM knowledge of Salesforce concepts.

## Quick Start

```bash
# List available test banks
sf-agentbench qa-list

# Run a sample test (5 questions)
sf-agentbench qa-run salesforce_admin_test_bank.json -n 5 -m gemini-2.0-flash

# Run full test bank
sf-agentbench qa-run salesforce_admin_test_bank.json -m gemini-2.0-flash

# Filter by domain
sf-agentbench qa-run salesforce_admin_test_bank.json -d "Security & Access" -m gemini-2.0-flash

# Save results to JSON
sf-agentbench qa-run salesforce_admin_test_bank.json -o results/my-test.json
```

## Available Test Banks

| File | Description | Questions | Domains |
|------|-------------|-----------|---------|
| `salesforce_admin_test_bank.json` | Salesforce Admin Certification | 50 | Security, Data, Automation, Reports, Sales/Service |

## Creating Your Own Test Bank

Test banks follow a JSON schema. Here's how to create one:

### Basic Structure

```json
{
  "metadata": {
    "version": "1.0",
    "id": "my-test-bank",
    "name": "My Custom Test Bank",
    "description": "Description of what this tests",
    "created": "2026-01-21",
    "authors": ["Your Name"],
    "domains": ["Domain1", "Domain2"],
    "difficulty": "intermediate",
    "tags": ["salesforce", "apex", "lwc"]
  },
  "questions": [
    {
      "id": 1,
      "type": "multiple_choice",
      "domain": "Domain1",
      "difficulty": "medium",
      "question": "What is the correct answer?",
      "choices": {
        "A": "First option",
        "B": "Second option",
        "C": "Third option",
        "D": "Fourth option"
      },
      "correct_answer": "B",
      "explanation": "Explanation of why B is correct"
    }
  ]
}
```

### Question Types

| Type | Description | Required Fields |
|------|-------------|-----------------|
| `multiple_choice` | A/B/C/D options | `choices`, `correct_answer` (letter) |
| `true_false` | True or False | `correct_answer` ("True" or "False") |
| `short_answer` | Free text | `correct_answer` (text or array of accepted answers) |
| `code` | Code-related | `context`, `correct_answer` |
| `scenario` | Complex scenario | `context`, `choices`, `correct_answer` |

### Field Reference

**Metadata Fields:**

| Field | Required | Description |
|-------|----------|-------------|
| `version` | Yes | Schema version (e.g., "1.0") |
| `id` | Yes | Unique identifier |
| `name` | Yes | Human-readable name |
| `description` | Yes | What this test bank covers |
| `created` | No | Creation date (YYYY-MM-DD) |
| `authors` | No | List of contributors |
| `domains` | No | Knowledge domains covered |
| `difficulty` | No | Overall difficulty (beginner/intermediate/advanced/expert/mixed) |
| `tags` | No | Searchable tags |

**Question Fields:**

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Unique question ID (number or string) |
| `type` | Yes | Question type (see above) |
| `question` | Yes | The question text |
| `correct_answer` | Yes | The correct answer |
| `domain` | No | Knowledge domain |
| `difficulty` | No | Question difficulty (easy/medium/hard/expert) |
| `context` | No | Additional context or scenario |
| `choices` | No* | Answer choices for multiple choice |
| `explanation` | No | Why the answer is correct |
| `tags` | No | Question-specific tags |
| `points` | No | Point value (default: 1) |

*Required for multiple_choice type

### Example: Adding a New Question

```json
{
  "id": 51,
  "type": "multiple_choice",
  "domain": "Apex",
  "difficulty": "hard",
  "question": "What is the governor limit for SOQL queries in a single transaction?",
  "choices": {
    "A": "50",
    "B": "100",
    "C": "150",
    "D": "200"
  },
  "correct_answer": "B",
  "explanation": "The synchronous Apex governor limit is 100 SOQL queries per transaction.",
  "tags": ["governor-limits", "soql"]
}
```

## Schema Validation

The full JSON Schema is available in `test_bank_schema.json`. Use it to validate your test banks:

```bash
# Using jsonschema (Python)
pip install jsonschema
python -c "
import json
from jsonschema import validate

with open('docs/data/test_bank_schema.json') as f:
    schema = json.load(f)
with open('docs/data/my_test_bank.json') as f:
    data = json.load(f)
validate(data, schema)
print('Valid!')
"
```

## Contributing Test Banks

1. Create your test bank following the schema above
2. Place it in `docs/data/`
3. Run `sf-agentbench qa-list` to verify it's detected
4. Test with a small sample: `sf-agentbench qa-run your_bank.json -n 5`
5. Submit a PR!

### Guidelines

- Use clear, unambiguous questions
- Provide explanations for educational value
- Tag questions appropriately for filtering
- Test with multiple LLMs to verify question quality
- Avoid questions that are too ambiguous or have multiple correct answers
