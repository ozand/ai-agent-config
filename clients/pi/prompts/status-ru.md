---
description: Generate a brief business-friendly project status report in Russian
---
Generate a brief, non-technical status report in Russian.

Rules:
- Use simple business language understandable to a non-technical reader.
- Use only confirmed information from the current session and project; do not invent details.
- Report only the current status.
- Under "In Progress", include only tasks that are actively being worked on now.
- If a section has no items, write "Нет".
- Do not add an introduction, conclusion, or unnecessary technical details.
- Do not report a task as completed on the strength of a plan or a passing intention. Completed means verified — checks run, result observed. If it was not verified, it belongs under "В работе".

Under "Требуются решения", include every item that is genuinely waiting on the user, in plain language:
- proposed architectural decisions awaiting approval (ADRs with status `Proposed`);
- actions that cannot be undone and were held for approval;
- anything blocked on access, credentials, or a choice only the user can make.

Use exactly these four bulleted sections:

- **🟢 Завершено**
  - ...
- **🔄 В работе**
  - ...
- **📋 Запланировано**
  - ...
- **⚠️ Требуются решения**
  - Explicitly state whether the user needs to approve or decide anything to unblock your work. Name what specifically becomes possible once they decide. If nothing is needed, write: "Одобрение или решение не требуется".
