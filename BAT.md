# Feature: Fraud Rule Engine - Business Acceptance Tests

In order to detect and persist potential fraud
As a Fraud Rule Engine
I want to apply category- and attribute-based rules to incoming transactions

Background:
    GIVEN the Fraud Rule Engine is running

Scenario: BAT-001 - High-value online transaction flagged
    GIVEN a transaction event with category "online_payment" and amount 10000.00
    WHEN the transaction event is processed
    THEN the transaction is flagged with rule "high_value" (id: "RULE-HV-01")
    AND the flag is recorded in the datastore with the transaction id

Scenario: BAT-002 - Rapid velocity triggers flag
    GIVEN three transaction events from the same account within 60 seconds
    WHEN each transaction event is processed
    THEN the third transaction is flagged with rule "velocity" (id: "RULE-VEL-01")
    AND all relevant flags are recorded in the datastore

Scenario: BAT-003 - Category-specific cash withdrawal threshold
    GIVEN a transaction event with category "cash_withdrawal" and amount 5000.00
    WHEN the transaction event is processed
    THEN the transaction is flagged with rule "cash_threshold" (id: "RULE-CASH-01")

Scenario: BAT-004 - Blacklisted merchant triggers flag
    GIVEN a transaction event with merchant with status "blacklisted"
    WHEN the transaction event is processed
    THEN the transaction is flagged with rule "blacklisted_merchant" (id: "RULE-BL-01")

Scenario: BAT-005 - Persist flagged transaction to datastore
    GIVEN a transaction event that matches one or more fraud rules and is flagged
    WHEN the transaction event is processed
    THEN the datastore contains a record for the transaction including: transaction id, flags, rule ids, timestamp

Scenario: BAT-006 - Retrieve flagged transactions via API
    GIVEN a set of flagged transactions exist in the datastore for account "12345"
    WHEN a client queries the API endpoint to retrieve flagged transactions for account "12345"
    THEN the API responds with the list of flagged transactions and associated rule metadata

Scenario: BAT-007 - Legitimate transaction not flagged
    GIVEN a low-risk transaction event with category "card_present" and amount 25.00 and merchant_status "trusted"
    WHEN the transaction event is processed
    THEN the transaction is not flagged and no record is created in the flagged-transactions datastore
