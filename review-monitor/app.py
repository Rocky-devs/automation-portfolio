from flask import Flask, jsonify
import requests
import os

app = Flask(__name__)

WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "https://hook.us2.make.com/snlh4r668p84gyz0xoa1b4mmh5hvedue")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
SHEET_NAME = "Review Monitor"

RESTAURANTS = [
    {"name": "Shake Shack Madison Square Park", "place_id": "ChIJz1idlLxYwokRwl1Twi2KrIQ"},
]

def get_reviews(place_id):
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        "place_id": place_id,
        "fields": "name,reviews",
        "key": GOOGLE_API_KEY
    }
    response = requests.get(url, params=params)
    return response.json().get("result", {}).get("reviews", [])

def send_to_webhook(restaurant_name, review):
    payload = {
        "restaurant": restaurant_name,
        "reviewer": review["author_name"],
        "rating": review["rating"],
        "review": review["text"].replace("\n", " "),
    }
    requests.post(WEBHOOK_URL, json=payload)

@app.route("/run", methods=["POST"])
def run():
    results = []

    for restaurant in RESTAURANTS:
        reviews = get_reviews(restaurant["place_id"])
        print(f"{restaurant['name']}: {len(reviews)} reviews")

        for review in reviews:
            send_to_webhook(restaurant["name"], review)

        results.append({
            "restaurant": restaurant["name"],
            "new_reviews": len(reviews)
        })

    return jsonify({"status": "ok", "results": results})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)