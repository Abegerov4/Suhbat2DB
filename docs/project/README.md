# Project management

## YouTrack

Project tasks are tracked in YouTrack: [wasm.youtrack.cloud/issues/DIP](https://wasm.youtrack.cloud/issues/DIP), project `DIP` (Kanban template). As of 21.10.2026, 36 tasks had been created.

| Tasks | Contents | State |
|---|---|---|
| DIP-1…8 | Plan by roles and roles 1–7, with links to the commits | Done |
| DIP-9…16 | Pre-defence 1 documents: architecture, proposal, requirements, literature review, comparisons, diagrams, roadmap | Review |
| DIP-17, DIP-18 | Figma prototype, tag `pre-defense-1` | Queue |
| DIP-19…36 | Plan until May 2027: interviews, prompt v2, stage 2 evaluation, diploma chapters, pre-defences | Queue |

Each task states the expected result, the acceptance criterion and the deadline. The completed tasks DIP-1…8 were created on 21.10.2026 already closed, because before that date the work was planned in [docs/roles](../roles/README.md). The original task list is kept in [`youtrack_tasks.csv`](youtrack_tasks.csv).

## Workflow since 22.10.2026

1. A task in YouTrack: assignee, expected result, acceptance criterion, deadline.
2. A branch from `main`: `DIP-<number>-<short-name>`, for example `DIP-21-prompt-v2-refusals`.
3. Commits: `DIP-21: Reduce false out_of_scope refusals`.
4. A pull request to `main`: what was changed, a link to the task, how it was checked (tests, evals). The supervisor reviews significant changes at the agreed milestones.
5. After the merge, the link to the pull request is added to the task. A task is closed only when its acceptance criterion is met.
6. Each submitted version gets a tag: `pre-defense-1`, `pre-defense-2`, `final-pre-defense`. A tag is not moved after the version has been submitted.

## Templates

- [User interview](../templates/interview.md)
- [Supervisor meeting notes](../templates/supervisor_meeting.md)
