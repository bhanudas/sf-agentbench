/**
 * Apex class with edge cases for judge evaluation.
 * Expected rubric score: 0.5 - 0.6 (mixed quality)
 * 
 * This code has some good practices and some issues,
 * testing the judge's ability to provide nuanced scoring.
 */
public with sharing class MixedQualityService {
    
    // Good: Using constants
    private static final Integer MAX_RECORDS = 200;
    
    // Good: Bulkified query, but...
    // Bad: No CRUD check before query
    public static List<Account> getActiveAccounts() {
        return [
            SELECT Id, Name, Industry, AnnualRevenue
            FROM Account
            WHERE IsDeleted = false
            LIMIT :MAX_RECORDS
        ];
    }
    
    // Good: Bulkified processing
    // Bad: No null checks on input
    public static Map<Id, Decimal> calculateAccountScores(List<Account> accounts) {
        Map<Id, Decimal> scores = new Map<Id, Decimal>();
        
        for (Account acc : accounts) {
            Decimal score = 0;
            
            // Good: Using null-safe operations
            if (acc.AnnualRevenue != null) {
                score += acc.AnnualRevenue / 100000;
            }
            
            scores.put(acc.Id, score);
        }
        
        return scores;
    }
    
    // Good: Has error handling
    // Bad: Catches generic Exception
    public static void updateAccountScores(List<Account> accounts) {
        try {
            update accounts;
        } catch (Exception e) {
            // Bad: Generic exception catch
            System.debug('Error: ' + e.getMessage());
            // Bad: Swallowing exception
        }
    }
    
    // Good: Using Test.isRunningTest()
    // Bad: Different behavior in test vs production
    public static void sendNotifications(List<Id> accountIds) {
        if (Test.isRunningTest()) {
            return; // Skip in tests - not ideal
        }
        
        // Actual implementation...
        for (Id accId : accountIds) {
            // Some notification logic
        }
    }
    
    // Good: Separated concerns
    // Bad: No input validation
    @Future(callout=true)
    public static void syncToExternalSystem(String accountId) {
        // No validation of accountId format
        HttpRequest req = new HttpRequest();
        req.setEndpoint('callout:ExternalSystem/accounts/' + accountId);
        req.setMethod('POST');
        
        Http http = new Http();
        HttpResponse res = http.send(req);
        
        // Good: Checking response status
        if (res.getStatusCode() != 200) {
            System.debug('Sync failed: ' + res.getBody());
        }
    }
}
