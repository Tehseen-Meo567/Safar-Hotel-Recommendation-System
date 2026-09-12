# 🏨 SAFAR — Hotel Recommendation Module 
### By Member 3: Tehseen Meo

Part of **SAFAR: Pakistan Travel Agent**.

Recommends hotels per destination city, matched to the tourist's travel style and remaining budget — not just filtered, but **ranked** using a transparent scoring system. Plugs directly into the shared Streamlit app built by Member 2 (Budget Planner).

---

## ✨ What it does

- Recommends hotels **per city** in the tourist's itinerary
- Matches hotels to the **actual remaining hotel budget** (not just travel-style tier)
- Prices for the **real number of rooms** a group needs, based on each hotel's guest capacity
- Automatically **steps down to a cheaper tier** if the requested one doesn't fit the budget
- Shows price, rating, reviews, amenities, and location — in **PKR and USD**
- Optionally generates a **natural-language explanation** for each pick using Groq (LLM)
- Exports results as structured JSON for other modules to consume

---

## 🧠 How recommendations are decided

Each hotel is scored **0–100** on four weighted factors — not sorted by a single field:

| Factor | Weight | What it measures |
|---|---|---|
| Rating | 35% | Guest rating out of 5 |
| Budget fit | 35% | How well total stay cost fits the city's budget slice |
| Star class | 15% | Official star rating out of 5 |
| Review volume | 15% | Number of reviews (popularity signal, capped at 30,000) |

**Budget fit is continuous, not pass/fail** — a hotel at 2× the budget still scores higher than one at 4×, so even fallback results favor the cheapest, best-reviewed option.

### The formulas, step by step

**1. Budget is split evenly across chosen cities:**
```
per_city_budget = total_hotel_budget_pkr / number_of_destinations
```

**2. Rooms needed, based on group size vs. each hotel's own capacity:**
```
rooms_needed = ceil(travelers / hotel's Max_Guests)
```

**3. Total stay cost — this is the "duration × budget"-style calculation:**
```
estimated_stay_cost = price_per_room_per_day × duration_days × rooms_needed
```

**4. Budget fit score (capped at a perfect 1.0, never rewarded beyond that):**
```
budget_fit_score = min(per_city_budget / estimated_stay_cost, 1.0)
```

**5. Final composite score (0–100), combining everything above:**
```
score = 100 × ( 0.35 × (rating / 5)
              + 0.35 × budget_fit_score
              + 0.15 × (star_class / 5)
              + 0.15 × min(review_count / 30000, 1.0) )
```

**Decision order per city:**
1. Try the requested tier (Budget/Standard/Luxury) → rank affordable hotels by score
2. If nothing affordable → step down to a cheaper tier
3. If still nothing affordable anywhere → show the best-scoring options anyway, clearly labeled "over budget"

---

## 🤖 Groq AI layer (optional)

A toggle lets the app generate a one-sentence, human-friendly explanation for each hotel pick using **Groq** (`llama-3.3-70b-versatile`).

- **Off by default** — not required for the system to work
- The LLM only **phrases** facts already computed in Python (rating, price, budget fit) — it's told not to invent numbers
- Falls back to a deterministic template sentence if no `GROQ_API_KEY` is set, the `groq` package is missing, or the API call fails — **the app never breaks because of this feature**

---

## 📁 Project structure

```
├── app.py              # Streamlit UI (Hotel Recommendations section)
├── hotel_utils.py       # All recommendation logic — no UI code
├── hotel.xlsx           # Hotel dataset — 91 hotels across 9 cities, 3 tiers
└── requirements.txt
```

`app.py` reads trip inputs (destinations, travel style, duration, travelers, hotel budget) that are already collected by Member 2's Budget Planner section — this module adds no duplicate input fields.

**Cities covered:** Islamabad, Lahore, Peshawar, Hunza Valley, Gilgit, Swat, Skardu, Murree, Karachi.

---

## 🚀 Running locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

### Optional: enable the Groq AI explanations

```bash
export GROQ_API_KEY="your_key_here"   # macOS/Linux
set GROQ_API_KEY=your_key_here        # Windows
```

On **Streamlit Community Cloud**, add `GROQ_API_KEY` under your app's **Settings → Secrets** instead.

---

## 🧪 Testing

- Verified with automated syntax checks and live `streamlit run` smoke tests (HTTP 200, no exceptions)
- Targeted scenario tests: tier step-down when unaffordable, multi-room pricing for large groups, "nothing fits" fallback
- A self-contained **Google Colab notebook** is available for quick testing without deploying — installs dependencies, rebuilds `hotel.xlsx` from an embedded copy, and launches the app via a public tunnel link

---

## 📤 Output

Two JSON files are generated, kept separate so nothing already using the original schema breaks:

| File | Contains |
|---|---|
| `budget_data.json` | Member 2's original schema — unchanged |
| `hotel-recommendation.json` | Everything above **plus** `hotel_recommendations` (per-city picks, scores, tiers, room counts) and `total_estimated_hotel_cost_pkr` |

---

## ⚠️ Known limitations

- Large groups are priced as multiple rooms **at one hotel**, not split across properties
- No minimum room-capacity filter — a 1-guest hotel can technically show "10 rooms needed" for a big group
- With a fixed demo dataset, some low-budget scenarios genuinely can't be made affordable — this is shown transparently rather than hidden

---

## 🔗 Related

- Full technical documentation: `Hotel_Recommendation_System_Documentation.docx`
- Team responsibility: Member 3 — Hotel & Accommodation Recommendation System
