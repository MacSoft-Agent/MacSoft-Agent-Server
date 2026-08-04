# Data integrity

- Preserve source types, units, currency, date precision, and nulls.
- Define aggregation, grouping, filters, exclusions, and comparison windows.
- A derived value must show its formula and source fields.
- Missing data is not zero; an absent period is not evidence of no activity.
- Counts are not amounts. Orders are not completed sales unless the source and
  business rule establish that relationship.
- Do not infer a cause from a correlation or a date sequence.
- Show a short source and method note in the HTML so the reader can audit the
  displayed result.
- Do not place secrets, tokens, connector credentials, or unnecessary raw
  responses in the generated HTML.
