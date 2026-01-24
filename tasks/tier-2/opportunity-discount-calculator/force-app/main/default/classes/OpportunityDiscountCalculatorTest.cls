/**
 * Test class for OpportunityDiscountCalculator
 *
 * Tests:
 * - Base discount by amount tier
 * - Additional discount by customer tier
 * - Final amount calculation
 * - Bulk processing (200 records)
 * - Edge cases (null values)
 */
@IsTest
private class OpportunityDiscountCalculatorTest {

    @TestSetup
    static void setupTestData() {
        // Create test Account
        Account acc = new Account(Name = 'Test Account');
        insert acc;
    }

    @IsTest
    static void testHighValueDiscount() {
        // Amount >= 1,000,000 should get 15% base discount
        Account acc = [SELECT Id FROM Account LIMIT 1];
        Opportunity opp = new Opportunity(
            Name = 'High Value Opp',
            AccountId = acc.Id,
            Amount = 1500000,
            Customer_Tier__c = 'Bronze',
            StageName = 'Prospecting',
            CloseDate = Date.today().addDays(30)
        );
        insert opp;

        Test.startTest();
        OpportunityDiscountCalculator.calculateDiscounts(new List<Id>{opp.Id});
        Test.stopTest();

        Opportunity updatedOpp = [SELECT Discount_Percentage__c, Final_Amount__c FROM Opportunity WHERE Id = :opp.Id];
        System.assertEquals(15.00, updatedOpp.Discount_Percentage__c, 'High value should get 15% discount');
        System.assertEquals(1275000, updatedOpp.Final_Amount__c, 'Final amount should be 85% of original');
    }

    @IsTest
    static void testMediumHighValueDiscount() {
        // Amount >= 500,000 should get 10% base discount
        Account acc = [SELECT Id FROM Account LIMIT 1];
        Opportunity opp = new Opportunity(
            Name = 'Medium High Value Opp',
            AccountId = acc.Id,
            Amount = 750000,
            Customer_Tier__c = 'Bronze',
            StageName = 'Prospecting',
            CloseDate = Date.today().addDays(30)
        );
        insert opp;

        Test.startTest();
        OpportunityDiscountCalculator.calculateDiscounts(new List<Id>{opp.Id});
        Test.stopTest();

        Opportunity updatedOpp = [SELECT Discount_Percentage__c, Final_Amount__c FROM Opportunity WHERE Id = :opp.Id];
        System.assertEquals(10.00, updatedOpp.Discount_Percentage__c, 'Medium-high value should get 10% discount');
        System.assertEquals(675000, updatedOpp.Final_Amount__c, 'Final amount should be 90% of original');
    }

    @IsTest
    static void testMediumValueDiscount() {
        // Amount >= 100,000 should get 5% base discount
        Account acc = [SELECT Id FROM Account LIMIT 1];
        Opportunity opp = new Opportunity(
            Name = 'Medium Value Opp',
            AccountId = acc.Id,
            Amount = 200000,
            Customer_Tier__c = 'Bronze',
            StageName = 'Prospecting',
            CloseDate = Date.today().addDays(30)
        );
        insert opp;

        Test.startTest();
        OpportunityDiscountCalculator.calculateDiscounts(new List<Id>{opp.Id});
        Test.stopTest();

        Opportunity updatedOpp = [SELECT Discount_Percentage__c, Final_Amount__c FROM Opportunity WHERE Id = :opp.Id];
        System.assertEquals(5.00, updatedOpp.Discount_Percentage__c, 'Medium value should get 5% discount');
        System.assertEquals(190000, updatedOpp.Final_Amount__c, 'Final amount should be 95% of original');
    }

    @IsTest
    static void testLowValueNoDiscount() {
        // Amount < 100,000 should get 0% base discount
        Account acc = [SELECT Id FROM Account LIMIT 1];
        Opportunity opp = new Opportunity(
            Name = 'Low Value Opp',
            AccountId = acc.Id,
            Amount = 50000,
            Customer_Tier__c = 'Bronze',
            StageName = 'Prospecting',
            CloseDate = Date.today().addDays(30)
        );
        insert opp;

        Test.startTest();
        OpportunityDiscountCalculator.calculateDiscounts(new List<Id>{opp.Id});
        Test.stopTest();

        Opportunity updatedOpp = [SELECT Discount_Percentage__c, Final_Amount__c FROM Opportunity WHERE Id = :opp.Id];
        System.assertEquals(0.00, updatedOpp.Discount_Percentage__c, 'Low value should get 0% discount');
        System.assertEquals(50000, updatedOpp.Final_Amount__c, 'Final amount should equal original');
    }

    @IsTest
    static void testPlatinumTierBonus() {
        // Platinum tier should add 5% to base discount
        Account acc = [SELECT Id FROM Account LIMIT 1];
        Opportunity opp = new Opportunity(
            Name = 'Platinum Opp',
            AccountId = acc.Id,
            Amount = 1000000,
            Customer_Tier__c = 'Platinum',
            StageName = 'Prospecting',
            CloseDate = Date.today().addDays(30)
        );
        insert opp;

        Test.startTest();
        OpportunityDiscountCalculator.calculateDiscounts(new List<Id>{opp.Id});
        Test.stopTest();

        Opportunity updatedOpp = [SELECT Discount_Percentage__c, Final_Amount__c FROM Opportunity WHERE Id = :opp.Id];
        System.assertEquals(20.00, updatedOpp.Discount_Percentage__c, 'Platinum should get 15% + 5% = 20% discount');
        System.assertEquals(800000, updatedOpp.Final_Amount__c, 'Final amount should be 80% of original');
    }

