# Diagrams

The diagram sources are text files in [Mermaid](https://mermaid.js.org/) (`*.mmd`). They can be edited in any editor, and GitHub renders them directly. SVG exports are stored next to them.

| Diagram | Source | Export | Where it is described |
|---|---|---|---|
| System context (C4, level 1) | [context.mmd](context.mmd) | [context.svg](context.svg) | [proposal](../proposal.md) |
| Use cases | [use_cases.mmd](use_cases.mmd) | [use_cases.svg](use_cases.svg) | [requirements](../requirements.md) |
| Components (C4, level 2) | [components.mmd](components.mmd) | [components.svg](components.svg) | [ARCHITECTURE §1](../../ARCHITECTURE.md#1-components) |
| Deployment | [deployment.mmd](deployment.mmd) | [deployment.svg](deployment.svg) | [ARCHITECTURE §2](../../ARCHITECTURE.md#2-deployment) |
| Agent graph (simplified) | [agent_graph.mmd](agent_graph.mmd) | [agent_graph.svg](agent_graph.svg) | [ARCHITECTURE §3](../../ARCHITECTURE.md#3-agent-graph); the full version built from the code is in [graph.md](../graph.md) |
| Path of one request (sequence) | [request_sequence.mmd](request_sequence.mmd) | [request_sequence.svg](request_sequence.svg) | [ARCHITECTURE §4](../../ARCHITECTURE.md#4-path-of-one-request) |

The use case diagram is drawn with Mermaid: actors and use cases are shown as ovals, and the `«include»` and `«extend»` relations are labelled. The notation is close to UML but is not strict UML.

Rebuilding the exports:

```bash
cd docs/diagrams
for f in *.mmd; do npx -y @mermaid-js/mermaid-cli@11.4.2 -i "$f" -o "${f%.mmd}.svg" -b white; done
```
