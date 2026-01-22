/**
 * Poor quality Apex class with multiple anti-patterns.
 * Expected rubric score: < 0.4
 * 
 * Anti-patterns demonstrated:
 * - SOQL in loop
 * - DML in loop
 * - Hardcoded IDs
 * - No error handling
 * - No CRUD/FLS checks
 * - Poor naming
 */
public class doLeadStuff {
    
    // Hardcoded ID - bad practice
    public static final Id ADMIN_QUEUE_ID = '00G000000000001';
    
    public static void processLeads(List<Lead> leads) {
        // SOQL in loop - will hit governor limits
        for (Lead l : leads) {
            // Query in loop!
            List<Lead> existing = [
                SELECT Id, Email FROM Lead WHERE Email = :l.Email
            ];
            
            if (existing.size() > 0) {
                // DML in loop!
                update l;
            }
            
            // Another query in loop!
            User owner = [SELECT Id, Name FROM User WHERE Id = :l.OwnerId LIMIT 1];
            
            // DML in loop again!
            insert new Task(
                WhatId = l.Id,
                Subject = 'Follow up',
                OwnerId = owner.Id
            );
        }
    }
    
    // No access checks, direct string concatenation (SOQL injection risk)
    public static List<Lead> searchLeads(String searchTerm) {
        // SOQL injection vulnerability!
        String query = 'SELECT Id, Name FROM Lead WHERE Name LIKE \'%' + searchTerm + '%\'';
        return Database.query(query);
    }
    
    // Magic numbers, no constants
    public static void scoreLeads(List<Lead> leads) {
        for (Lead l : leads) {
            Integer s = 0;
            if (l.Industry == 'Technology') {
                s = s + 10;
            }
            if (l.Annual_Revenue__c > 1000000) {
                s = s + 20;
            }
            l.Lead_Score__c = s;
            // DML in loop!
            update l;
        }
    }
    
    // No documentation, unclear purpose
    public static void x(List<Id> ids) {
        for (Id i : ids) {
            Lead l = [SELECT Id FROM Lead WHERE Id = :i];
            l.Status = 'Working';
            update l;
        }
    }
    
    // Hardcoded credentials - critical security issue
    public static void callExternalService() {
        String apiKey = 'sk-1234567890abcdef';
        String password = 'admin123';
        
        HttpRequest req = new HttpRequest();
        req.setEndpoint('https://api.example.com/data');
        req.setHeader('Authorization', 'Bearer ' + apiKey);
        // ...
    }
}
