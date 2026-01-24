/**
 * Test class for AccountTerritoryTrigger and AccountTerritoryHandler
 *
 * Tests:
 * - Territory assignment for each region (West, East, South, Central, Other)
 * - Territory update when BillingState changes
 * - Bulk insert handling (200 records)
 * - Null BillingState handling
 */
@IsTest
private class AccountTerritoryTriggerTest {

    @IsTest
    static void testWestTerritory() {
        // Test West territory states: CA, OR, WA
        List<Account> accounts = new List<Account>();
        accounts.add(new Account(Name = 'Test CA', BillingState = 'CA'));
        accounts.add(new Account(Name = 'Test OR', BillingState = 'OR'));
        accounts.add(new Account(Name = 'Test WA', BillingState = 'WA'));

        Test.startTest();
        insert accounts;
        Test.stopTest();

        List<Account> insertedAccounts = [SELECT Territory__c FROM Account WHERE Id IN :accounts];
        for (Account acc : insertedAccounts) {
            System.assertEquals('West', acc.Territory__c, 'West coast states should be assigned West territory');
        }
    }

    @IsTest
    static void testEastTerritory() {
        // Test East territory states: NY, NJ, CT, MA
        List<Account> accounts = new List<Account>();
        accounts.add(new Account(Name = 'Test NY', BillingState = 'NY'));
        accounts.add(new Account(Name = 'Test NJ', BillingState = 'NJ'));
        accounts.add(new Account(Name = 'Test CT', BillingState = 'CT'));
        accounts.add(new Account(Name = 'Test MA', BillingState = 'MA'));

        Test.startTest();
        insert accounts;
        Test.stopTest();

        List<Account> insertedAccounts = [SELECT Territory__c FROM Account WHERE Id IN :accounts];
        for (Account acc : insertedAccounts) {
            System.assertEquals('East', acc.Territory__c, 'East coast states should be assigned East territory');
        }
    }

    @IsTest
    static void testSouthTerritory() {
        // Test South territory states: TX, FL, GA
        List<Account> accounts = new List<Account>();
        accounts.add(new Account(Name = 'Test TX', BillingState = 'TX'));
        accounts.add(new Account(Name = 'Test FL', BillingState = 'FL'));
        accounts.add(new Account(Name = 'Test GA', BillingState = 'GA'));

        Test.startTest();
        insert accounts;
        Test.stopTest();

        List<Account> insertedAccounts = [SELECT Territory__c FROM Account WHERE Id IN :accounts];
        for (Account acc : insertedAccounts) {
            System.assertEquals('South', acc.Territory__c, 'South states should be assigned South territory');
        }
    }

    @IsTest
    static void testCentralTerritory() {
        // Test Central territory states: IL, MI, OH
        List<Account> accounts = new List<Account>();
        accounts.add(new Account(Name = 'Test IL', BillingState = 'IL'));
        accounts.add(new Account(Name = 'Test MI', BillingState = 'MI'));
        accounts.add(new Account(Name = 'Test OH', BillingState = 'OH'));

        Test.startTest();
        insert accounts;
        Test.stopTest();

        List<Account> insertedAccounts = [SELECT Territory__c FROM Account WHERE Id IN :accounts];
        for (Account acc : insertedAccounts) {
            System.assertEquals('Central', acc.Territory__c, 'Central states should be assigned Central territory');
        }
    }

    @IsTest
    static void testOtherTerritory() {
        // Test Other territory for states not in defined regions
        Account acc = new Account(Name = 'Test AZ', BillingState = 'AZ');

        Test.startTest();
        insert acc;
        Test.stopTest();

        Account insertedAcc = [SELECT Territory__c FROM Account WHERE Id = :acc.Id];
        System.assertEquals('Other', insertedAcc.Territory__c, 'Non-defined states should be assigned Other territory');
    }

    @IsTest
    static void testNullBillingState() {
        // Test null BillingState handling
        Account acc = new Account(Name = 'Test Null State');

        Test.startTest();
        insert acc;
        Test.stopTest();

        Account insertedAcc = [SELECT Territory__c FROM Account WHERE Id = :acc.Id];
        System.assertEquals('Unassigned', insertedAcc.Territory__c, 'Null BillingState should result in Unassigned territory');
    }

    @IsTest
    static void testTerritoryUpdateOnStateChange() {
        // Test that territory updates when BillingState changes
        Account acc = new Account(Name = 'Test Update', BillingState = 'CA');
        insert acc;

        Account insertedAcc = [SELECT Territory__c FROM Account WHERE Id = :acc.Id];
        System.assertEquals('West', insertedAcc.Territory__c, 'Initial territory should be West');

        Test.startTest();
        acc.BillingState = 'NY';
        update acc;
        Test.stopTest();

        Account updatedAcc = [SELECT Territory__c FROM Account WHERE Id = :acc.Id];
        System.assertEquals('East', updatedAcc.Territory__c, 'Territory should update to East after state change');
    }

    @IsTest
    static void testBulkInsert() {
        // Test bulk insert of 200 records
        List<Account> accounts = new List<Account>();
        List<String> states = new List<String>{'CA', 'NY', 'TX', 'IL', 'AZ'};

        for (Integer i = 0; i < 200; i++) {
            String state = states[Math.mod(i, states.size())];
            accounts.add(new Account(Name = 'Bulk Test ' + i, BillingState = state));
        }

        Test.startTest();
        insert accounts;
        Test.stopTest();

        // Verify all accounts have a territory assigned
        List<Account> insertedAccounts = [SELECT Territory__c FROM Account WHERE Id IN :accounts];
        System.assertEquals(200, insertedAccounts.size(), 'All 200 accounts should be inserted');

        for (Account acc : insertedAccounts) {
            System.assertNotEquals(null, acc.Territory__c, 'All accounts should have a territory assigned');
        }
    }
}
