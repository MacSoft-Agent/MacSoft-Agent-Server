---
name: macsoft-chart-dashboard
description: Orchestrate verified data and single-file HTML dashboards.
---

# MacSoft Chart Dashboard

Use this skill when the user asks for a chart, dashboard, KPI view, business
comparison, trend, or data-driven HTML page.

## Required workflow

1. Restate the decision the user wants to make. Identify the measure, unit,
   dimensions, time window, comparison, audience, and desired detail level.
2. If the source is AutoCount, load and follow the existing
   `macsoft-autocount:autocount-operations` skill. Use an approved structured
   read/query command and its real returned data. Do not use an HTML/report
   command as a chart data source.
3. Inspect the returned fields and rows before choosing a visualization. Keep
   source values separate from derived values and record filters, grouping,
   exclusions, and formulas.
4. Load `macsoft-chart-visualization` to choose the chart and encodings. Load
   `kpi-dashboard-design` for a multi-KPI or executive dashboard, and load
   `data-storytelling` when the user asks for findings or recommendations.
5. Load `web-design-engineer` for layout and HTML implementation. Read the
   references below only when their topic is needed.
6. Produce one complete HTML document. It must start with `<!doctype html>` and
   end with `</html>`. Put the verified data, chart configuration, labels,
   units, and a concise source/method note in that document.
7. Before responding, check that every displayed number can be traced to the
   returned data or to a stated calculation. Explain unsupported fields and
   missing data instead of filling gaps.

## Routing

- Always: this skill, chart visualization, and web design for an HTML result.
- AutoCount source: `macsoft-autocount:autocount-operations`.
- Multiple headline metrics: KPI dashboard design.
- Narrative insights or recommendations: data storytelling.
- Read `references/skill-routing.md` for the complete decision table.

## Implementation boundary

The current deliverable is HTML text only. Do not claim that an artifact was
saved, an ID was created, or a Preview was opened. Do not assume a CDN, local
ECharts file, network access, artifact endpoint, or client chart renderer.
Follow `references/html-runtime.md` and
`references/echarts-implementation.md`. If the approved ECharts runtime is not
available, return a truthful semantic HTML/CSS fallback rather than inventing a
dependency path.

## Data safety

Never manufacture rows, totals, dates, targets, currencies, or conclusions.
Counts, amounts, orders, invoices, and payments remain distinct measures.
Missing is not zero. Cancelled or excluded records must be visible in the
method note. Never expose credentials, tokens, internal file paths, or raw
connector responses that are not needed for the visualization.
