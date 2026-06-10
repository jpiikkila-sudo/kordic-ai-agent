# Auto-Groom Jira Backlogs

**Vertical:** Atlassian system of work and Rovo agents
**Category:** How-to
**Reference Age:** 4 days

---

Title: Auto-Groom Jira Backlogs
Subtitle: Eliminate backlog noise with Atlassian Rovo and AI agent workflows.

When a deployment fails at 4:45 PM on a Friday, the last thing your team wants is to sort through a messy backlog of duplicate tickets. We found that most teams do this manually. 

So, use this automation model to route tickets and keep your workspace clean.

### Why Auto-Grooming Matters
A cluttered backlog slows down your sprint planning. It breeds confusion.
This guide shows you how to deploy a Rovo agent that sweeps your Jira backlog hourly, closing duplicate tickets and highlighting stale requests.

### Prerequisites
* Administrative access to your Jira Cloud environment.
* Atlassian Rovo API access.
* A secure API token stored in your environment.

### Implementation Blueprint
* **Step 1: Configure the Webhook**
  Navigate to Project Settings > Automation > Webhooks. Create a webhook that triggers on issue creation.
* **Step 2: Initialize Rovo Agent Prompt**
  Configure the agent prompt with specific instructions: "Scan the last 50 issues. If you detect a similarity score above 85%, mark the newer issue as a duplicate."
* **Step 3: Establish the Auto-Close Loop**
  Define the action path in Jira: Link the duplicate issue to the parent issue and transition it to closed status.

### Success Verification
Open a test issue that duplicates an existing ticket. The Rovo agent will automatically link and close the duplicate ticket within 5 minutes.