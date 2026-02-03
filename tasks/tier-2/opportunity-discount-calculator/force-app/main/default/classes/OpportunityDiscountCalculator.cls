/**
 * OpportunityDiscountCalculator
 * 
 * Calculates automatic discounts for opportunities based on:
 * - Deal size (Amount)
 * - Customer loyalty tier
 * 
 * Discount Logic:
 * Base discount by Amount:
 * - Amount >= 1,000,000 → 15%
 * - Amount >= 500,000 → 10%
 * - Amount >= 100,000 → 5%
 * - Amount < 100,000 → 0%
 * 
 * Additional discount by Customer Tier:
 * - Platinum → +5%
 * - Gold → +3%
 * - Silver → +1%
 * - Bronze → +0%
 */
public class OpportunityDiscountCalculator {

    /**
     * Invocable method to calculate discounts for opportunities
     * @param opportunityIds List of Opportunity IDs to process
     * @return List of updated Opportunity IDs
     */
    @InvocableMethod(label='Calculate Opportunity Discounts' description='Calculates discounts based on amount and customer tier')
    public static List<Id> calculateDiscounts(List<Id> opportunityIds) {
        
        // Validate input
        if (opportunityIds == null || opportunityIds.isEmpty()) {
            return new List<Id>();
        }
        
        // Query opportunities with required fields
        List<Opportunity> opportunities = [
            SELECT Id, Amount, Customer_Tier__c, Discount_Percentage__c, Final_Amount__c
            FROM Opportunity 
            WHERE Id IN :opportunityIds
        ];
        
        // Process each opportunity
        List<Opportunity> oppsToUpdate = new List<Opportunity>();
        for (Opportunity opp : opportunities) {
            
            // Calculate base discount based on amount
            Decimal baseDiscount = calculateBaseDiscount(opp.Amount);
            
            // Calculate tier bonus
            Decimal tierBonus = calculateTierBonus(opp.Customer_Tier__c);
            
            // Total discount percentage
            Decimal totalDiscount = baseDiscount + tierBonus;
            
            // Set discount percentage
            opp.Discount_Percentage__c = totalDiscount;
            
            // Calculate final amount
            if (opp.Amount != null) {
                opp.Final_Amount__c = opp.Amount * (1 - totalDiscount / 100);
            } else {
                opp.Final_Amount__c = null;
            }
            
            oppsToUpdate.add(opp);
        }
        
        // Update opportunities (single DML operation for bulkification)
        if (!oppsToUpdate.isEmpty()) {
            update oppsToUpdate;
        }
        
        // Return list of updated IDs
        List<Id> updatedIds = new List<Id>();
        for (Opportunity opp : oppsToUpdate) {
            updatedIds.add(opp.Id);
        }
        
        return updatedIds;
    }
    
    /**
     * Calculate base discount percentage based on opportunity amount
     * @param amount Opportunity amount
     * @return Base discount percentage
     */
    private static Decimal calculateBaseDiscount(Decimal amount) {
        if (amount == null) {
            return 0;
        }
        
        if (amount >= 1000000) {
            return 15.00;
        } else if (amount >= 500000) {
            return 10.00;
        } else if (amount >= 100000) {
            return 5.00;
        } else {
            return 0.00;
        }
    }
    
    /**
     * Calculate additional discount percentage based on customer tier
     * @param customerTier Customer tier value
     * @return Additional discount percentage
     */
    private static Decimal calculateTierBonus(String customerTier) {
        if (customerTier == null) {
            return 0.00;
        }
        
        switch on customerTier {
            when 'Platinum' {
                return 5.00;
            }
            when 'Gold' {
                return 3.00;
            }
            when 'Silver' {
                return 1.00;
            }
            when 'Bronze' {
                return 0.00;
            }
            when else {
                return 0.00;
            }
        }
    }
}