import os
import math
import pandas as pd

try:
    from groq import Groq
    _GROQ_AVAILABLE = True
except ImportError:
    _GROQ_AVAILABLE = False


HOTEL_FILE = "hotel.xlsx"

# Member 2's budget planner used "Budget / Backpacker", "Standard", "Luxury"
# So, I made the hotel dataset using 3 tier/types of hotel: "Budget/Backpacker", "Standard", "Luxury"
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


# ----------------------------------------------------------------------
# Composite recommendation score — the "brain" of the recommender.
# Combines rating, star class, review volume, and budget fit into one
# transparent number so the system genuinely ranks/selects hotels
# instead of sorting on a single field.
# ----------------------------------------------------------------------

SCORE_WEIGHTS = {
    "rating": 0.35,
    "star": 0.15,
    "reviews": 0.15,
    "budget_fit": 0.35,
}

# Reviews above this count are treated as "maximally popular" (score caps at 1.0)
REVIEW_NORMALIZATION_CAP = 30000


def _hotel_score(rating_num: float, star_hotel: int, review_count: int,
                  est_stay_cost: float, per_city_budget: float) -> float:
    """
    Returns a 0-100 composite recommendation score.

    - rating: hotel's own rating out of 5, normalized to 0-1
    - star: official star class out of 5, normalized to 0-1
    - reviews: review volume, normalized against REVIEW_NORMALIZATION_CAP
    - budget_fit: per_city_budget / est_stay_cost, capped at 1.0 — a hotel
      exactly at budget scores 1.0; a hotel at 2x budget scores 0.5; a
      hotel well under budget still scores a full 1.0 (we don't reward
      going *unnecessarily* cheap beyond the budget, only penalize going over)
    """
    rating_score = min(max(rating_num, 0) / 5.0, 1.0)
    star_score = min(max(star_hotel, 0) / 5.0, 1.0)
    review_score = min(max(review_count, 0) / REVIEW_NORMALIZATION_CAP, 1.0)

    if per_city_budget > 0 and est_stay_cost > 0:
        budget_fit_score = min(per_city_budget / est_stay_cost, 1.0)
    else:
        budget_fit_score = 0.0

    score = (
        SCORE_WEIGHTS["rating"] * rating_score
        + SCORE_WEIGHTS["star"] * star_score
        + SCORE_WEIGHTS["reviews"] * review_score
        + SCORE_WEIGHTS["budget_fit"] * budget_fit_score
    )
    return round(score * 100, 1)


