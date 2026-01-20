# Case Escalation Screen Flow

## Business Requirements

Support managers need a streamlined way to escalate high-priority cases.

### Requirements

1. **Invocable Apex Class**: Create `CaseEscalationService` with:
   - `@InvocableMethod` named `escalateCases`
   - Input: List of Case IDs
   - Logic:
     - Set `Priority` to "High"
     - Set `Status` to "Escalated"
     - Add a CaseComment: "Case escalated by {running user name}"
   - Return: List of escalated Case IDs

2. **Screen Flow**: Create a Screen Flow that:
   - Shows a data table of open Cases (Status != 'Closed')
   - Allows selecting multiple Cases
   - Has an "Escalate Selected" button
   - Calls the `CaseEscalationService`
   - Shows confirmation message with count of escalated cases

### Acceptance Criteria

- Apex class is bulkified (no queries/DML in loops)
- Flow correctly passes selected Case IDs to Apex
- Test class has 90%+ code coverage
- Solution handles up to 200 cases
