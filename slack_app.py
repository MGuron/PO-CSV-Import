import csv
from datetime import datetime
import io
import json
import os

import gspread
import requests
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk.errors import SlackApiError
from slack_sdk.http_retry.builtin_handlers import ConnectionErrorRetryHandler
from slack_sdk.web import WebClient

from importWCPData import filter_shopify_product, get_shopify_product


STORE_URL = os.environ["SHOPIFY_STORE_URL"]

#Fetch and format Shopify products from a two-column CSV. Currenty works for WCP only
def products_from_csv(csv_text):
    rows = list(csv.reader(io.StringIO(csv_text)))
    if not rows:
        raise ValueError("The CSV file is empty.")

    header = [column.strip().lower() for column in rows[0]]
    if header in (["handle", "quantity"], ["sku", "qty"]):
        rows = rows[1:]

    results = []
    for row_number, row in enumerate(rows, start=1):
        if not row or not any(cell.strip() for cell in row):
            continue
        if len(row) != 2:
            raise ValueError(f"Row {row_number} must contain exactly two columns.")

        handle, quantity_text = (cell.strip() for cell in row)
        handle = handle.lower()
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

#Download a private Slack file using the bot token.
def download_slack_file(file_info):
    response = requests.get(
        file_info["url_private_download"],
        headers={"Authorization": f"Bearer {os.environ['SLACK_BOT_TOKEN']}"},
        timeout=30,
    )
    response.raise_for_status()
    return response.text


def process_file(file_id, client, needed_by, requested_by):
    file_info = client.files_info(file=file_id)["file"]
    filename = file_info.get("name", "")
    if not filename.lower().endswith(".csv"):
        raise ValueError("Please select a CSV file.")

    results = products_from_csv(download_slack_file(file_info))
    for result in results:
        result["Needed By"] = needed_by
        result["Requested By"] = requested_by
    append_products_to_sheet(results)
    return results

#Append product results to the configured Google worksheet.
def append_products_to_sheet(results):
    credentials = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
    sheets_client = gspread.service_account_from_dict(credentials)
    spreadsheet = sheets_client.open_by_key(os.environ["GOOGLE_SHEET_ID"])
    worksheet = spreadsheet.worksheet(os.getenv("GOOGLE_WORKSHEET_NAME", "Sheet1"))

    header_rows = worksheet.get("1:1", pad_values=True)
    headers = header_rows[0] if header_rows else []
    if not headers:
        headers = ["Title", "Num", "Link", "Price", "Needed By", "Requested By"]
        worksheet.append_row(headers, value_input_option="USER_ENTERED")

    field_aliases = {
        "title": "Title",
        "item": "Title",
        "product": "Title",
        "product title": "Title",
        "num": "Num",
        "qty": "Num",
        "quantity": "Num",
        "link": "Link",
        "url": "Link",
        "product link": "Link",
        "price": "Price",
        "per": "Price",
        "needed by": "Needed By",
        "needed_by": "Needed By",
        "requested by": "Requested By",
        "requested_by": "Requested By",
    }
    fields_by_column = [
        field_aliases.get(header.strip().lower())
        for header in headers
    ]
    missing_fields = {
        field for field in ("Title", "Num", "Link", "Price", "Needed By", "Requested By")
        if field not in fields_by_column
    }
    if missing_fields:
        raise ValueError(
            "Google Sheet is missing columns: " + ", ".join(sorted(missing_fields))
        )

    field_columns = {
        field: column_number
        for column_number, field in enumerate(fields_by_column, start=1)
        if field
    }
    first_column = min(field_columns.values())
    last_column = max(field_columns.values())
    next_row = len(worksheet.get_all_values()) + 1
    final_row = next_row + len(results) - 1

    def column_letter(column_number):
        letters = ""
        while column_number:
            column_number, remainder = divmod(column_number - 1, 26)
            letters = chr(65 + remainder) + letters
        return letters

    worksheet.update(
        f"{column_letter(first_column)}{next_row}:{column_letter(last_column)}{final_row}",
        [
            [
                next(
                    (
                        result[field]
                        for column_number, field in enumerate(fields_by_column, start=1)
                        if column_number == target_column and field
                    ),
                    "",
                )
                for target_column in range(first_column, last_column + 1)
            ]
            for result in results
        ],
        value_input_option="USER_ENTERED",
    )

#Support Slack's file input state shape while keeping validation explicit.
def extract_file_id(view_state):
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

# Create slack upload form
def open_upload_form(ack, body, client):
    ack()
    client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "shopify_csv_upload",
            "title": {"type": "plain_text", "text": "Import Vendor CSV"},
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
                    "label": {"type": "plain_text", "text": "Post confirmation in"},
                    "element": {
                        "type": "conversations_select",
                        "action_id": "channel",
                        "default_to_current_conversation": True,
                        "response_url_enabled": True,
                        "filter": {"include": ["public"]},
                    },
                },
                {
                    "type": "input",
                    "block_id": "needed_by",
                    "label": {"type": "plain_text", "text": "Needed by"},
                    "element": {
                        "type": "datepicker",
                        "action_id": "date",
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
        needed_by = datetime.strptime(
            state["needed_by"]["date"]["selected_date"], "%Y-%m-%d"
        ).strftime("%m/%d/%Y")
        user_id = body["user"]["id"]
        user_info = client.users_info(user=user_id)["user"]
        requested_by = (
            user_info.get("profile", {}).get("display_name")
            or user_info.get("real_name")
            or user_id
        )
        results = process_file(file_id, client, needed_by, requested_by)
        channel_id = state["destination"]["channel"]["selected_conversation"]
        mention = os.getenv("SLACK_IMPORT_MENTION", "").strip()
        mention_prefix = f"{mention} " if mention else ""
        entries = "\n".join(
            f"> `{result['Title']}` | link: <{result['Link']}|open> | "
                f"Qty: `{result['Num']}` | Price: `${result['Price']}` | "
                f"Needed by: `{result['Needed By']}` | Requested by: `{result['Requested By']}`"
            for result in results
        )
        client.chat_postMessage(
            channel=channel_id,
            text=(
                f"{mention_prefix}"
                f"<@{body['user']['id']}> imported a CSV file into the PO Sheet.\n"
                f"*Imported entries:*\n{entries}"
            ),
        )
    except SlackApiError as error:
        if error.response.get("error") == "file_not_found":
            message = (
                "Slack could not access that upload. Reinstall the app after granting "
                "files:read, confirm the bot is in the destination channel, and try again."
            )
        else:
            message = f"Slack returned an error: {error.response.get('error', error)}"
        client.chat_postMessage(channel=body["user"]["id"], text=message)
    except (KeyError, requests.RequestException, ValueError, gspread.exceptions.GSpreadException) as error:
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
        process_before_response=True,
        token_verification_enabled=False,
    )
    app.shortcut("upload_shopify_csv")(open_upload_form)
    app.view("shopify_csv_upload")(handle_upload_submission)
    return app


if __name__ == "__main__":
    SocketModeHandler(create_app(), os.environ["SLACK_APP_TOKEN"]).start()