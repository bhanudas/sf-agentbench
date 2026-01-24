# Account Territory Assignment Trigger

## Business Requirements

Universal Containers needs to automatically assign accounts to sales territories based on their billing address.

### Requirements

1. **Custom Field**: A custom field `Territory__c` (Text, 50 chars) exists on Account.

2. **Apex Trigger**: Create a trigger `AccountTerritoryTrigger` on Account that:
   - Fires on `before insert` and `before update`
   - Calls a handler class for logic (separation of concerns)

3. **Handler Class**: Create `AccountTerritoryHandler` with:
   - Method `assignTerritories(List<Account> accounts)`
   - Territory assignment logic:
     - BillingState = 'CA', 'OR', 'WA' → Territory = 'West'
     - BillingState = 'NY', 'NJ', 'CT', 'MA' → Territory = 'East'
     - BillingState = 'TX', 'FL', 'GA' → Territory = 'South'
     - BillingState = 'IL', 'MI', 'OH' → Territory = 'Central'
     - All other states → Territory = 'Other'
   - Only update Territory if BillingState changed (on update)
   - Handle null BillingState gracefully (set Territory = 'Unassigned')

4. **Test Class**: Create `AccountTerritoryTriggerTest` with:
   - Test insert with each territory region
   - Test update that changes territory
   - Test bulk insert (200 records)
   - Test null BillingState handling

### Acceptance Criteria

- Trigger delegates to handler class (no business logic in trigger)
- Handler is bulkified (no SOQL/DML in loops)
- Only updates Territory when BillingState changes
- Test coverage >= 90%
- Solution handles 200+ records efficiently
