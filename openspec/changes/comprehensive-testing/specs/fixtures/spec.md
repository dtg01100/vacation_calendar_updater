# Test Fixture Library Specification

## Overview

This specification defines the reusable test fixtures needed for comprehensive testing of the Vacation Calendar Updater application.

## ADDED Requirements

### Requirement: Mock Google API Fixture

The test suite SHALL provide a `mock_google_api` fixture that simulates Google Calendar and Gmail API responses without network calls.

#### Scenario: Mock calendar list retrieval
**WHEN:** A test requests the `mock_google_api` fixture  
**THEN:** The fixture SHALL return a mock calendar service with pre-configured calendars

#### Scenario: Mock event creation
**WHEN:** The mock calendar service receives a create event request  
**THEN:** It SHALL return a valid CreatedEvent with generated event_id

#### Scenario: Mock API error handling
**WHEN:** A test configures the mock to raise HttpError  
**THEN:** The mock SHALL propagate the error appropriately

---

### Requirement: Qt Application Fixture

The test suite SHALL provide a `qapp` fixture that creates a QApplication instance for UI testing.

#### Scenario: Single QApplication per session
**WHEN:** Multiple tests require `qapp`  
**THEN:** Only one QApplication instance SHALL exist per test session

#### Scenario: Offscreen platform for headless testing
**WHEN:** The `qapp` fixture is created  
**THEN:** It SHALL use the offscreen platform to enable headless testing

---

### Requirement: Undo Manager Test Fixture

The test suite SHALL provide an `undo_manager` fixture that creates a configured UndoManager instance.

#### Scenario: Fresh undo manager
**WHEN:** A test requests the `undo_manager` fixture  
**THEN:** It SHALL return an empty UndoManager with no history

#### Scenario: Pre-populated undo manager
**WHEN:** A test specifies initial batches  
**THEN:** The fixture SHALL populate the UndoManager with those batches

---

### Requirement: Sample Event Data Fixture

The test suite SHALL provide `sample_events` fixture containing typical EnhancedCreatedEvent objects.

#### Scenario: Single event fixture
**WHEN:** A test requests `sample_event`  
**THEN:** It SHALL return one valid EnhancedCreatedEvent

#### Scenario: Batch events fixture
**WHEN:** A test requests `sample_batch`  
**THEN:** It SHALL return a list of 5 EnhancedCreatedEvent objects sharing the same batch_id

---

### Requirement: Schedule Request Fixture

The test suite SHALL provide a `schedule_request` fixture that creates valid ScheduleRequest objects.

#### Scenario: Default schedule request
**WHEN:** A test requests `schedule_request`  
**THEN:** It SHALL return a ScheduleRequest with typical vacation dates (start: today, end: +5 days)

#### Scenario: Custom date range
**WHEN:** A test overrides date parameters  
**THEN:** The fixture SHALL accept custom start_date, end_date, and weekdays