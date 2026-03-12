"""
Static risk data: country risk scores, high-risk industries, sanctions list stubs.
"""
from typing import Dict, List

# ─── Country Risk Scores (0-100) ──────────────────────────────────────────────
# Based on FATF grey/blacklists, Basel AML Index, and Transparency International

COUNTRY_RISK_SCORES: Dict[str, float] = {
    # Critical risk (>70)
    "KP": 95, "IR": 90, "SY": 88, "YE": 85, "AF": 84,
    "SD": 82, "SS": 80, "LY": 78, "MM": 76, "VN": 74,
    "PK": 72, "ZW": 71,
    # High risk (50-70)
    "NG": 68, "KE": 65, "GH": 62, "TZ": 60, "MW": 58,
    "AE": 60, "PA": 58, "MT": 55, "TR": 52, "BA": 51,
    # Medium risk (20-50)
    "RU": 48, "CN": 42, "IN": 35, "BR": 38, "MX": 40,
    "CO": 42, "ZA": 36, "UA": 38, "TH": 32, "VE": 45,
    # Low risk (<20)
    "US": 15, "GB": 12, "DE": 10, "FR": 11, "CH": 10,
    "AU": 10, "CA": 11, "JP": 8,  "NL": 12, "SE": 8,
    "NO": 7,  "DK": 7,  "FI": 6,  "SG": 15, "NZ": 8,
}

DEFAULT_COUNTRY_RISK = 40  # Unknown countries get medium-high risk


# ─── Sanctions Lists (stub – in production connect to OFAC/UN APIs) ───────────

SANCTIONED_COUNTRIES: List[str] = ["KP", "IR", "SY", "CU", "SD"]
SANCTIONED_ENTITIES: List[str] = [
    "ACME_OFFSHORE_LTD",  # Placeholder – replaced by live OFAC data
    "SHADOW_HOLDINGS",
    "GHOST_CORP",
]

HIGH_RISK_INDUSTRIES: List[str] = [
    "crypto", "cryptocurrency", "gambling", "casino",
    "adult entertainment", "firearms", "arms", "precious metals",
    "money services", "forex", "hawala", "shell company",
]

MEDIUM_RISK_INDUSTRIES: List[str] = [
    "real estate", "construction", "import export", "trading",
    "legal services", "accounting", "luxury goods",
]

PEP_RISK_BOOST = 30
ADVERSE_MEDIA_BOOST = 20
SANCTIONS_COUNTRY_BOOST = 50


def get_country_risk(country_code: str) -> float:
    """Return risk score for a country (0-100)."""
    return COUNTRY_RISK_SCORES.get(country_code.upper(), DEFAULT_COUNTRY_RISK)


def get_industry_risk(industry: str) -> float:
    """Return industry risk score (0-100)."""
    industry_lower = industry.lower()
    for hi_risk in HIGH_RISK_INDUSTRIES:
        if hi_risk in industry_lower:
            return 80.0
    for med_risk in MEDIUM_RISK_INDUSTRIES:
        if med_risk in industry_lower:
            return 45.0
    return 20.0


def is_sanctioned_country(country_code: str) -> bool:
    return country_code.upper() in SANCTIONED_COUNTRIES


def is_sanctioned_entity(entity_id: str) -> bool:
    return entity_id.upper() in [e.upper() for e in SANCTIONED_ENTITIES]


def compute_risk_rating(score: float) -> str:
    """Map a numeric risk score to a rating category."""
    if score <= 30:
        return "LOW"
    elif score <= 60:
        return "MEDIUM"
    elif score <= 80:
        return "HIGH"
    else:
        return "CRITICAL"
