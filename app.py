import streamlit as st
import pandas as pd
import plotly.express as px
import json
from hotel_utils import (
    load_hotels,
    recommend_hotels,
    total_estimated_hotel_cost,
    generate_ai_explanation,
)

# Page Setup & Configuration
st.set_page_config(
    page_title="SAFAR - AI Travel Companion for Pakistan",
    page_icon="🇵🇰",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for a clean modern UI
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1b4332;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #555;
        margin-bottom: 1.5rem;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.5rem !important;
        font-weight: 700 !important;
        color: #2d6a4f !important;
    }
    .card-box {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 1.2rem;
        border: 1px solid #e9ecef;
    }
    .tier-badge {
        display: inline-block;
        padding: 0.15rem 0.6rem;
        border-radius: 999px;
        font-size: 0.75rem;
        font-weight: 600;
        color: white;
    }
    .score-bar-track {
        background-color: #e9ecef;
        border-radius: 999px;
        height: 8px;
        width: 100%;
        overflow: hidden;
        margin: 0.3rem 0 0.6rem 0;
    }
    .score-bar-fill {
        height: 100%;
        border-radius: 999px;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">🇵🇰 SAFAR: Pakistan Travel Budget Planner</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Plan your journey, optimize costs, and generate trip specifications for Pakistan.</div>', unsafe_allow_html=True)

# ----------------------------------------------------
# 1. TOURIST REQUIREMENTS & TRIP INPUTS
# ----------------------------------------------------
with st.container():
    st.subheader("1. Trip Parameters")
    
    col1, col2, col3 = st.columns(3)

    with col1:
        travelers = st.number_input(
            "Number of Travelers",
            min_value=1,
            max_value=50,
            value=2,
            step=1
        )
        trip_duration = st.number_input(
            "Trip Duration (Days)",
            min_value=1,
            max_value=60,
            value=7,
            step=1
        )

    with col2:
        currency = st.selectbox(
            "Input Currency",
            options=["PKR", "USD"],
            index=0
        )
        default_budget = 300000 if currency == "PKR" else 1100
        min_budget = 5000 if currency == "PKR" else 20
        
        total_budget_input = st.number_input(
            f"Total Budget ({currency})",
            min_value=min_budget,
            value=default_budget,
            step=5000 if currency == "PKR" else 50
        )

    with col3:
        travel_style = st.selectbox(
            "Travel Preference",
            options=["Budget / Backpacker", "Standard", "Luxury"],
            index=1
        )
        destinations = st.multiselect(
            "Planned Destinations",
            options=[
                "Islamabad", "Lahore", "Hunza Valley", "Skardu", 
                "Swat", "Murree", "Gilgit", "Peshawar", "Karachi"
            ],
            default=["Islamabad", "Hunza Valley"]
        )

st.divider()

# ----------------------------------------------------
# 2. BUDGET ENGINE & CALCULATIONS
# ----------------------------------------------------
USD_TO_PKR_RATE = 280.0
total_budget_pkr = float(total_budget_input if currency == "PKR" else total_budget_input * USD_TO_PKR_RATE)

allocation_ratios = {
    "Budget / Backpacker": {"hotels": 0.30, "transport": 0.30, "food": 0.25, "activities": 0.15},
    "Standard": {"hotels": 0.35, "transport": 0.25, "food": 0.20, "activities": 0.20},
    "Luxury": {"hotels": 0.45, "transport": 0.25, "food": 0.15, "activities": 0.15}
}

active_ratios = allocation_ratios[travel_style]
alloc_hotels = total_budget_pkr * active_ratios["hotels"]
alloc_transport = total_budget_pkr * active_ratios["transport"]
alloc_food = total_budget_pkr * active_ratios["food"]
alloc_activities = total_budget_pkr * active_ratios["activities"]

# Feasibility benchmark: ~5,000 PKR per person per day
min_required_budget = travelers * trip_duration * 5000.0
is_feasible = total_budget_pkr >= min_required_budget

# ----------------------------------------------------
# 3. EXPENSE ALLOCATION & VISUALIZATION
# ----------------------------------------------------
st.subheader("2. Expense Breakdown & Allocation")

if is_feasible:
    st.success(f"Budget is balanced: Total allocated budget ({total_budget_pkr:,.0f} PKR) is sufficient for {travelers} travelers across {trip_duration} days.")
else:
    st.warning(f"Budget Notice: Estimated standard baseline is ~{min_required_budget:,.0f} PKR ({travelers} travelers × {trip_duration} days). Costs may require adjustments.")

# Metric Cards
m1, m2, m3, m4 = st.columns(4)
m1.metric("Hotels & Stay", f"PKR {alloc_hotels:,.0f}", f"{active_ratios['hotels']*100:.0f}%")
m2.metric("Transportation", f"PKR {alloc_transport:,.0f}", f"{active_ratios['transport']*100:.0f}%")
m3.metric("Food & Dining", f"PKR {alloc_food:,.0f}", f"{active_ratios['food']*100:.0f}%")
m4.metric("Activities & Sightseeing", f"PKR {alloc_activities:,.0f}", f"{active_ratios['activities']*100:.0f}%")

st.write("")

viz_col1, viz_col2 = st.columns([1.1, 0.9])

with viz_col1:
    breakdown_df = pd.DataFrame({
        "Category": ["Hotels & Accommodation", "Transportation", "Food & Dining", "Activities & Sightseeing"],
        "Allocation": [f"{v * 100:.0f}%" for v in active_ratios.values()],
        "Cost (PKR)": [alloc_hotels, alloc_transport, alloc_food, alloc_activities],
        "Cost (USD)": [alloc_hotels / USD_TO_PKR_RATE, alloc_transport / USD_TO_PKR_RATE, alloc_food / USD_TO_PKR_RATE, alloc_activities / USD_TO_PKR_RATE]
    })
    st.dataframe(
        breakdown_df.style.format({
            "Cost (PKR)": "{:,.0f}",
            "Cost (USD)": "${:,.2f}"
        }),
        use_container_width=True,
        hide_index=True
    )

with viz_col2:
    fig = px.pie(
        breakdown_df,
        names="Category",
        values="Cost (PKR)",
        hole=0.45,
        color_discrete_sequence=["#1b4332", "#2d6a4f", "#52b788", "#74c69d"]
    )
    fig.update_layout(margin=dict(t=20, b=20, l=20, r=20), showlegend=True)
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# ----------------------------------------------------
# 3.5 HOTEL & ACCOMMODATION RECOMMENDATION (Member 3)
# ----------------------------------------------------
st.subheader("3. Hotel Recommendations")

hotels_df = load_hotels()


@st.cache_data(show_spinner=False)
def cached_ai_explanation(hotel_id, hotel_json, travelers, per_city_budget):
    """Cache Groq calls per (hotel, travelers, budget) so Streamlit's
    rerun-on-every-widget-change behavior doesn't re-call the API for
    the same recommendation."""
    hotel = json.loads(hotel_json)
    return generate_ai_explanation(hotel, travelers, per_city_budget)


use_ai_explanations = st.toggle(
    "✨ Use AI (Groq) to explain each hotel pick",
    value=False,
    help="Generates a short natural-language reason for each recommendation. "
         "Falls back to a plain-text summary if no GROQ_API_KEY is configured.",
)

TIER_COLORS = {
    "Budget/Backpacker": "#74c69d",
    "Standard": "#2d6a4f",
    "Luxury": "#1b4332",
    "Mixed (requested tier unavailable here)": "#95a5a6",
}


def _score_color(score: float) -> str:
    if score >= 75:
        return "#2d6a4f"
    elif score >= 50:
        return "#e9c46a"
    else:
        return "#e76f51"


if not destinations:
    st.info("Select at least one destination above to see hotel recommendations.")
    hotel_recommendations = {}
    total_hotel_cost = 0.0
else:
    hotel_recommendations = recommend_hotels(
        df=hotels_df,
        destinations=destinations,
        travel_style=travel_style,
        duration_days=int(trip_duration),
        travelers=int(travelers),
        hotel_budget_pkr=alloc_hotels,
        top_n=3,
    )
    total_hotel_cost = total_estimated_hotel_cost(hotel_recommendations)

    hc1, hc2 = st.columns(2)
    hc1.metric(
        "Hotel Budget Allocated",
        f"PKR {alloc_hotels:,.0f}",
        f"${alloc_hotels / USD_TO_PKR_RATE:,.2f}",
        delta_color="off",
    )
    hc2.metric(
        "Estimated Hotel Cost (top picks)",
        f"PKR {total_hotel_cost:,.0f}",
        f"${total_hotel_cost / USD_TO_PKR_RATE:,.2f}  ·  {(total_hotel_cost - alloc_hotels):+,.0f} PKR vs. budget",
        delta_color="inverse",
    )

    if total_hotel_cost > alloc_hotels:
        st.warning(
            f"Top-ranked hotel picks come to PKR {total_hotel_cost:,.0f} "
            f"(${total_hotel_cost / USD_TO_PKR_RATE:,.2f}), which is above the "
            f"PKR {alloc_hotels:,.0f} hotel budget. Consider a lower travel-style "
            "tier or fewer nights per city."
        )
    else:
        st.success(
            f"Recommended hotels fit within the PKR {alloc_hotels:,.0f} hotel budget "
            f"(estimated PKR {total_hotel_cost:,.0f} / ${total_hotel_cost / USD_TO_PKR_RATE:,.2f})."
        )

    # Budget vs. estimated cost per city, shown half-width alongside a
    # compact summary table — mirroring the table+donut layout used for
    # the overall expense breakdown above, instead of a full-width chart.
    if len(destinations) >= 1:
        summary_rows = []
        for city in destinations:
            cdata = hotel_recommendations.get(city, {})
            budget = cdata.get("per_city_budget_pkr", 0)
            top_cost = cdata["hotels"][0]["estimated_stay_cost_pkr"] if cdata.get("hotels") else 0
            pct = (top_cost / budget * 100) if budget > 0 else 0
            summary_rows.append({
                "City": city,
                "Tier Used": cdata.get("tier_used") or "-",
                "Budget (PKR)": budget,
                "Top Pick (PKR)": top_cost,
                "% Used": f"{pct:,.0f}%",
            })
        summary_df = pd.DataFrame(summary_rows)

        hchart_col, htable_col = st.columns([1, 1])

        with hchart_col:
            chart_df = summary_df.rename(
                columns={"Budget (PKR)": "Budget Allocated", "Top Pick (PKR)": "Top Pick Cost"}
            )[["City", "Budget Allocated", "Top Pick Cost"]]
            fig_hotels = px.bar(
                chart_df.melt(id_vars="City", var_name="Type", value_name="PKR"),
                x="City", y="PKR", color="Type", barmode="group",
                color_discrete_sequence=["#95d5b2", "#1b4332"],
            )
            fig_hotels.update_layout(
                margin=dict(t=20, b=20, l=20, r=20),
                legend_title_text="",
                showlegend=True,
            )
            st.plotly_chart(fig_hotels, use_container_width=True)

        with htable_col:
            st.dataframe(
                summary_df.style.format({
                    "Budget (PKR)": "{:,.0f}",
                    "Top Pick (PKR)": "{:,.0f}",
                }),
                use_container_width=True,
                hide_index=True,
            )

    st.write("")

    for city in destinations:
        city_data = hotel_recommendations.get(city)
        if not city_data:
            continue

        st.markdown(f"#### 📍 {city}")

        if city_data.get("note"):
            st.caption(f"⚠️ {city_data['note']}")

        if not city_data["hotels"]:
            st.info("No hotel options available for this city yet.")
            continue

        cols = st.columns(len(city_data["hotels"]))
        for col, hotel in zip(cols, city_data["hotels"]):
            rooms = hotel["rooms_needed"]
            room_line = (
                f"🛏️ {rooms} rooms needed for {travelers} guests<br>"
                if rooms > 1 else ""
            )
            badge_color = TIER_COLORS.get(hotel["hotel_type"], "#6c757d")
            score = hotel["recommendation_score"]
            score_color = _score_color(score)
            price_usd = hotel["price_per_day_pkr"] / USD_TO_PKR_RATE
            total_usd = hotel["estimated_stay_cost_pkr"] / USD_TO_PKR_RATE

            with col:
                st.markdown(
                    f"""<div class="card-box">
                    <b>{hotel['hotel_name']}</b>
                    <span class="tier-badge" style="background-color:{badge_color};">{hotel['hotel_type']}</span><br>
                    <span style="font-size:0.8rem;color:#666;">Match score</span>
                    <div class="score-bar-track">
                        <div class="score-bar-fill" style="width:{score}%;background-color:{score_color};"></div>
                    </div>
                    ⭐ {hotel['rating']} &nbsp;|&nbsp; 📝 {hotel['review_count']:,} reviews<br>
                    🏔️ {hotel['travel_theme']} theme &middot; {hotel['region']} region<br>
                    💰 PKR {hotel['price_per_day_pkr']:,.0f} (${price_usd:,.2f})/day per room<br>
                    {room_line}🧾 Est. stay total: PKR {hotel['estimated_stay_cost_pkr']:,.0f} (${total_usd:,.2f})<br>
                    👥 Up to {hotel['max_guests']} guests per room
                    </div>""",
                    unsafe_allow_html=True,
                )
                with st.expander("Amenities"):
                    if hotel["amenities"]:
                        st.write(", ".join(hotel["amenities"]))
                    else:
                        st.write("Not listed")

                if use_ai_explanations:
                    with st.spinner("Thinking..."):
                        explanation = cached_ai_explanation(
                            hotel["hotel_id"],
                            json.dumps(hotel),
                            travelers,
                            city_data["per_city_budget_pkr"],
                        )
                    st.caption(f"🤖 {explanation}")

        st.write("")

st.divider()

# ----------------------------------------------------
# 4. STRUCTURED DATA EXPORT
# ----------------------------------------------------
st.subheader("3. Trip Payload")

# Original Member 2 schema, unchanged — kept separate so anything already
# consuming budget_data.json (per the team's original contract) doesn't
# have to change or wade through hotel data it doesn't expect.
budget_payload = {
    "user_profile": {
        "travelers": int(travelers),
        "duration_days": int(trip_duration),
        "travel_style": travel_style
    },
    "destinations": destinations,
    "budget_pkr": {
        "total": float(total_budget_pkr),
        "hotels": float(alloc_hotels),
        "transport": float(alloc_transport),
        "food": float(alloc_food),
        "activities": float(alloc_activities)
    },
    "budget_usd": {
        "total": float(total_budget_pkr / USD_TO_PKR_RATE),
        "hotels": float(alloc_hotels / USD_TO_PKR_RATE),
        "transport": float(alloc_transport / USD_TO_PKR_RATE),
        "food": float(alloc_food / USD_TO_PKR_RATE),
        "activities": float(alloc_activities / USD_TO_PKR_RATE)
    },
    "is_feasible": bool(is_feasible),
}

# Fuller payload — everything above PLUS hotel recommendations, for
# Member 4/Member 1 or anyone who wants the complete picture in one file.
hotel_payload = {
    **budget_payload,
    "hotel_recommendations": hotel_recommendations,
    "total_estimated_hotel_cost_pkr": float(total_hotel_cost),
}

budget_payload_json = json.dumps(budget_payload, indent=4)
hotel_payload_json = json.dumps(hotel_payload, indent=4)

dl1, dl2 = st.columns(2)
with dl1:
    st.download_button(
        label="📥 Download Budget Payload (budget_data.json)",
        data=budget_payload_json,
        file_name="budget_data.json",
        mime="application/json"
    )
with dl2:
    st.download_button(
        label="📥 Download Hotel Recommendations (hotel-recommendation.json)",
        data=hotel_payload_json,
        file_name="hotel-recommendation.json",
        mime="application/json"
    )

import streamlit as st
import pandas as pd
import plotly.express as px
import json
from hotel_utils import (
    load_hotels,
    recommend_hotels,
    total_estimated_hotel_cost,
    generate_ai_explanation,
)

# Page Setup & Configuration
st.set_page_config(
    page_title="SAFAR - AI Travel Companion for Pakistan",
    page_icon="🇵🇰",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for a clean modern UI
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1b4332;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #555;
        margin-bottom: 1.5rem;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.5rem !important;
        font-weight: 700 !important;
        color: #2d6a4f !important;
    }
    .card-box {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 1.2rem;
        border: 1px solid #e9ecef;
    }
    .tier-badge {
        display: inline-block;
        padding: 0.15rem 0.6rem;
        border-radius: 999px;
        font-size: 0.75rem;
        font-weight: 600;
        color: white;
    }
    .score-bar-track {
        background-color: #e9ecef;
        border-radius: 999px;
        height: 8px;
        width: 100%;
        overflow: hidden;
        margin: 0.3rem 0 0.6rem 0;
    }
    .score-bar-fill {
        height: 100%;
        border-radius: 999px;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">🇵🇰 SAFAR: Pakistan Travel Budget Planner</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Plan your journey, optimize costs, and generate trip specifications for Pakistan.</div>', unsafe_allow_html=True)

# ----------------------------------------------------
# 1. TOURIST REQUIREMENTS & TRIP INPUTS
# ----------------------------------------------------
with st.container():
    st.subheader("1. Trip Parameters")
    
    col1, col2, col3 = st.columns(3)

    with col1:
        travelers = st.number_input(
            "Number of Travelers",
            min_value=1,
            max_value=50,
            value=2,
            step=1
        )
        trip_duration = st.number_input(
            "Trip Duration (Days)",
            min_value=1,
            max_value=60,
            value=7,
            step=1
        )

    with col2:
        currency = st.selectbox(
            "Input Currency",
            options=["PKR", "USD"],
            index=0
        )
        default_budget = 300000 if currency == "PKR" else 1100
        min_budget = 5000 if currency == "PKR" else 20
        
        total_budget_input = st.number_input(
            f"Total Budget ({currency})",
            min_value=min_budget,
            value=default_budget,
            step=5000 if currency == "PKR" else 50
        )

    with col3:
        travel_style = st.selectbox(
            "Travel Preference",
            options=["Budget / Backpacker", "Standard", "Luxury"],
            index=1
        )
        destinations = st.multiselect(
            "Planned Destinations",
            options=[
                "Islamabad", "Lahore", "Hunza Valley", "Skardu", 
                "Swat", "Murree", "Gilgit", "Peshawar", "Karachi"
            ],
            default=["Islamabad", "Hunza Valley"]
        )

st.divider()

# ----------------------------------------------------
# 2. BUDGET ENGINE & CALCULATIONS
# ----------------------------------------------------
USD_TO_PKR_RATE = 280.0
total_budget_pkr = float(total_budget_input if currency == "PKR" else total_budget_input * USD_TO_PKR_RATE)

allocation_ratios = {
    "Budget / Backpacker": {"hotels": 0.30, "transport": 0.30, "food": 0.25, "activities": 0.15},
    "Standard": {"hotels": 0.35, "transport": 0.25, "food": 0.20, "activities": 0.20},
    "Luxury": {"hotels": 0.45, "transport": 0.25, "food": 0.15, "activities": 0.15}
}

active_ratios = allocation_ratios[travel_style]
alloc_hotels = total_budget_pkr * active_ratios["hotels"]
alloc_transport = total_budget_pkr * active_ratios["transport"]
alloc_food = total_budget_pkr * active_ratios["food"]
alloc_activities = total_budget_pkr * active_ratios["activities"]

# Feasibility benchmark: ~5,000 PKR per person per day
min_required_budget = travelers * trip_duration * 5000.0
is_feasible = total_budget_pkr >= min_required_budget

# ----------------------------------------------------
# 3. EXPENSE ALLOCATION & VISUALIZATION
# ----------------------------------------------------
st.subheader("2. Expense Breakdown & Allocation")

if is_feasible:
    st.success(f"Budget is balanced: Total allocated budget ({total_budget_pkr:,.0f} PKR) is sufficient for {travelers} travelers across {trip_duration} days.")
else:
    st.warning(f"Budget Notice: Estimated standard baseline is ~{min_required_budget:,.0f} PKR ({travelers} travelers × {trip_duration} days). Costs may require adjustments.")

# Metric Cards
m1, m2, m3, m4 = st.columns(4)
m1.metric("Hotels & Stay", f"PKR {alloc_hotels:,.0f}", f"{active_ratios['hotels']*100:.0f}%")
m2.metric("Transportation", f"PKR {alloc_transport:,.0f}", f"{active_ratios['transport']*100:.0f}%")
m3.metric("Food & Dining", f"PKR {alloc_food:,.0f}", f"{active_ratios['food']*100:.0f}%")
m4.metric("Activities & Sightseeing", f"PKR {alloc_activities:,.0f}", f"{active_ratios['activities']*100:.0f}%")

st.write("")

viz_col1, viz_col2 = st.columns([1.1, 0.9])

with viz_col1:
    breakdown_df = pd.DataFrame({
        "Category": ["Hotels & Accommodation", "Transportation", "Food & Dining", "Activities & Sightseeing"],
        "Allocation": [f"{v * 100:.0f}%" for v in active_ratios.values()],
        "Cost (PKR)": [alloc_hotels, alloc_transport, alloc_food, alloc_activities],
        "Cost (USD)": [alloc_hotels / USD_TO_PKR_RATE, alloc_transport / USD_TO_PKR_RATE, alloc_food / USD_TO_PKR_RATE, alloc_activities / USD_TO_PKR_RATE]
    })
    st.dataframe(
        breakdown_df.style.format({
            "Cost (PKR)": "{:,.0f}",
            "Cost (USD)": "${:,.2f}"
        }),
        use_container_width=True,
        hide_index=True
    )

with viz_col2:
    fig = px.pie(
        breakdown_df,
        names="Category",
        values="Cost (PKR)",
        hole=0.45,
        color_discrete_sequence=["#1b4332", "#2d6a4f", "#52b788", "#74c69d"]
    )
    fig.update_layout(margin=dict(t=20, b=20, l=20, r=20), showlegend=True)
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# ----------------------------------------------------
# 3.5 HOTEL & ACCOMMODATION RECOMMENDATION (Member 3)
# ----------------------------------------------------
st.subheader("3. Hotel Recommendations")

hotels_df = load_hotels()


@st.cache_data(show_spinner=False)
def cached_ai_explanation(hotel_id, hotel_json, travelers, per_city_budget):
    """Cache Groq calls per (hotel, travelers, budget) so Streamlit's
    rerun-on-every-widget-change behavior doesn't re-call the API for
    the same recommendation."""
    hotel = json.loads(hotel_json)
    return generate_ai_explanation(hotel, travelers, per_city_budget)


use_ai_explanations = st.toggle(
    "✨ Use AI (Groq) to explain each hotel pick",
    value=False,
    help="Generates a short natural-language reason for each recommendation. "
         "Falls back to a plain-text summary if no GROQ_API_KEY is configured.",
)

TIER_COLORS = {
    "Budget/Backpacker": "#74c69d",
    "Standard": "#2d6a4f",
    "Luxury": "#1b4332",
    "Mixed (requested tier unavailable here)": "#95a5a6",
}


def _score_color(score: float) -> str:
    if score >= 75:
        return "#2d6a4f"
    elif score >= 50:
        return "#e9c46a"
    else:
        return "#e76f51"


if not destinations:
    st.info("Select at least one destination above to see hotel recommendations.")
    hotel_recommendations = {}
    total_hotel_cost = 0.0
else:
    hotel_recommendations = recommend_hotels(
        df=hotels_df,
        destinations=destinations,
        travel_style=travel_style,
        duration_days=int(trip_duration),
        travelers=int(travelers),
        hotel_budget_pkr=alloc_hotels,
        top_n=3,
    )
    total_hotel_cost = total_estimated_hotel_cost(hotel_recommendations)

    hc1, hc2 = st.columns(2)
    hc1.metric(
        "Hotel Budget Allocated",
        f"PKR {alloc_hotels:,.0f}",
        f"${alloc_hotels / USD_TO_PKR_RATE:,.2f}",
        delta_color="off",
    )
    hc2.metric(
        "Estimated Hotel Cost (top picks)",
        f"PKR {total_hotel_cost:,.0f}",
        f"${total_hotel_cost / USD_TO_PKR_RATE:,.2f}  ·  {(total_hotel_cost - alloc_hotels):+,.0f} PKR vs. budget",
        delta_color="inverse",
    )

    if total_hotel_cost > alloc_hotels:
        st.warning(
            f"Top-ranked hotel picks come to PKR {total_hotel_cost:,.0f} "
            f"(${total_hotel_cost / USD_TO_PKR_RATE:,.2f}), which is above the "
            f"PKR {alloc_hotels:,.0f} hotel budget. Consider a lower travel-style "
            "tier or fewer nights per city."
        )
    else:
        st.success(
            f"Recommended hotels fit within the PKR {alloc_hotels:,.0f} hotel budget "
            f"(estimated PKR {total_hotel_cost:,.0f} / ${total_hotel_cost / USD_TO_PKR_RATE:,.2f})."
        )

    # Budget vs. estimated cost per city, shown half-width alongside a
    # compact summary table — mirroring the table+donut layout used for
    # the overall expense breakdown above, instead of a full-width chart.
    if len(destinations) >= 1:
        summary_rows = []
        for city in destinations:
            cdata = hotel_recommendations.get(city, {})
            budget = cdata.get("per_city_budget_pkr", 0)
            top_cost = cdata["hotels"][0]["estimated_stay_cost_pkr"] if cdata.get("hotels") else 0
            pct = (top_cost / budget * 100) if budget > 0 else 0
            summary_rows.append({
                "City": city,
                "Tier Used": cdata.get("tier_used") or "-",
                "Budget (PKR)": budget,
                "Top Pick (PKR)": top_cost,
                "% Used": f"{pct:,.0f}%",
            })
        summary_df = pd.DataFrame(summary_rows)

        hchart_col, htable_col = st.columns([1, 1])

        with hchart_col:
            chart_df = summary_df.rename(
                columns={"Budget (PKR)": "Budget Allocated", "Top Pick (PKR)": "Top Pick Cost"}
            )[["City", "Budget Allocated", "Top Pick Cost"]]
            fig_hotels = px.bar(
                chart_df.melt(id_vars="City", var_name="Type", value_name="PKR"),
                x="City", y="PKR", color="Type", barmode="group",
                color_discrete_sequence=["#95d5b2", "#1b4332"],
            )
            fig_hotels.update_layout(
                margin=dict(t=20, b=20, l=20, r=20),
                legend_title_text="",
                showlegend=True,
            )
            st.plotly_chart(fig_hotels, use_container_width=True)

        with htable_col:
            st.dataframe(
                summary_df.style.format({
                    "Budget (PKR)": "{:,.0f}",
                    "Top Pick (PKR)": "{:,.0f}",
                }),
                use_container_width=True,
                hide_index=True,
            )

    st.write("")

    for city in destinations:
        city_data = hotel_recommendations.get(city)
        if not city_data:
            continue

        st.markdown(f"#### 📍 {city}")

        if city_data.get("note"):
            st.caption(f"⚠️ {city_data['note']}")

        if not city_data["hotels"]:
            st.info("No hotel options available for this city yet.")
            continue

        cols = st.columns(len(city_data["hotels"]))
        for col, hotel in zip(cols, city_data["hotels"]):
            rooms = hotel["rooms_needed"]
            room_line = (
                f"🛏️ {rooms} rooms needed for {travelers} guests<br>"
                if rooms > 1 else ""
            )
            badge_color = TIER_COLORS.get(hotel["hotel_type"], "#6c757d")
            score = hotel["recommendation_score"]
            score_color = _score_color(score)
            price_usd = hotel["price_per_day_pkr"] / USD_TO_PKR_RATE
            total_usd = hotel["estimated_stay_cost_pkr"] / USD_TO_PKR_RATE

            with col:
                st.markdown(
                    f"""<div class="card-box">
                    <b>{hotel['hotel_name']}</b>
                    <span class="tier-badge" style="background-color:{badge_color};">{hotel['hotel_type']}</span><br>
                    <span style="font-size:0.8rem;color:#666;">Match score</span>
                    <div class="score-bar-track">
                        <div class="score-bar-fill" style="width:{score}%;background-color:{score_color};"></div>
                    </div>
                    ⭐ {hotel['rating']} &nbsp;|&nbsp; 📝 {hotel['review_count']:,} reviews<br>
                    🏔️ {hotel['travel_theme']} theme &middot; {hotel['region']} region<br>
                    💰 PKR {hotel['price_per_day_pkr']:,.0f} (${price_usd:,.2f})/day per room<br>
                    {room_line}🧾 Est. stay total: PKR {hotel['estimated_stay_cost_pkr']:,.0f} (${total_usd:,.2f})<br>
                    👥 Up to {hotel['max_guests']} guests per room
                    </div>""",
                    unsafe_allow_html=True,
                )
                with st.expander("Amenities"):
                    if hotel["amenities"]:
                        st.write(", ".join(hotel["amenities"]))
                    else:
                        st.write("Not listed")

                if use_ai_explanations:
                    with st.spinner("Thinking..."):
                        explanation = cached_ai_explanation(
                            hotel["hotel_id"],
                            json.dumps(hotel),
                            travelers,
                            city_data["per_city_budget_pkr"],
                        )
                    st.caption(f"🤖 {explanation}")

        st.write("")

st.divider()

# ----------------------------------------------------
# 4. STRUCTURED DATA EXPORT
# ----------------------------------------------------
st.subheader("3. Trip Payload")

# Original Member 2 schema, unchanged — kept separate so anything already
# consuming budget_data.json (per the team's original contract) doesn't
# have to change or wade through hotel data it doesn't expect.
budget_payload = {
    "user_profile": {
        "travelers": int(travelers),
        "duration_days": int(trip_duration),
        "travel_style": travel_style
    },
    "destinations": destinations,
    "budget_pkr": {
        "total": float(total_budget_pkr),
        "hotels": float(alloc_hotels),
        "transport": float(alloc_transport),
        "food": float(alloc_food),
        "activities": float(alloc_activities)
    },
    "budget_usd": {
        "total": float(total_budget_pkr / USD_TO_PKR_RATE),
        "hotels": float(alloc_hotels / USD_TO_PKR_RATE),
        "transport": float(alloc_transport / USD_TO_PKR_RATE),
        "food": float(alloc_food / USD_TO_PKR_RATE),
        "activities": float(alloc_activities / USD_TO_PKR_RATE)
    },
    "is_feasible": bool(is_feasible),
}

# Fuller payload — everything above PLUS hotel recommendations, for
# Member 4/Member 1 or anyone who wants the complete picture in one file.
hotel_payload = {
    **budget_payload,
    "hotel_recommendations": hotel_recommendations,
    "total_estimated_hotel_cost_pkr": float(total_hotel_cost),
}

budget_payload_json = json.dumps(budget_payload, indent=4)
hotel_payload_json = json.dumps(hotel_payload, indent=4)

dl1, dl2 = st.columns(2)
with dl1:
    st.download_button(
        label="📥 Download Budget Payload (budget_data.json)",
        data=budget_payload_json,
        file_name="budget_data.json",
        mime="application/json"
    )
with dl2:
    st.download_button(
        label="📥 Download Hotel Recommendations (hotel-recommendation.json)",
        data=hotel_payload_json,
        file_name="hotel-recommendation.json",
        mime="application/json"
    )

with st.expander("View Payload Preview"):
    st.json(hotel_payload)
