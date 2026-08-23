# Shopify CSV Slack app

This Slack app provides a form-based workflow for uploading a two-column CSV and looking up each Shopify product using its handle.

The CSV may omit headers:

```csv
handle,quantity
wcp-0063,2
wcp-0100,1
```

## Deploy to Vercel

1. Create or update the Slack app from `manifest.yaml` and install it in the target workspace.
2. Confirm the `files:read`, `chat:write`, `channels:read`, and `commands` bot scopes.
3. Install dependencies with `python -m pip install -r requirements.txt`.
4. Deploy the repository with Vercel. Vercel automatically uses [api/index.py](api/index.py) as the Python function entrypoint.
5. In Slack, set the Interactivity Request URL to `https://YOUR-VERCEL-DOMAIN/api/index`.
6. Add `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET`, and `SHOPIFY_STORE_URL` as Vercel environment variables.

For local development, set the variables in `.env.example` in your shell and run `python slack_app.py` with `SLACK_APP_TOKEN` for Socket Mode.

Use the **Import Shopify CSV** global shortcut in Slack. Select the `.csv` file and the destination channel in the form. The bot replies there with each product title, quantity, clickable product link, and price in dollars.