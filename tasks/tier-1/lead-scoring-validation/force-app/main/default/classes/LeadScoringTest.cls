@IsTest
private class LeadScoringTest {
    
    @IsTest
    static void testValidationRuleBlocksNegativeRevenue() {
        Lead testLead = new Lead(
            LastName = 'Test',
            Company = 'Test Company',
            Annual_Revenue__c = -1000
        );
        
        Test.startTest();
        try {
            insert testLead;
            System.assert(false, 'Should have thrown validation error');
        } catch (DmlException e) {
            System.assert(e.getMessage().contains('negative'), 
                'Error should mention negative: ' + e.getMessage());
        }
        Test.stopTest();
    }
    
    @IsTest
    static void testLeadScoreCalculation() {
        Lead testLead = new Lead(
            LastName = 'Test',
            Company = 'Tech Corp',
            Industry = 'Technology',
            Annual_Revenue__c = 2000000,
            NumberOfEmployees = 500
        );
        
        Test.startTest();
        insert testLead;
        Test.stopTest();
        
        testLead = [SELECT Lead_Score__c FROM Lead WHERE Id = :testLead.Id];
        
        // Should have: 10 (Technology) + 20 (>1M revenue) + 15 (>100 employees) = 45
        System.assertEquals(45, testLead.Lead_Score__c, 
            'Lead score should be 45');
    }
    
    @IsTest
    static void testBulkLeadScoring() {
        List<Lead> leads = new List<Lead>();
        for (Integer i = 0; i < 200; i++) {
            leads.add(new Lead(
                LastName = 'Test ' + i,
                Company = 'Company ' + i,
                Industry = 'Technology',
                Annual_Revenue__c = 500000
            ));
        }
        
        Test.startTest();
        insert leads;
        Test.stopTest();
        
        List<Lead> insertedLeads = [
            SELECT Lead_Score__c FROM Lead WHERE Id IN :leads
        ];
        
        for (Lead l : insertedLeads) {
            System.assertNotEquals(null, l.Lead_Score__c, 
                'Lead score should be calculated');
        }
    }
}
