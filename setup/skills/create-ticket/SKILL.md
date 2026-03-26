---
name: create-ticket
description: Create a Jira ticket in the NOP project with proper custom fields, templates, and workflow transitions
argument-hint: "<summary>" [--type Story|Defect] [--brand "CP & CU"|CP|CU] [--sprint "Tech Debt Backlog"] [--labels Backend,TechnicalDebt] [--due YYYY-MM-DD]
---

# Create a Jira Ticket (NOP Project)

Create a Jira ticket based on the conversation context and user input.

## Input

- **$ARGUMENTS** — The raw arguments. Parse them as follows:
  - First quoted string or free text = ticket summary
  - `--type` = issue type (default: `Story`)
  - `--brand` = brand (default: `CP & CU`)
  - `--sprint` = sprint name (default: none)
  - `--labels` = comma-separated labels (default: none)
  - `--due` = due date in `YYYY-MM-DD` format (default: none)
  - Any remaining text = additional context for the description

**Due date detection:** Even without `--due`, scan the full conversation context for any explicit deadlines or dates (e.g. "bis 30. September 2028", "Retirement-Datum: 30.09.2028", "by Q3 2026"). If found, convert to `YYYY-MM-DD` and use as the due date. Always prefer the most concrete/specific date mentioned.

## Jira Field Reference

### Required custom fields for Story

| Field | Custom field ID | Format | Known values |
|---|---|---|---|
| Brand | `customfield_11115` | array of strings | `"CP"`, `"CU"`, `"CP & CU"` |
| (always set) | `customfield_11109` | array of strings | always `["Alle"]` |
| Akzeptanzkriterien | `customfield_11001` | Atlassian Document Format (ADF) | see below |

### Akzeptanzkriterien ADF format

```json
{
  "type": "doc",
  "version": 1,
  "content": [{
    "type": "bulletList",
    "content": [{
      "type": "listItem",
      "content": [{"type": "paragraph", "content": [{"type": "text", "text": "criterion text"}]}]
    }]
  }]
}
```

### Sprint field

- Custom field ID: `customfield_10020`
- Value: integer sprint ID
- Board ID for NOP project: `536`
- To resolve a sprint name to an ID, use `jira_get_sprints_from_board` with board_id `536` and state `future` (or `active`). Match the sprint name from the results and use its `id`.

### Labels

- Pass via `additional_fields`, not as a top-level parameter
- Labels cannot contain spaces (e.g. `TechnicalDebt` not `Technical Debt`)
- IT-department-driven tickets get the `TechnicalDebt` label in addition to their area label (e.g. `Backend`, `Frontend`)

### Issue link types

| Name | Inward | Outward |
|---|---|---|
| Blocks | `is blocked by` | `blocks` |
| Duplicate | `is duplicated by` | `duplicates` |
| Relates | `relates to` | `relates to` |

Link type ID for "Blocks": `10000`. Use link name `"Relates"` (not `"Relates to"`).

For "Blocks" direction in `jira_create_issue_link`: `inward_issue_key` = the BLOCKER, `outward_issue_key` = the BLOCKED.

### Ticket title convention

Do NOT prefix titles with ticket numbers. Use a concise topic prefix in German that groups related tickets, followed by a colon.
Example: `Session Invalidierung: JWT Token Invalidierung via Redis jti-Allowlist implementieren`

## Ticket Templates

### Story (in German)

Required sections in the description:

**Beschreibung**
Beschreibe die Anforderung in 2–3 Sätzen (Was soll umgesetzt werden?)

**Wer ist Ansprechpartner**
Haupt-Ansprechpartner & Vertreter

**Begründung der Anforderung**
Welchen Mehrwert bringt die Umsetzung, bzw. welches Problem löst es?

**IST-Verhalten**
Beschreibe die derzeitige Lösung, falls vorhanden (inkl. Beispiele)

**SOLL-Verhalten**
Beschreibe die gewünschte Lösung (inkl. Screenshots, Scribbles, User Flows, Designs, falls vorhanden)

**Anforderung an Tracking**
Wird ein Tracking in Adobe/Webtrekk/SAP benötigt und was soll gemessen werden?
*For backend-only tickets: omit this section entirely.*

**A/B Test**
Kann die Idee vorher als A/B-Test getestet werden?
*For backend-only tickets: omit this section entirely.*

