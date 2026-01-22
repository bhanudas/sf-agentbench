/**
 * High-quality Apex class demonstrating best practices.
 * Expected rubric score: > 0.8
 * 
 * Best practices demonstrated:
 * - Bulkified operations (no SOQL/DML in loops)
 * - CRUD/FLS checks
 * - Proper error handling
 * - Well-structured and readable code
 */
public with sharing class LeadScoringService {
    
    // Constants
    private static final Integer INDUSTRY_TECH_BONUS = 10;
    private static final Integer INDUSTRY_FINANCE_BONUS = 10;
    private static final Integer HIGH_REVENUE_BONUS = 20;
    private static final Integer HIGH_EMPLOYEES_BONUS = 15;
    private static final Decimal REVENUE_THRESHOLD = 1000000;
    private static final Integer EMPLOYEES_THRESHOLD = 100;
    
    private static final Set<String> HIGH_VALUE_INDUSTRIES = new Set<String>{
        'Technology', 'Finance'
    };
    
    /**
     * Calculate and update lead scores for a batch of leads.
     * Bulkified and CRUD/FLS safe.
     * 
     * @param leadIds List of Lead IDs to score
     * @return Map of Lead ID to calculated score
     */
    public static Map<Id, Integer> calculateScores(List<Id> leadIds) {
        // Validate input
        if (leadIds == null || leadIds.isEmpty()) {
            return new Map<Id, Integer>();
        }
        
        // Check CRUD permissions
        if (!Schema.sObjectType.Lead.isAccessible()) {
            throw new LeadScoringException('Insufficient permissions to read Lead records');
        }
        
        // Query leads in bulk
        List<Lead> leads = [
            SELECT Id, Industry, Annual_Revenue__c, NumberOfEmployees
            FROM Lead
            WHERE Id IN :leadIds
            WITH SECURITY_ENFORCED
        ];
        
        // Calculate scores
        Map<Id, Integer> scoresByLeadId = new Map<Id, Integer>();
        List<Lead> leadsToUpdate = new List<Lead>();
        
        for (Lead l : leads) {
            Integer score = calculateSingleLeadScore(l);
            scoresByLeadId.put(l.Id, score);
            
            leadsToUpdate.add(new Lead(
                Id = l.Id,
                Lead_Score__c = score
            ));
        }
        
        // Update leads in bulk
        if (!leadsToUpdate.isEmpty() && Schema.sObjectType.Lead.isUpdateable()) {
            try {
                update leadsToUpdate;
            } catch (DmlException e) {
                throw new LeadScoringException('Failed to update lead scores: ' + e.getMessage());
            }
        }
        
        return scoresByLeadId;
    }
    
    /**
     * Calculate score for a single lead.
     * 
     * @param l The lead record
     * @return Calculated score
     */
    @TestVisible
    private static Integer calculateSingleLeadScore(Lead l) {
        Integer score = 0;
        
        // Industry bonus
        if (l.Industry != null && HIGH_VALUE_INDUSTRIES.contains(l.Industry)) {
            score += INDUSTRY_TECH_BONUS;
        }
        
        // Revenue bonus
        if (l.Annual_Revenue__c != null && l.Annual_Revenue__c > REVENUE_THRESHOLD) {
            score += HIGH_REVENUE_BONUS;
        }
        
        // Employee count bonus
        if (l.NumberOfEmployees != null && l.NumberOfEmployees > EMPLOYEES_THRESHOLD) {
            score += HIGH_EMPLOYEES_BONUS;
        }
        
        return score;
    }
    
    /**
     * Invocable method for Flow integration.
     */
    @InvocableMethod(label='Calculate Lead Scores' description='Calculates scores for the given leads')
    public static List<ScoreResult> calculateLeadScoresInvocable(List<ScoreRequest> requests) {
        List<ScoreResult> results = new List<ScoreResult>();
        
        // Collect all lead IDs
        List<Id> allLeadIds = new List<Id>();
        for (ScoreRequest req : requests) {
            if (req.leadIds != null) {
                allLeadIds.addAll(req.leadIds);
            }
        }
        
        // Calculate scores in bulk
        Map<Id, Integer> scores = calculateScores(allLeadIds);
        
        // Build results
        for (ScoreRequest req : requests) {
            ScoreResult result = new ScoreResult();
            result.scores = new List<Integer>();
            
            if (req.leadIds != null) {
                for (Id leadId : req.leadIds) {
                    result.scores.add(scores.get(leadId));
                }
            }
            
            results.add(result);
        }
        
        return results;
    }
    
    /**
     * Input class for invocable method.
     */
    public class ScoreRequest {
        @InvocableVariable(label='Lead IDs' required=true)
        public List<Id> leadIds;
    }
    
    /**
     * Output class for invocable method.
     */
    public class ScoreResult {
        @InvocableVariable(label='Calculated Scores')
        public List<Integer> scores;
    }
    
    /**
     * Custom exception for lead scoring errors.
     */
    public class LeadScoringException extends Exception {}
}
