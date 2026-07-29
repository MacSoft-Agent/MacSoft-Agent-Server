# MacSoft AutoCount Charting

## Purpose

Create a chart payload from official AutoCount query results. The chart payload
is renderer-independent and is delivered to the Server as a structured
`chart_payload` event. The model chooses the chart type and field mapping; the
model may analyze the returned real query rows freely; the Server retains the
authoritative rows and validates the final payload.

## Non-negotiable workflow

1. Use `autocount_search_commands` when the official read/report command type is
   uncertain.
2. Fetch and follow the current command schema with
   `autocount_get_command_schema`.
3. Validate the read/report payload with `autocount_validate_command`.
4. Call `autocount_query_data` and retain its opaque `result_ref`.
5. Analyze the returned real rows and choose a chart type whose minimum
   encodings match the available fields.
6. Call `autocount_create_chart` with the `result_ref`, title, and
   chart-type-specific encodings.
7. Describe the chart briefly in the assistant text. Do not fabricate values
   or submit replacement rows; the Chart Tool uses the Server-owned result_ref.

Never use a write, edit, delete, or other mutating AutoCount command as the
source of a chart. Never generate frontend code, ECharts options, SQL, Python,
or browser automation for charting.

## Chart type minimum encodings

| Chart type | Required encodings | Optional encodings |
| --- | --- | --- |
| `line` | `x`, `y` | `series` |
| `area` | `x`, `y` | `series` |
| `bar` | `category`, `value` | `series` |
| `horizontal_bar` | `category`, `value` | `series` |
| `pie` | `category`, `value` | none |
| `donut` | `category`, `value` | none |
| `gauge` | `value`, `min`, `max` | `target` |
| `calendar_heatmap` | `date`, `value` | none |
| `scatter` | `x`, `y` | `series` |
| `table` | query `data.columns` and `data.rows` | none |

The encoding names above are not interchangeable. Every mapped field must
exist in the query result. Numeric encodings must use numeric columns; the
calendar date encoding must use a date/datetime column. The Server performs the
final validation and rejects incomplete or incompatible mappings.
