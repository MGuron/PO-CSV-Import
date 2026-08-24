# FRCBOM CSV to PO Sheet Slack app

This Slack app provides allows users to upload CSVs generated from FRCBOM into the PO Spreadsheet. This keeps all purchases tracked in one place, while allowing us to use quick-ordering features and easily move data between systems


```csv
SKU,QTY
wcp-0063,2
wcp-0100,1
```

## Deploy to Vercel

1. Create or update the Slack app from `manifest.yaml` and install it in the target workspace.
2. Confirm the `files:read`, `chat:write`, `channels:read`, `commands`, and `users:read` bot scopes.
3. Install dependencies with `python -m pip install -r requirements.txt`.
4. Deploy the repository with Vercel. Vercel automatically uses [api/index.py](api/index.py) as the Python function entrypoint.
5. In Slack, set the Interactivity Request URL to `https://YOUR-VERCEL-DOMAIN/api/index`.
6. Add `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET`, `SHOPIFY_STORE_URL`, `GOOGLE_SERVICE_ACCOUNT_JSON`, `GOOGLE_SHEET_ID`, and `GOOGLE_WORKSHEET_NAME` as Vercel environment variables. The 
7. Share the Google Sheet with the service account email from `GOOGLE_SERVICE_ACCOUNT_JSON` as an Editor.

Because the app creates a new context with file upload, you need to deploy the application for a persistent lifetime. Running the app locally in your python development environment will not work.

Use the **Import Order CSV**  shortcut in the #purchasing channel Slack and select the `.csv` file of interest. The app appends the product title, quantity, clickable product link, and price in dollars to the configured Google sheet.