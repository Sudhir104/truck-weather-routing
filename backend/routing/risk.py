"""Risk rules from the assessment brief. Levels: 0 Low .. 4 No Travel."""
LEVELS = ["Low", "Moderate", "High", "Severe", "No Travel"]

# (cut points for Moderate/High/Severe/No Travel, is the top cut inclusive?)
WIND = ((25, 35, 45, 55), True)    # >=55 mph is No Travel
RAIN = ((0.10, 0.25, 0.50, 1.00), False)  # >1.00 in/hr is No Travel
SNOW = ((0.5, 1.0, 2.0, 3.0), False)      # >3.0 in/hr is No Travel


def band(value, rule):
    cuts, top_inclusive = rule
    level = sum(value >= c for c in cuts[:3])
    top = value >= cuts[3] if top_inclusive else value > cuts[3]
    return 4 if top else level


def wind_level(mph, load_lbs):
    level = band(mph, WIND)
    if 45 <= mph < 55 and load_lbs > 30000:
        level = 4
    elif 35 <= mph < 45 and load_lbs > 40000:
        level = max(level, 3)
    return level


def checkpoint_risk(wind, rain, snow, load_lbs):
    return max(wind_level(wind, load_lbs), band(rain, RAIN), band(snow, SNOW))
