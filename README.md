# Shopify CSV Slack app

This Slack app provides a form-based workflow for uploading a two-column CSV and looking up each Shopify product using its handle.

The CSV may omit headers:

```csv
handle,quantity
wcp-0063,2
wcp-0100,1
```

## Run

1. Create or update the Slack app from `manifest.yaml`, enable Socket Mode, and install it in the target workspace.
2. Confirm the `files:read`, `chat:write`, and `channels:read` bot scopes, then create an app-level token with `connections:write`.
3. Install dependencies with `python -m pip install -r requirements.txt`.
4. Set the variables in `.env.example` in your shell. The app does not load `.env` files automatically.
5. Start it with `python slack_app.py`.

Use the **Import Shopify CSV** global shortcut in Slack. Select the `.csv` file and the destination channel in the form. The bot replies there with each product title, quantity, clickable product link, and price in dollars.