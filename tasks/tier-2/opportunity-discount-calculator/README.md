# Opportunity Discount Calculator

## Business Requirements

Universal Containers needs to calculate automatic discounts for opportunities based on deal size and customer loyalty.

### Requirements

1. **Custom Fields**: The following custom fields exist on Opportunity:
   - `Discount_Percentage__c` (Number, 2 decimal places)
   - `Final_Amount__c` (Currency)
   - `Customer_Tier__c` (Picklist: Bronze, Silver, Gold, Platinum)

2. **Apex Class**: Create `OpportunityDiscountCalculator` with:
   - `@InvocableMethod` named `calculateDiscounts`
   - Input: List of Opportunity IDs
   - Logic for calculating `Discount_Percentage__c`:
     - Base discount by Amount:
       - Amount >= 1,000,000 → 15%
       - Amount >= 500,000 → 10%
       - Amount >= 100,000 → 5%
       - Amount < 100,000 → 0%
     - Additional discount by Customer Tier:
       - Platinum → +5%
       - Gold → +3%
       - Silver → +1%
       - Bronze → +0%
   - Calculate `Final_Amount__c` = Amount * (1 - Discount_Percentage__c/100)
   - Update the Opportunity records
   - Return: List of updated Opportunity IDs

3. **Test Class**: Create `OpportunityDiscountCalculatorTest` with:
   - Test each amount tier
   - Test each customer tier bonus
   - Test combination scenarios
   - Test bulk processing (200 records)
   - Test edge cases (null Amount, null Tier)

### Acceptance Criteria

- Discounts calculated correctly for all tiers
- Final_Amount__c computed accurately
- Class is bulkified (single SOQL query, single DML)
- Test coverage >= 90%
- Solution handles 200+ opportunities efficiently