**Dokumentation & Dringlichkeit**
Alle wichtige Quellen & Links, Fälligkeiten und bekannte Abhängigkeiten.

### Defect (in German)

Required sections in the description:

**Zusammenfassung**
Ein prägnanter Satz: Was passiert wo unter welchen Umständen?

**Schritte zur Reproduktion**
1. Gehe auf Seite X...
2. Klicke auf Y...

**Erwartetes Verhalten**
Was hätte passieren sollen?

**Tatsächliches Verhalten**
Was passiert stattdessen?

**Umgebung & Kontext**
Gerät/Browser, User/Account, etc.

**Beweismittel (Attachments)**
Screenshot oder Video — besonders bei UI-Fehlern Pflicht.

## Instructions

### Step 0 — Resolve the current user's identity

Before composing the ticket, determine who is creating it:

1. Call `jira_search` with JQL `assignee = currentUser() ORDER BY created DESC` (limit 1) and extract `assignee.displayName` and `assignee.accountId` from the result.
2. Use this identity to populate the **Wer ist Ansprechpartner** section as:
   `<DisplayName> [~accountid:<accountId>]`

### Step 1 — Ask for target sprint

Unless `--sprint` was already provided in the arguments:

1. Call `jira_get_sprints_from_board` with board_id `536` and state `active`, then again with state `future` and limit `50` to get all available sprints.
2. Filter the results to only include:
   - All active sprints
   - Future sprints whose name contains "Backlog" (case-insensitive)
3. Present the filtered list to the user as a numbered menu, e.g.:
   ```
   Which sprint should this ticket be assigned to?
   0. No sprint
   1. WEB-Sprint 6: 23 März - 7 Apr (active, ends 07.04.)
   2. Tech Debt Backlog (future)
   3. Demands Backlog (future)
   ```
4. Wait for the user's selection before proceeding.
5. Resolve the chosen sprint name to its integer ID for use in `customfield_10020`.

### Step 3 — Compose the ticket

Based on the issue type, follow the appropriate template structure above.

**CRITICAL: Never invent content for any section.** Fill sections ONLY with information from the conversation or user input. If no information is available for a section, omit it entirely. Do not paraphrase, extrapolate, or guess.

Write all ticket content in **German**.

### Step 4 — Show preview

Show a formatted preview of the ticket to the user and ask for confirmation before creating it. Include:
- Summary
- Type
- Labels
- Brand
- Sprint (if set)
- Due date (if detected or provided)
- Description (full text)
- Akzeptanzkriterien (if Story)

### Step 5 — Create the ticket

After user confirmation, create the ticket via `jira_create_issue` with:
- `project_key`: `NOP`
- `summary`: the ticket summary
- `issue_type`: Story or Defect
- `description`: the composed description in Markdown format
- `additional_fields`: JSON containing:
  - `customfield_11115`: Brand array
  - `customfield_11109`: `["Alle"]` (for Stories)
  - `customfield_11001`: Akzeptanzkriterien in ADF format (for Stories)
  - `customfield_10020`: Sprint ID as a plain integer, not an object (if sprint selected)
  - `labels`: array of label strings
- `customfield_10999`: due date string in `YYYY-MM-DD` format (if a due date was detected or provided) — this is the NOP project's custom "Fälligkeitsdatum" field shown in the UI; do NOT use the standard `duedate` field

### Step 6 — Transition to "Ready 4 Groom"

After successful creation, immediately transition the ticket to **"Ready 4 Groom"**. Do not wait for the user to ask — this is standard workflow.

To find the correct transition ID:
1. Call `jira_get_transitions` for the newly created issue
2. Find the transition whose name matches "Ready 4 Groom"
3. Use that transition's ID with `jira_transition_issue`

### Step 7 — Report result

Show the user:
- Ticket key and link: `https://cyberport.atlassian.net/browse/NOP-XXXXX`
- Final status

## Example usage

```
/create-ticket "MailKit upgraden" --type Story --brand "CP & CU" --sprint "Tech Debt Backlog" --labels Backend,TechnicalDebt
```

```
/create-ticket "Login-Button reagiert nicht auf iOS" --type Defect --brand CU --labels Frontend
```

```
/create-ticket "Redis Connection Pooling optimieren"
```
(defaults to Story, CP & CU, no sprint, no labels — will compose from conversation context)
