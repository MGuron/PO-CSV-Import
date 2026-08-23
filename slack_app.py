import csv
import io
import os

import requests
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk.errors import SlackApiError
from slack_sdk.http_retry.builtin_handlers import ConnectionErrorRetryHandler
from slack_sdk.web import WebClient

from importWCPData import filter_shopify_product, get_shopify_product


STORE_URL = os.environ["SHOPIFY_STORE_URL"]


def products_from_csv(csv_text):
    """Fetch and format Shopify products from a two-column CSV."""
    rows = list(csv.reader(io.StringIO(csv_text)))
    if not rows:
        raise ValueError("The CSV file is empty.")

    if [column.strip().lower() for column in rows[0]] == ["handle", "quantity"]:
        rows = rows[1:]

    results = []
    for row_number, row in enumerate(rows, start=1):
        if not row or not any(cell.strip() for cell in row):
            continue
        if len(row) != 2:
            raise ValueError(f"Row {row_number} must contain exactly two columns.")

        handle, quantity_text = (cell.strip() for cell in row)
        if not handle:
            raise ValueError(f"Row {row_number} has no product handle.")
        try:
            quantity = int(quantity_text)
        except ValueError as error:
            raise ValueError(f"Row {row_number} quantity must be a whole number.") from error
        if quantity < 1:
            raise ValueError(f"Row {row_number} quantity must be at least 1.")

        product = get_shopify_product(STORE_URL, handle)
        results.append(filter_shopify_product(product, quantity, STORE_URL))

    if not results:
        raise ValueError("The CSV contains no product rows.")
    return results


def download_slack_file(file_info):
    """Download a private Slack file using the bot token."""
    response = requests.get(
        file_info["url_private_download"],
        headers={"Authorization": f"Bearer {os.environ['SLACK_BOT_TOKEN']}"},
        timeout=30,
    )
    response.raise_for_status()
    return response.text


def process_file(file_id, channel_id, client):
    file_info = client.files_info(file=file_id)["file"]
    filename = file_info.get("name", "")
    if not filename.lower().endswith(".csv"):
        raise ValueError("Please select a CSV file.")

    results = products_from_csv(download_slack_file(file_info))
    lines = [
        f"<{result['Link']}|{result['Title']}> - {result['Quantity']} x {result['Price']}"
        for result in results
    ]
    client.chat_postMessage(channel=channel_id, text="\n".join(lines))


def extract_file_id(view_state):
    """Support Slack's file input state shape while keeping validation explicit."""
    file_value = view_state["csv_file"]["upload"]
    file_ids = file_value.get("files", [])
    if not file_ids:
        raise ValueError("Please select a CSV file.")
    file_id = file_ids[0]
    if isinstance(file_id, dict):
        file_id = file_id.get("id")
    if not file_id:
        raise ValueError("Slack did not return a usable file ID.")
    return file_id


def open_upload_form(ack, body, client):
    ack()
    client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "shopify_csv_upload",
            "title": {"type": "plain_text", "text": "Import CSV"},
            "submit": {"type": "plain_text", "text": "Import"},
            "close": {"type": "plain_text", "text": "Cancel"},
            "blocks": [
                {
                    "type": "input",
                    "block_id": "csv_file",
                    "label": {"type": "plain_text", "text": "CSV file"},
                    "element": {
                        "type": "file_input",
                        "action_id": "upload",
                        "filetypes": ["csv"],
                        "max_files": 1,
                    },
                },
                {
                    "type": "input",
                    "block_id": "destination",
                    "label": {"type": "plain_text", "text": "Post results in"},
                    "element": {
                        "type": "conversations_select",
                        "action_id": "channel",
                        "filter": {"include": ["public"]},
                    },
                },
            ],
        },
    )


def handle_upload_submission(ack, body, view, client):
    ack()
    try:
        state = view["state"]["values"]
        file_id = extract_file_id(state)
        channel_id = state["destination"]["channel"]["selected_conversation"]
        process_file(file_id, channel_id, client)
    except SlackApiError as error:
        if error.response.get("error") == "file_not_found":
            message = (
                "Slack could not access that upload. Reinstall the app after granting "
                "files:read, confirm the bot is in the destination channel, and try again."
            )
        else:
            message = f"Slack returned an error: {error.response.get('error', error)}"
        client.chat_postMessage(channel=body["user"]["id"], text=message)
    except (KeyError, requests.RequestException, ValueError) as error:
        client.chat_postMessage(
            channel=body["user"]["id"],
            text=f"I couldn't process that CSV: {error}",
        )


def create_app():
    client = WebClient(
        token=os.environ["SLACK_BOT_TOKEN"],
        retry_handlers=[ConnectionErrorRetryHandler(max_retry_count=3)],
    )
    app = App(
        client=client,
        signing_secret=os.environ["SLACK_SIGNING_SECRET"],
    )
    app.shortcut("upload_shopify_csv")(open_upload_form)
    app.view("shopify_csv_upload")(handle_upload_submission)
    return app


if __name__ == "__main__":
    SocketModeHandler(create_app(), os.environ["SLACK_APP_TOKEN"]).start()