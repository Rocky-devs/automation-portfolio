"""
Rainforest API wrapper.
Docs: https://www.rainforestapi.com/docs

Free tier: 100 requests/month.
Portfolio recommendation: monitor ≤ 10 ASINs, run every 3 days = ~100 calls/month.
"""
import os
import requests

BASE_URL = "https://api.rainforestapi.com/request"


def get_product_data(asin: str, domain: str = "amazon.com") -> dict:
    """
    Fetch product snapshot for one ASIN.
    Returns normalized dict with: asin, title, price, rating, reviews_count, bsr, brand.
    Raises on HTTP error or missing product.
    """
    params = {
        "api_key": os.environ["RAINFOREST_API_KEY"],
        "type": "product",
        "asin": asin,
        "amazon_domain": domain,
    }

    resp = requests.get(BASE_URL, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    if "product" not in data:
        raise ValueError(f"No product data returned for ASIN {asin}: {data}")

    product = data["product"]

    # Price: prefer buybox winner, fall back to top-level price field
    price = None
    buybox = product.get("buybox_winner", {})
    if buybox.get("price", {}).get("value"):
        price = buybox["price"]["value"]
    elif product.get("price", {}).get("value"):
        price = product["price"]["value"]

    # BSR: first entry in bestsellers_rank list
    bsr = None
    bsr_list = product.get("bestsellers_rank", [])
    if bsr_list:
        bsr = bsr_list[0].get("rank")

    return {
        "asin": asin,
        "title": product.get("title", ""),
        "brand": product.get("brand", ""),
        "price": price,
        "rating": product.get("rating"),
        "reviews_count": product.get("ratings_total"),
        "bsr": bsr,
    }
