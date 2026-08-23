import requests
from decimal import Decimal, InvalidOperation
from urllib.parse import quote


def get_shopify_product(store_url, handle):
    """
    Get public Shopify product information using the product handle. For WCP, this is the SKU (E.g. "wcp-0063").

    Returns:
        dict containing all of the Shopify product information
    """

    store_url = store_url.rstrip("/")
    url = f"{store_url}/products/{handle}.js"

    response = requests.get(
        url,
        headers={
            "User-Agent": "Mozilla/5.0"
        },
        timeout=10
    )

    response.raise_for_status()
    
    return response.json()


def filter_shopify_product(product, quantity, store_url):
    """
    Return the product fields needed by the Slack CSV workflow.

    Returns:
        dict containing the title, quantity, human-readable link, and price.
    """
    handle = product.get("handle", "")
    variants = product.get("variants") or []
    price = product.get("price")
    if price is None and variants:
        price = variants[0].get("price")

    try:
        formatted_price = f"${Decimal(str(price or 0)):,.2f}"
    except (InvalidOperation, ValueError):
        formatted_price = f"${price}" if price else "$0.00"

    return {
        "Title": product.get("title"),
        "Quantity": quantity,
        "Link": f"{store_url.rstrip('/')}/products/{quote(handle, safe='')}" if handle else None,
        "Price": formatted_price,
    }
