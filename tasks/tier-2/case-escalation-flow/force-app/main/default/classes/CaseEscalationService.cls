/**
 * CaseEscalationService - Invocable Apex class for case escalation
 * 
 * Provides a bulkified method for escalating multiple cases at once.
 * Sets Priority to High, Status to Escalated, and adds a CaseComment.
 */
public with sharing class CaseEscalationService {
    
    /**
     * Wrapper class for invocable method input
     */
    public class EscalationRequest {
        @InvocableVariable(label='Case IDs to Escalate' required=true)
        public List<Id> caseIds;
    }
    
    /**
     * Wrapper class for invocable method output
     */
    public class EscalationResult {
        @InvocableVariable(label='Escalated Case IDs')
        public List<Id> escalatedCaseIds;
        
        @InvocableVariable(label='Number of Cases Escalated')
        public Integer escalatedCount;
    }
    
    /**
     * Escalates the provided cases by setting Priority to High,
     * Status to Escalated, and adding a comment with the user's name.
     * 
     * @param requests List of EscalationRequest containing Case IDs
     * @return List of EscalationResult with escalated Case IDs
     */
    @InvocableMethod(
        label='Escalate Cases'
        description='Escalates cases by setting Priority to High, Status to Escalated, and adding a comment'
    )
    public static List<EscalationResult> escalateCases(List<EscalationRequest> requests) {
        List<EscalationResult> results = new List<EscalationResult>();
        
        if (requests == null || requests.isEmpty()) {
            return results;
        }
        
        // Collect all case IDs from all requests
        Set<Id> allCaseIds = new Set<Id>();
        for (EscalationRequest req : requests) {
            if (req.caseIds != null) {
                allCaseIds.addAll(req.caseIds);
            }
        }
        
        if (allCaseIds.isEmpty()) {
            EscalationResult emptyResult = new EscalationResult();
            emptyResult.escalatedCaseIds = new List<Id>();
            emptyResult.escalatedCount = 0;
            results.add(emptyResult);
            return results;
        }
        
        // Get the running user's name
        String userName = UserInfo.getName();
        
        // Query the cases to update - bulkified
        List<Case> casesToUpdate = [
            SELECT Id, Priority, Status 
            FROM Case 
            WHERE Id IN :allCaseIds
        ];
        
        // Update case fields - bulkified (no DML in loop)
        for (Case c : casesToUpdate) {
            c.Priority = 'High';
            c.Status = 'Escalated';
        }
        
        // Perform the update - single DML statement
        update casesToUpdate;
        
        // Create case comments - bulkified
        List<CaseComment> comments = new List<CaseComment>();
        for (Case c : casesToUpdate) {
            comments.add(new CaseComment(
                ParentId = c.Id,
                CommentBody = 'Case escalated by ' + userName,
                IsPublished = true
            ));
        }
        
        // Insert all comments at once - single DML statement
        insert comments;
        
        // Build result
        EscalationResult result = new EscalationResult();
        result.escalatedCaseIds = new List<Id>();
        for (Case c : casesToUpdate) {
            result.escalatedCaseIds.add(c.Id);
        }
        result.escalatedCount = casesToUpdate.size();
        results.add(result);
        
        return results;
    }
    
    /**
     * Simplified method for direct Apex calls (used by tests)
     */
    public static List<Id> escalateCases(List<Id> caseIds) {
        EscalationRequest req = new EscalationRequest();
        req.caseIds = caseIds;
        
        List<EscalationResult> results = escalateCases(new List<EscalationRequest>{ req });
        
        if (!results.isEmpty() && results[0].escalatedCaseIds != null) {
            return results[0].escalatedCaseIds;
        }
        return new List<Id>();
    }
}
