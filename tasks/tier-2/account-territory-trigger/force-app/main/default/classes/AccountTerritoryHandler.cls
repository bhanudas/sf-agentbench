/**
 * Handler class for Account Territory assignment logic
 * 
 * Assigns territories to accounts based on their billing state:
 * - West: CA, OR, WA
 * - East: NY, NJ, CT, MA  
 * - South: TX, FL, GA
 * - Central: IL, MI, OH
 * - Other: All other states
 * - Unassigned: Null billing state
 */
public class AccountTerritoryHandler {
    
    // Territory mapping - using sets for O(1) lookup performance
    private static final Set<String> WEST_STATES = new Set<String>{'CA', 'OR', 'WA'};
    private static final Set<String> EAST_STATES = new Set<String>{'NY', 'NJ', 'CT', 'MA'};
    private static final Set<String> SOUTH_STATES = new Set<String>{'TX', 'FL', 'GA'};
    private static final Set<String> CENTRAL_STATES = new Set<String>{'IL', 'MI', 'OH'};
    
    /**
     * Assigns territories to accounts based on billing state
     * Only updates territory if billing state has changed (for updates)
     * 
     * @param accounts List of accounts to process
     */
    public static void assignTerritories(List<Account> accounts) {
        // Get old values for update operations
        Map<Id, Account> oldAccountMap = Trigger.isUpdate ? (Map<Id, Account>)Trigger.oldMap : null;
        
        for (Account acc : accounts) {
            // For updates, only process if BillingState changed or Territory is null
            if (Trigger.isUpdate && oldAccountMap != null) {
                Account oldAccount = oldAccountMap.get(acc.Id);
                if (acc.BillingState == oldAccount.BillingState && acc.Territory__c != null) {
                    continue; // Skip if BillingState hasn't changed and Territory is already set
                }
            }
            
            // Assign territory based on billing state
            acc.Territory__c = getTerritoryForState(acc.BillingState);
        }
    }
    
    /**
     * Returns the appropriate territory for a given state
     * 
     * @param state The billing state
     * @return The territory assignment
     */
    private static String getTerritoryForState(String state) {
        if (String.isBlank(state)) {
            return 'Unassigned';
        }
        
        String upperState = state.toUpperCase();
        
        if (WEST_STATES.contains(upperState)) {
            return 'West';
        } else if (EAST_STATES.contains(upperState)) {
            return 'East';
        } else if (SOUTH_STATES.contains(upperState)) {
            return 'South';
        } else if (CENTRAL_STATES.contains(upperState)) {
            return 'Central';
        } else {
            return 'Other';
        }
    }
}