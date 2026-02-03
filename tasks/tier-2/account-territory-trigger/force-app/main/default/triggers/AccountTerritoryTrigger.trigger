/**
 * Trigger for Account territory assignment
 * 
 * Fires on before insert and before update to automatically assign
 * territories based on billing address state
 */
trigger AccountTerritoryTrigger on Account (before insert, before update) {
    AccountTerritoryHandler.assignTerritories(Trigger.new);
}