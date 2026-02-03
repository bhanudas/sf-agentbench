# Lead Scoring Validation Rule

## Business Requirements

Universal Containers needs to implement lead scoring to prioritize sales efforts.

### Requirements

1. **Validation Rule**: Create a validation rule on the Lead object that:
   - Prevents saving a Lead if `Annual_Revenue__c` is less than 0
   - Error message: "Annual Revenue cannot be negative"

2. **Lead Scoring Flow**: Create a Record-Triggered Flow that:
   - Triggers when a Lead is created or updated
   - Calculates `Lead_Score__c` based on:
     - +10 points if `Industry` is "Technology" or "Finance"
     - +20 points if `Annual_Revenue__c` > 1,000,000
     - +15 points if `NumberOfEmployees` > 100
   - Updates the Lead record with the calculated score

### Acceptance Criteria

- Validation rule blocks negative Annual Revenue values
- Lead Score is automatically calculated on create/update
- Solution works for bulk operations (up to 200 records)
