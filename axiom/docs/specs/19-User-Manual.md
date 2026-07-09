# User Manual
## Enterprise AI Platform — OCIF

**Document 19 of 20** | **Traces to:** Documents 1–18
**Status:** Draft v1.0 — Pending Approval

---

## 1. Introduction

This manual guides end users, process owners, compliance officers, and administrators through day-to-day use of the OCIF Enterprise AI Platform. It complements the UI/UX Design (Document 15) with task-oriented instructions.

---

## 2. Getting Started

1. Sign in via your organization's single sign-on (SSO) portal.
2. On first login, you'll see the **Chat** screen by default. Your available features (Workflow Builder, Approval Console, Admin Console) depend on your assigned role (see Document 14, Section 3.1).

---

## 3. Using Chat & Copilot

### 3.1 Asking a Question
Type your question in natural language. The assistant will:
- Search enterprise knowledge relevant to your question.
- Respond with an answer, a **confidence score**, and **source citations**.
- If no relevant knowledge is found, it will tell you clearly rather than guessing.

### 3.2 Understanding Confidence Scores
| Badge Color | Meaning |
|---|---|
| Green (≥85%) | High confidence, well-grounded in sources |
| Amber (60–84%) | Moderate confidence — review citations before relying on this |
| Red (<60%) | Low confidence — treat as a starting point only, verify independently |

### 3.3 Viewing the Decision Trace
Click **"View decision trace"** below any response to see exactly which knowledge sources were used, which reasoning steps were taken, and (if applicable) which policy checks a proposed action passed through.

### 3.4 Giving Feedback
Use the thumbs up/down icons to rate a response. If a response is incorrect, click **"Suggest correction"** to help improve future answers.

---

## 4. Working with Proposed Actions

Some requests result in the assistant proposing an action (e.g., "issue a refund," "update a record") rather than just answering. You'll see an **Action Proposal Card** showing:
- What the action is
- Its risk level
- Whether it requires approval

If you have approval authority and the action is low-risk, you may see **Approve/Reject** buttons directly in chat. Higher-risk actions always route to the **Approval Console** for formal review — this cannot be bypassed (see Document 7, Section 8).

---

## 5. Using the Approval Console (Process Owners, Compliance Officers)

1. Navigate to **Approval Console** from the main menu.
2. Review pending items, sorted by risk score or age.
3. Click an item to see full context: the original request, retrieved sources, the proposed action, and which policy rules it was checked against.
4. Choose **Approve**, **Reject**, or **Request More Info**.
5. Your decision is permanently logged in the audit trail — it cannot be edited or deleted afterward.

---

## 6. Using Dashboards

Navigate to **Dashboards** to view:
- **Usage & Cost:** requests, tokens consumed, and cost trends.
- **Automation Rate:** percentage of actions auto-approved vs. requiring human review vs. blocked.
- **Quality:** average confidence and user feedback ratings over time.

Executives and process owners can export dashboard views as reports.

---

## 7. Searching Enterprise Knowledge Directly

Use **Knowledge Search** to query indexed documents without a conversational assistant response — useful for browsing source material directly. Results show the same citation and relevance-score information used internally by the assistant.

---

## 8. Administrator Tasks (Tenant Admin / Platform Admin)

### 8.1 Managing Policies
Go to **Admin → Policies** to create or edit business rules governing what actions can be auto-approved, require approval, or are blocked outright. Use the **"Test Policy"** sandbox before activating any change.

### 8.2 Managing Tools
Go to **Admin → Tool Registry** to register new enterprise APIs/tools the assistant and agents can use. Each tool requires a defined risk level and approval requirement.

### 8.3 Managing Users & Roles
Go to **Admin → Users** to assign roles (end_user, process_owner, compliance_officer, tenant_admin) per the RBAC model (Document 14, Section 3.1).

---

## 9. Troubleshooting

| Issue | Resolution |
|---|---|
| "No relevant knowledge found" for a question you expect it to know | The source document may not be indexed yet — contact your admin to confirm ingestion status |
| A proposed action is stuck "pending" | Check the Approval Console — it likely needs review from an authorized approver |
| Response seems outdated | Source documents may need re-ingestion; contact your admin |
| Access denied to a feature | Your role may not include that permission; contact your tenant admin |

---

## 10. Getting Help

Contact your organization's platform administrator, or use the in-app **Feedback** option to report issues directly to the platform team.

---

## 11. Traceability

This manual documents end-user workflows for features F-01–F-20 (Document 3 — PRD) as implemented per the UI/UX Design (Document 15).

---
*End of User Manual*
