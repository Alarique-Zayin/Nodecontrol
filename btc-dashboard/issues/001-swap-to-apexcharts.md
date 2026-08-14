Title: Swap Chart.js for ApexCharts for finance-style visuals

Description
-----------
Replace Chart.js with ApexCharts to achieve smoother, finance-style charts (candlesticks, area gradients, and performant sparklines). ApexCharts provides better default styling and interactions suited for financial UIs.

Acceptance criteria
- Replace Chart.js CDN include with ApexCharts CDN in `templates/index.html`.
- Update `static/js/dashboard.js` to initialize ApexCharts sparklines with the same series API.
- Ensure sparklines render and update in real time via the existing WebSocket poller.
- Visual parity: area fill with subtle gradient and thin line similar to Google Finance sparklines.

Estimate: 2-4 hours
