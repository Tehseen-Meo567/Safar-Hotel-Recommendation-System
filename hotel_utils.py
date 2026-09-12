"""
hotel_utils.py
--------------
Member 3 module: Hotel & Accommodation Recommendation.

Responsibilities covered here:
- Load and clean the hotel dataset (hotel.xlsx)
- Match hotels to the tourist's destinations + travel style
- Fit hotel picks within the per-city slice of the overall hotel budget
- Return a clean, JSON-serializable structure other members (esp. Member 4 /
  Member 1) can consume
- Optionally generate a natural-language explanation of each pick via Groq
  (the LLM only phrases sentences from numbers we already computed — it
  never invents a price, rating, or review count itself)
"""

import os
import pandas as pd

try:
    from groq import Groq
    _GROQ_AVAILABLE = True
except ImportError:
    _GROQ_AVAILABLE = False


HOTEL_FILE = "hotel.xlsx"

# Member 2's budget planner uses "Budget / Backpacker", "Standard", "Luxury"
# The hotel dataset uses "Budget/Backpacker", "Standard", "Luxury"
TIER_MAP = {
    "Budget / Backpacker": "Budget/Backpacker",
    "Standard": "Standard",
    "Luxury": "Luxury",
}

TIER_FALLBACK_ORDER = ["Budget/Backpacker", "Standard", "Luxury"]


def load_hotels(path: str = HOTEL_FILE) -> pd.DataFrame:
    """Load and lightly clean the hotel dataset."""
    df = pd.read_excel(path)

    # Numeric rating for sorting (dataset stores ratings as text like "4.5/5").
    # Take the part before the "/" rather than assuming a fixed "/5" suffix,
    # since a few rows in the source sheet have typos like "4.9/6".
    df["Rating_Num"] = (
        df["Rating"].astype(str).str.split("/").str[0].astype(float)
    )

    # Amenities as a list for cleaner display
    df["Amenities_List"] = (
        df["Amenities"]
        .fillna("")
        .apply(lambda x: [a.strip() for a in str(x).split(",") if a.strip()])
    )

    return df


def _tier_for_style(travel_style: str) -> str:
    return TIER_MAP.get(travel_style, travel_style)


def recommend_hotels(
    df: pd.DataFrame,
    destinations: list,
    travel_style: str,
    duration_days: int,
    hotel_budget_pkr: float,
    top_n: int = 3,
) -> dict:
    """
    Recommend up to `top_n` hotels per destination city.

    Splits `hotel_budget_pkr` evenly across the number of destinations, then
    for each city:
      1. Filters to the requested tier (Hotel_Type).
      2. If that tier isn't available in the city, falls back to whatever
         tier IS available (flagged in the result).
      3. Prefers hotels whose full-stay cost fits the city's budget slice;
         if none fit, still returns the closest options (flagged
         `within_budget: False`) so the UI can warn instead of showing
         nothing.
      4. Ranks by rating (desc), then price (asc).

    Returns a dict keyed by city name, e.g.:
    {
        "Islamabad": {
            "tier_requested": "Standard",
            "tier_used": "Standard",
            "per_city_budget_pkr": 52500.0,
            "within_budget": True,
            "hotels": [ {...row...}, {...row...} ]
        },
        ...
    }
    """
    requested_tier = _tier_for_style(travel_style)
    n_cities = max(len(destinations), 1)
    per_city_budget = hotel_budget_pkr / n_cities

    display_cols = [
        "Hotel_id", "Region", "City", "Travel_Theme", "Hotel_Name",
        "Hotel_Type", "Rating", "Star_Hotel", "Max_Guests",
        "Estimated Price/Day", "Amenities_List",
    ]

    results = {}

    for city in destinations:
        city_df = df[df["City"] == city]

        if city_df.empty:
            results[city] = {
                "tier_requested": requested_tier,
                "tier_used": None,
                "per_city_budget_pkr": per_city_budget,
                "within_budget": False,
                "hotels": [],
                "note": "No hotels in the dataset for this destination yet.",
            }
            continue

        tier_df = city_df[city_df["Hotel_Type"] == requested_tier]
        tier_used = requested_tier
        note = None

        if tier_df.empty:
            tier_df = city_df
            tier_used = "Mixed (requested tier unavailable here)"
            note = (
                f"No '{requested_tier}' hotels found in {city}; "
                "showing best available options across tiers instead."
            )

        tier_df = tier_df.copy()
        tier_df["Est_Stay_Cost"] = tier_df["Estimated Price/Day"] * duration_days

        affordable = tier_df[tier_df["Est_Stay_Cost"] <= per_city_budget]
        within_budget = not affordable.empty
        pool = affordable if within_budget else tier_df

        pool = pool.sort_values(by=["Rating_Num", "Estimated Price/Day"], ascending=[False, True])
        top = pool.head(top_n)

        hotels_out = []
        for _, row in top.iterrows():
            hotels_out.append({
                "hotel_id": row["Hotel_id"],
                "hotel_name": row["Hotel_Name"],
                "region": row["Region"],
                "city": row["City"],
                "travel_theme": row["Travel_Theme"],
                "hotel_type": row["Hotel_Type"],
                "rating": row["Rating"],
                "star_hotel": int(row["Star_Hotel"]),
                "max_guests": int(row["Max_Guests"]),
                "price_per_day_pkr": float(row["Estimated Price/Day"]),
                "estimated_stay_cost_pkr": float(row["Est_Stay_Cost"]),
                "amenities": row["Amenities_List"],
            })

        results[city] = {
            "tier_requested": requested_tier,
            "tier_used": tier_used,
            "per_city_budget_pkr": per_city_budget,
            "within_budget": within_budget,
            "hotels": hotels_out,
        }
        if note:
            results[city]["note"] = note

    return results


