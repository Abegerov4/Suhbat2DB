# Диаграммы

Исходники диаграмм лежат в текстовых файлах [Mermaid](https://mermaid.js.org/) (`*.mmd`). Их можно править в любом редакторе, а GitHub отображает их сам. Рядом лежат экспорты в SVG.

| Диаграмма | Исходник | Экспорт | Где описана |
|---|---|---|---|
| Контекст системы (C4, уровень 1) | [context.mmd](context.mmd) | [context.svg](context.svg) | [proposal](../proposal.md) |
| Варианты использования | [use_cases.mmd](use_cases.mmd) | [use_cases.svg](use_cases.svg) | [requirements](../requirements.md) |
| Компоненты (C4, уровень 2) | [components.mmd](components.mmd) | [components.svg](components.svg) | [ARCHITECTURE §1](../../ARCHITECTURE.md#1-компоненты) |
| Развёртывание | [deployment.mmd](deployment.mmd) | [deployment.svg](deployment.svg) | [ARCHITECTURE §2](../../ARCHITECTURE.md#2-развёртывание) |
| Граф агента (упрощённо) | [agent_graph.mmd](agent_graph.mmd) | [agent_graph.svg](agent_graph.svg) | [ARCHITECTURE §3](../../ARCHITECTURE.md#3-граф-агента); полная версия, построенная из кода, в [graph.md](../graph.md) |
| Путь одного запроса (последовательность) | [request_sequence.mmd](request_sequence.mmd) | [request_sequence.svg](request_sequence.svg) | [ARCHITECTURE §4](../../ARCHITECTURE.md#4-путь-одного-запроса) |

Диаграмма вариантов использования нарисована средствами Mermaid: актёры и варианты изображены овалами, связи `«include»` и `«extend»` подписаны. Нотация близка к UML, но строгим UML не является.

Пересборка экспортов:

```bash
cd docs/diagrams
for f in *.mmd; do npx -y @mermaid-js/mermaid-cli@11.4.2 -i "$f" -o "${f%.mmd}.svg" -b white; done
```
