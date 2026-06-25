# NL2SQL Mini Dataset

This folder simulates a tiny local database that already exists in the workspace.

Use it as context for the NL2SQL test. Do not paste these rows into `novice-input.md` or `customized-input.md`.

Files:

- `manifest.json`: table metadata, CSV file names and relationships.
- `sample_dataset.json`: all sample rows grouped by table.
- `*.csv`: one CSV file per table.

The data intentionally includes edge cases:

- cancelled and failed orders
- internal and test customers
- gift card products
- multiple captured payments for one order
- order-level refunds
- Q2 boundary timestamps
- multiple market timezones
- FX dates by local business date