def total_estimated_hotel_cost(recommendations: dict) -> float:
    """Sum of the top (first-ranked) hotel pick per city."""
    total = 0.0
    for city_data in recommendations.values():
        if city_data["hotels"]:
            total += city_data["hotels"][0]["estimated_stay_cost_pkr"]
    return total


# ----------------------------------------------------------------------
# AI-generated explanation (Groq) — phrasing only, never a data source
# ----------------------------------------------------------------------

_groq_client = None


def _get_groq_client():
    """Lazily create a single Groq client, reused across calls."""
    global _groq_client
    if not _GROQ_AVAILABLE:
        return None
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return None
    if _groq_client is None:
        _groq_client = Groq(api_key=api_key)
    return _groq_client


def _fallback_explanation(hotel: dict, travelers: int, per_city_budget: float) -> str:
    """Deterministic template used when Groq is unavailable or errors out.
    Keeps the app fully functional without an API key (e.g. for grading)."""
    fit = "fits comfortably within" if hotel["estimated_stay_cost_pkr"] <= per_city_budget else "runs a bit above"
    return (
        f"{hotel['hotel_name']} is a solid {hotel['hotel_type'].lower()} option in "
        f"{hotel['city']} for {travelers} traveler(s) — rated {hotel['rating']} and "
        f"priced at PKR {hotel['price_per_day_pkr']:,.0f}/day, which {fit} your "
        f"per-city hotel budget of PKR {per_city_budget:,.0f}."
    )


def generate_ai_explanation(
    hotel: dict,
    travelers: int,
    per_city_budget: float,
    model: str = "llama-3.3-70b-versatile",
) -> str:
    """
    Return a one-sentence, human-friendly explanation of why this hotel is
    a good pick, generated by Groq. The prompt supplies only facts already
    computed in `hotel` (name, rating, price, amenities, etc.) and instructs
    the model to phrase them, not invent additional facts.

    Falls back to a deterministic template if GROQ_API_KEY isn't set, the
    `groq` package isn't installed, or the API call fails for any reason —
    so the app never breaks because of a missing key or a network hiccup.
    """
    client = _get_groq_client()
    if client is None:
        return _fallback_explanation(hotel, travelers, per_city_budget)

    amenities_str = ", ".join(hotel["amenities"][:5]) if hotel["amenities"] else "no amenities listed"

    prompt = (
        "Write ONE short, friendly sentence recommending this hotel to a tourist. "
        "Use ONLY the facts given below — do not invent a rating, price, review count, "
        "or any amenity not listed. Do not use markdown.\n\n"
        f"Hotel name: {hotel['hotel_name']}\n"
        f"City: {hotel['city']}\n"
        f"Tier: {hotel['hotel_type']}\n"
        f"Rating: {hotel['rating']}\n"
        f"Price per day: PKR {hotel['price_per_day_pkr']:,.0f}\n"
        f"Estimated stay cost: PKR {hotel['estimated_stay_cost_pkr']:,.0f}\n"
        f"Traveler's per-city hotel budget: PKR {per_city_budget:,.0f}\n"
        f"Travelers: {travelers}\n"
        f"Amenities: {amenities_str}\n"
    )

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a concise, factual travel assistant."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
            max_tokens=80,
        )
        text = response.choices[0].message.content.strip()
        return text if text else _fallback_explanation(hotel, travelers, per_city_budget)
    except Exception:
        return _fallback_explanation(hotel, travelers, per_city_budget)
