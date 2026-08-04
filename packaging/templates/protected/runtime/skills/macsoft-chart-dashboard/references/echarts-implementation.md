# ECharts implementation contract

Use ECharts option conventions when an approved runtime supplies ECharts. Do
not use Chart.js, D3, AntV APIs, remote image URLs, or CDN guesses.

## Minimum mappings

- `line`: ordered `x` field to the category axis and numeric `y` field to one
  series; optional `series` creates multiple series.
- `bar`: categorical `category` field to the category axis and numeric `value`
  field to the value axis; optional `series` creates grouped bars.
- `pie`: `category` becomes `name` and numeric `value` becomes `value`.
- `scatter`: numeric `x` and `y` fields become coordinate pairs.
- `table`: render declared `columns` and `rows` without changing values.

Use `tooltip`, a readable legend when there are multiple series, axis names
with units, and a responsive chart container. Avoid unnecessary animation,
3D effects, dual axes, and dense labels. Keep the original rows available for
the table or method note when the chart aggregates them.

Serialize verified data safely into the document; do not interpolate untrusted
text into executable JavaScript. If ECharts cannot be delivered by the
approved runtime, use an honest HTML/CSS fallback and explain that limitation.
