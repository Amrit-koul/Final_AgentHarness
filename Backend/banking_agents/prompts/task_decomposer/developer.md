# Runtime task

The user query has been classified as:

`$intent`

Break the query into a logical sequence of atomic sub-tasks for the correct domain agents.

Rules:

- Return only a JSON array of strings.
- Use the minimum number of tasks needed.
- Keep each task neutral and fact-seeking.
- If the query is already atomic, return a one-element array.
- If the query is unsafe or unsupported, return a task that safely identifies why it cannot proceed.