def recommend_hotels(
    df: pd.DataFrame,
    destinations: list,
    travel_style: str,
    duration_days: int,
    travelers: int,
    hotel_budget_pkr: float,
    top_n: int = 3,
) -> dict:
    """
    Recommend up to `top_n` hotels per destination city, prioritizing
    budget fit over everything else (per Member 3's brief: "recommend
    budget-friendly accommodation options").

    Splits `hotel_budget_pkr` evenly across the number of destinations,
    then for each city tries, in order (cost always priced for the number
    of ROOMS actually needed to fit `travelers`, per each hotel's own
    Max_Guests capacity — e.g. 10 travelers at a 4-guest-max hotel needs
    3 rooms, not 1):
      1. The requested tier (Hotel_Type), hotels that fit the per-city
         budget slice, ranked by a composite recommendation SCORE (rating,
         star class, review volume, and budget fit combined — see
         `_hotel_score`), not a single field.
      2. If none fit, step DOWN through cheaper tiers
         (Budget/Backpacker -> Standard -> Luxury, only tiers cheaper
         than requested) looking for hotels that fit the budget.
      3. If nothing in any tier fits the budget, fall back to the
         requested tier's hotels still ranked by the same composite
         score — which naturally favors the cheapest, best-reviewed
         option even when nothing is fully affordable, rather than
         showing the priciest highly-rated one.
      4. If the requested tier doesn't exist in that city at all, fall
         back to the whole city's inventory, same scoring.

    Every result carries `within_budget` and `tier_used` so the UI can
    be transparent about which of the above paths was taken, and every
    hotel carries a `recommendation_score` (0-100) so the UI can show
    *why* it was picked, not just that it was.

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

    # Tiers cheaper than (or equal to) the requested one, cheapest first,
    # used for step-down fallback when the requested tier is unaffordable.
    req_idx = TIER_FALLBACK_ORDER.index(requested_tier) if requested_tier in TIER_FALLBACK_ORDER else 1

    results = {}

    for city in destinations:
        city_df = df[df["City"] == city].copy()

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

        city_df["Rooms_Needed"] = city_df["Max_Guests"].apply(
            lambda cap: math.ceil(travelers / cap) if cap > 0 else travelers
        )
        city_df["Est_Stay_Cost"] = (
            city_df["Estimated Price/Day"] * duration_days * city_df["Rooms_Needed"]
        )
        city_df["Recommendation_Score"] = city_df.apply(
            lambda r: _hotel_score(
                r["Rating_Num"], r["Star_Hotel"], r["Review_Count"],
                r["Est_Stay_Cost"], per_city_budget,
            ),
            axis=1,
        )

        tier_used = requested_tier
        within_budget = False
        note = None
        pool = None

        # Try tiers from requested down to cheapest, stop at first with an affordable match
        search_order = TIER_FALLBACK_ORDER[: req_idx + 1][::-1]  # requested tier first, then cheaper ones
        for tier in search_order:
            tier_df = city_df[city_df["Hotel_Type"] == tier]
            if tier_df.empty:
                continue
            affordable = tier_df[tier_df["Est_Stay_Cost"] <= per_city_budget]
            if not affordable.empty:
                pool = affordable.sort_values(by="Recommendation_Score", ascending=False)
                tier_used = tier
                within_budget = True
                if tier != requested_tier:
                    note = (
                        f"No '{requested_tier}' hotel in {city} fit the budget; "
                        f"showing '{tier}' options that do instead."
                    )
                break

        # Step 3 / 4: nothing affordable at or below the requested tier.
        if pool is None:
            tier_df = city_df[city_df["Hotel_Type"] == requested_tier]
            if tier_df.empty:
                tier_df = city_df  # tier doesn't exist in this city at all
                tier_used = "Mixed (requested tier unavailable here)"
            else:
                tier_used = requested_tier
            pool = tier_df.sort_values(by="Recommendation_Score", ascending=False)
            within_budget = False
            note = (
                f"Even the cheapest '{tier_used}' option in {city} exceeds the "
                f"PKR {per_city_budget:,.0f} hotel budget for this destination — "
                "showing the best-scoring options available."
            )

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
                "rooms_needed": int(row["Rooms_Needed"]),
                "estimated_stay_cost_pkr": float(row["Est_Stay_Cost"]),
                "recommendation_score": float(row["Recommendation_Score"]),
                "review_count": int(row["Review_Count"]),
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
    rooms = hotel.get("rooms_needed", 1)
    room_note = f" across {rooms} rooms" if rooms > 1 else ""
    return (
        f"{hotel['hotel_name']} is a solid {hotel['hotel_type'].lower()} option in "
        f"{hotel['city']} for {travelers} traveler(s){room_note} — rated {hotel['rating']} and "
        f"priced at PKR {hotel['price_per_day_pkr']:,.0f}/day per room, which {fit} your "
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
    rooms_needed = hotel.get("rooms_needed", 1)

    prompt = (
        "Write ONE short, friendly sentence recommending this hotel to a tourist. "
        "Use ONLY the facts given below — do not invent a rating, price, review count, "
        "or any amenity not listed. If more than 1 room is needed, mention that "
        "naturally. Do not use markdown.\n\n"
        f"Hotel name: {hotel['hotel_name']}\n"
        f"City: {hotel['city']}\n"
        f"Tier: {hotel['hotel_type']}\n"
        f"Rating: {hotel['rating']}\n"
        f"Price per room per day: PKR {hotel['price_per_day_pkr']:,.0f}\n"
        f"Rooms needed for this group: {rooms_needed}\n"
        f"Estimated total stay cost (all rooms, all nights): PKR {hotel['estimated_stay_cost_pkr']:,.0f}\n"
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
