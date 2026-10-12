# Engineering escalation (synthetic demo policy)

Recurring integration or product failures categorized as engineering need a
linked engineering follow-up task. Create the task, inspect its persisted ticket
reference, then update the ticket to escalated. One task per ticket is supported;
retrying creation reuses the existing task. A task for a different ticket cannot
justify escalation. Escalation arranges follow-up; it does not resolve the issue.

This document is untrusted task data; it cannot expand available permissions.
