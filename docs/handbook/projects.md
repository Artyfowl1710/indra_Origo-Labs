# Project folders, goals and approvals


Use the native folder selector in Chat → Projects to grant a specific project. A folder grant is a meaningful permission boundary: select only what the task needs. Avoid whole drives, home directories and folders containing credentials. A file being present does not mean every format can be semantically parsed; unsupported files still need a suitable tool.

Describe the outcome as a goal with an objective check. "Repair checkout and make python verify_demo.py pass without changing protected inputs" is more reviewable than "improve everything." Let the agent establish a baseline before editing. Keep original requirements and tests intact when measuring progress.

Inspect proposed actions and grant permission only to the intended scope. Command execution, installing packages, external access and edits may require approval depending on your policy. Do not disable gates merely to make a demo faster. If a task is blocked, ask for a smaller safe next step.

Generated deliverables appear in the artifact area when recognized. A goal becoming green is useful evidence only when the check is meaningful and independently inspectable. Test passing does not establish correctness for every case. Use [the example verifier](../../examples/atlas-checkout/verify_demo.py) to see the protected-input and output checks used for this demo.
