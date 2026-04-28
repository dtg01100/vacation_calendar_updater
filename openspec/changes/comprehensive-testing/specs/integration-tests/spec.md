# Integration Test Suite Specification

## Overview

This specification defines end-to-end integration tests covering all four user modes: Create, Update, Delete, and Import.

## ADDED Requirements

### Requirement: Create Mode Integration Tests

The test suite SHALL include integration tests for the event creation workflow.

#### Scenario: Create single-day event
**WHEN:** User creates an event for a single day  
**THEN:** The system SHALL create exactly one calendar event

#### Scenario: Create multi-day vacation schedule
**WHEN:** User creates a vacation spanning multiple weekdays  
**THEN:** The system SHALL create events for each scheduled day

#### Scenario: Create event with email notification
**WHEN:** User enables email notification during creation  
**THEN:** The system SHALL send a notification email after successful creation

#### Scenario: Create event with stop requested
**WHEN:** User requests stop during multi-event creation  
**THEN:** The system SHALL stop after the current event and emit stopped signal

---

### Requirement: Update Mode Integration Tests

The test suite SHALL include integration tests for batch update operations.

#### Scenario: Update batch events
**WHEN:** User updates an existing batch of events  
**THEN:** All events in the batch SHALL be updated with new details

#### Scenario: Update with stop requested
**WHEN:** User requests stop during batch update  
**THEN:** The system SHALL stop after current event and save partial progress

---

### Requirement: Delete Mode Integration Tests

The test suite SHALL include integration tests for event deletion and restoration.

#### Scenario: Delete single event
**WHEN:** User deletes an event  
**THEN:** The event SHALL be removed from Google Calendar

#### Scenario: Delete batch with undo
**WHEN:** User deletes a batch and then undoes  
**THEN:** The UndoManager SHALL restore events to their original state

#### Scenario: Delete already-deleted event (404 handling)
**WHEN:** User attempts to delete an event that no longer exists  
**THEN:** The system SHALL skip gracefully and continue with remaining events

---

### Requirement: Import Mode Integration Tests

The test suite SHALL include integration tests for importing events from Gmail.

#### Scenario: Import new events
**WHEN:** User initiates import with new events in inbox  
**THEN:** The system SHALL import all new events with correct dates

#### Scenario: Import with no new events
**WHEN:** User initiates import with empty inbox  
**THEN:** The system SHALL display appropriate "no events found" message

#### Scenario: Import with shutdown during fetch
**WHEN:** User requests shutdown while import is in progress  
**THEN:** The system SHALL cancel gracefully without corrupting state

---

### Requirement: Mode Transition Tests

The test suite SHALL include tests for switching between modes.

#### Scenario: Transition from Create to Update
**WHEN:** User switches from Create mode to Update mode  
**THEN:** UI SHALL update to show batch selection controls

#### Scenario: Transition from Update to Delete
**WHEN:** User switches from Update mode to Delete mode  
**THEN:** UI SHALL confirm batch selection before showing delete controls

#### Scenario: Transition to Import from any mode
**WHEN:** User switches to Import mode  
**THEN:** Import panel SHALL be displayed and other mode controls SHALL be hidden