    @IsTest
    static void testGoldTierBonus() {
        // Gold tier should add 3% to base discount
        Account acc = [SELECT Id FROM Account LIMIT 1];
        Opportunity opp = new Opportunity(
            Name = 'Gold Opp',
            AccountId = acc.Id,
            Amount = 500000,
            Customer_Tier__c = 'Gold',
            StageName = 'Prospecting',
            CloseDate = Date.today().addDays(30)
        );
        insert opp;

        Test.startTest();
        OpportunityDiscountCalculator.calculateDiscounts(new List<Id>{opp.Id});
        Test.stopTest();

        Opportunity updatedOpp = [SELECT Discount_Percentage__c, Final_Amount__c FROM Opportunity WHERE Id = :opp.Id];
        System.assertEquals(13.00, updatedOpp.Discount_Percentage__c, 'Gold should get 10% + 3% = 13% discount');
        System.assertEquals(435000, updatedOpp.Final_Amount__c, 'Final amount should be 87% of original');
    }

    @IsTest
    static void testSilverTierBonus() {
        // Silver tier should add 1% to base discount
        Account acc = [SELECT Id FROM Account LIMIT 1];
        Opportunity opp = new Opportunity(
            Name = 'Silver Opp',
            AccountId = acc.Id,
            Amount = 100000,
            Customer_Tier__c = 'Silver',
            StageName = 'Prospecting',
            CloseDate = Date.today().addDays(30)
        );
        insert opp;

        Test.startTest();
        OpportunityDiscountCalculator.calculateDiscounts(new List<Id>{opp.Id});
        Test.stopTest();

        Opportunity updatedOpp = [SELECT Discount_Percentage__c, Final_Amount__c FROM Opportunity WHERE Id = :opp.Id];
        System.assertEquals(6.00, updatedOpp.Discount_Percentage__c, 'Silver should get 5% + 1% = 6% discount');
        System.assertEquals(94000, updatedOpp.Final_Amount__c, 'Final amount should be 94% of original');
    }

    @IsTest
    static void testNullAmount() {
        // Null amount should be handled gracefully
        Account acc = [SELECT Id FROM Account LIMIT 1];
        Opportunity opp = new Opportunity(
            Name = 'Null Amount Opp',
            AccountId = acc.Id,
            Amount = null,
            Customer_Tier__c = 'Bronze',
            StageName = 'Prospecting',
            CloseDate = Date.today().addDays(30)
        );
        insert opp;

        Test.startTest();
        OpportunityDiscountCalculator.calculateDiscounts(new List<Id>{opp.Id});
        Test.stopTest();

        Opportunity updatedOpp = [SELECT Discount_Percentage__c, Final_Amount__c FROM Opportunity WHERE Id = :opp.Id];
        System.assertEquals(0.00, updatedOpp.Discount_Percentage__c, 'Null amount should get 0% discount');
        System.assertEquals(null, updatedOpp.Final_Amount__c, 'Final amount should be null when amount is null');
    }

    @IsTest
    static void testNullTier() {
        // Null tier should be handled as Bronze (0% bonus)
        Account acc = [SELECT Id FROM Account LIMIT 1];
        Opportunity opp = new Opportunity(
            Name = 'Null Tier Opp',
            AccountId = acc.Id,
            Amount = 200000,
            Customer_Tier__c = null,
            StageName = 'Prospecting',
            CloseDate = Date.today().addDays(30)
        );
        insert opp;

        Test.startTest();
        OpportunityDiscountCalculator.calculateDiscounts(new List<Id>{opp.Id});
        Test.stopTest();

        Opportunity updatedOpp = [SELECT Discount_Percentage__c, Final_Amount__c FROM Opportunity WHERE Id = :opp.Id];
        System.assertEquals(5.00, updatedOpp.Discount_Percentage__c, 'Null tier should get base discount only');
        System.assertEquals(190000, updatedOpp.Final_Amount__c, 'Final amount should be 95% of original');
    }

    @IsTest
    static void testBulkProcessing() {
        // Test bulk processing of 200 opportunities
        Account acc = [SELECT Id FROM Account LIMIT 1];
        List<Opportunity> opps = new List<Opportunity>();
        List<String> tiers = new List<String>{'Bronze', 'Silver', 'Gold', 'Platinum'};

        for (Integer i = 0; i < 200; i++) {
            opps.add(new Opportunity(
                Name = 'Bulk Opp ' + i,
                AccountId = acc.Id,
                Amount = (i + 1) * 10000,
                Customer_Tier__c = tiers[Math.mod(i, 4)],
                StageName = 'Prospecting',
                CloseDate = Date.today().addDays(30)
            ));
        }
        insert opps;

        List<Id> oppIds = new List<Id>();
        for (Opportunity o : opps) {
            oppIds.add(o.Id);
        }

        Test.startTest();
        OpportunityDiscountCalculator.calculateDiscounts(oppIds);
        Test.stopTest();

        List<Opportunity> updatedOpps = [SELECT Discount_Percentage__c, Final_Amount__c FROM Opportunity WHERE Id IN :oppIds];
        System.assertEquals(200, updatedOpps.size(), 'All 200 opportunities should be processed');

        for (Opportunity o : updatedOpps) {
            System.assertNotEquals(null, o.Discount_Percentage__c, 'All opportunities should have discount calculated');
        }
    }
}
