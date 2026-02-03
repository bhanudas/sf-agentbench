@IsTest
private class CaseEscalationTest {
    
    @TestSetup
    static void setupTestData() {
        List<Case> cases = new List<Case>();
        for (Integer i = 0; i < 10; i++) {
            cases.add(new Case(
                Subject = 'Test Case ' + i,
                Status = 'New',
                Priority = 'Medium',
                Origin = 'Email'
            ));
        }
        insert cases;
    }
    
    @IsTest
    static void testEscalateCases() {
        List<Case> cases = [SELECT Id FROM Case LIMIT 5];
        List<Id> caseIds = new List<Id>();
        for (Case c : cases) {
            caseIds.add(c.Id);
        }
        
        Test.startTest();
        List<Id> result = CaseEscalationService.escalateCases(caseIds);
        Test.stopTest();
        
        System.assertEquals(5, result.size(), 'Should return 5 escalated case IDs');
        
        List<Case> escalatedCases = [
            SELECT Priority, Status FROM Case WHERE Id IN :result
        ];
        
        for (Case c : escalatedCases) {
            System.assertEquals('High', c.Priority, 'Priority should be High');
            System.assertEquals('Escalated', c.Status, 'Status should be Escalated');
        }
        
        List<CaseComment> comments = [
            SELECT CommentBody FROM CaseComment WHERE ParentId IN :result
        ];
        System.assertEquals(5, comments.size(), 'Should have 5 case comments');
    }
    
    @IsTest
    static void testBulkEscalation() {
        // Create 200 cases for bulk test
        List<Case> bulkCases = new List<Case>();
        for (Integer i = 0; i < 200; i++) {
            bulkCases.add(new Case(
                Subject = 'Bulk Test ' + i,
                Status = 'New',
                Priority = 'Low',
                Origin = 'Web'
            ));
        }
        insert bulkCases;
        
        List<Id> caseIds = new List<Id>();
        for (Case c : bulkCases) {
            caseIds.add(c.Id);
        }
        
        Test.startTest();
        List<Id> result = CaseEscalationService.escalateCases(caseIds);
        Test.stopTest();
        
        System.assertEquals(200, result.size(), 'Should handle 200 cases');
    }
}
