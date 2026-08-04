---
name: macsoft-chart-visualization
description: Select chart forms and encodings for verified business data.
---

# MacSoft Chart Visualization

Use this skill when a user asks for a chart, comparison, trend, distribution,
relationship, or dashboard visualization. This skill decides what to show and
how fields map to visual channels. The dashboard skill owns the final HTML.

## Selection rules

| Question | Preferred chart |
|---|---|
| Change over an ordered time or sequence | `line` or `area` |
| Compare categories | `bar` or `column` |
| Compare two measures with different units | `dual-axis` only when one scale would mislead |
| Part-to-whole with a small number of categories | `pie` or `donut` |
| Relationship between two numeric measures | `scatter` |
| Distribution of a numeric measure | `histogram`, `boxplot`, or `violin` |
| Stage conversion | `funnel` |
| Flow between nodes | `sankey` |
| Hierarchical composition | `treemap` |
| Several measures across common dimensions | `radar` only when the dimensions are comparable |
| Exact records or many fields | `table` |

Prefer the simplest chart that answers the question. Use a table when exact
values matter more than pattern recognition. Do not use 3D effects or decorative
charts that imply precision the source data does not contain.

## Data and encoding rules

1. Use only fields and rows returned by an approved data query. Never invent
   values, dates, categories, totals, or targets.
2. Preserve the source type. A count is not a currency amount, and a document
   date is not an aging bucket unless the source provides that bucket or the
   calculation is explicitly defined.
3. State the aggregation and filters used by the chart. Missing values are not
   silently converted to zero.
4. Use encodings that match the chart:
   - line/area: ordered `x` plus numeric `y`, with optional `series`;
   - bar/column: categorical `category` plus numeric `value`, with optional
     `series`;
   - pie/donut: categorical `category` plus numeric `value`;
   - scatter: numeric `x` and `y`, with optional `series`;
   - table: explicit `columns` and `rows`.
5. Keep labels readable, sort intentionally, and explain any top-N or “other”
   grouping.

## MacSoft implementation boundary

This is a reasoning and design skill. Do not call an external visualization
API, use `curl`, return an image URL, or generate AntV/G2 code. When the
`macsoft-chart-dashboard` workflow asks for implementation, use its ECharts
contract and produce the single
HTML document required by that workflow. Do not assume that a CDN, artifact
store, or preview endpoint exists.
