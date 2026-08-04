# HTML runtime contract

The current phase returns HTML text. It does not save artifacts or open a
Preview. Never invent `artifact_id`, preview URLs, file paths, or successful
rendering claims.

The document must be a complete standalone document:

```html
<!doctype html>
<html lang="en">
  <head>...</head>
  <body>...</body>
</html>
```

Use semantic HTML, responsive CSS, accessible labels, and a visible empty or
error state when data is unavailable. Do not assume a CDN, network access,
Content Security Policy, local library path, or client-side chart library. The
ECharts reference defines option shape and mapping only; dependency delivery
must be supplied by a future runtime contract.
