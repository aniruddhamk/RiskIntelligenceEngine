"""
Rule Evaluator – loads and evaluates JSON-configured AML rules.
"""
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Rule weights
RULE_WEIGHTS = {
    "SANCTIONS_COUNTRY": 50,
    "PEP_FLAG": 30,
    "ADVERSE_MEDIA": 20,
    "HIGH_RISK_INDUSTRY": 20,
    "MEDIUM_RISK_INDUSTRY": 10,
    "HIGH_CASH_RATIO": 15,
    "HIGH_INTERNATIONAL_RATIO": 10,
    "VERY_HIGH_VOLUME": 15,
    "CORPORATE_UNVERIFIED_FUNDS": 10,
    "HIGH_COUNTRY_RISK": 20,
    "CRYPTO_EXPOSURE": 25,
}

# Sanctioned/high-risk classifications
SANCTIONED_COUNTRIES = {"KP", "IR", "SY", "CU", "SD"}
HIGH_RISK_INDUSTRIES = {"crypto", "cryptocurrency", "gambling", "casino", "firearms", "arms", "hawala", "money services"}
MEDIUM_RISK_INDUSTRIES = {"real estate", "construction", "trading", "forex", "legal services"}

HIGH_RISK_COUNTRIES = {"KP", "IR", "SY", "AF", "YE", "SS", "SD", "LY", "MM"}


class RuleEvaluator:
    """
    Evaluates a set of configurable AML risk rules.
    Rules are loaded from aml_rules.json; fallback uses hardcoded rules.
    """

    def __init__(self):
        self._rules = self._load_rules()
        logger.info(f"RuleEvaluator initialized with {len(self._rules)} rules")

    def _load_rules(self) -> List[Dict]:
        rules_path = os.path.join(os.path.dirname(__file__), "..", "rules", "aml_rules.json")
        try:
            with open(rules_path) as f:
                return json.load(f).get("rules", [])
        except Exception as e:
            logger.warning(f"Could not load rules file: {e}. Using built-in rules.")
            return self._default_rules()

    def _default_rules(self) -> List[Dict]:
        return [
            {"id": "R001", "name": "Sanctioned Country", "code": "SANCTIONS_COUNTRY", "weight": 50, "active": True},
            {"id": "R002", "name": "PEP Flag", "code": "PEP_FLAG", "weight": 30, "active": True},
            {"id": "R003", "name": "Adverse Media", "code": "ADVERSE_MEDIA", "weight": 20, "active": True},
            {"id": "R004", "name": "High Risk Industry", "code": "HIGH_RISK_INDUSTRY", "weight": 20, "active": True},
            {"id": "R005", "name": "High Cash Ratio (>30%)", "code": "HIGH_CASH_RATIO", "weight": 15, "active": True},
            {"id": "R006", "name": "High International Ratio (>60%)", "code": "HIGH_INTERNATIONAL_RATIO", "weight": 10, "active": True},
            {"id": "R007", "name": "Very High Volume (>$10M/mo)", "code": "VERY_HIGH_VOLUME", "weight": 15, "active": True},
            {"id": "R008", "name": "High Risk Country", "code": "HIGH_COUNTRY_RISK", "weight": 20, "active": True},
            {"id": "R009", "name": "Crypto Exposure", "code": "CRYPTO_EXPOSURE", "weight": 25, "active": True},
            {"id": "R010", "name": "Medium Risk Industry", "code": "MEDIUM_RISK_INDUSTRY", "weight": 10, "active": True},
        ]

    def evaluate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate all active rules against client data and return score."""
        score = 0.0
        triggered = []
        details = {}

        country = data.get("country", "").upper()
        industry = data.get("industry", "").lower()
        pep_flag = data.get("pep_flag", False)
        adverse_media = data.get("adverse_media", False)
        cash_ratio = data.get("cash_ratio", 0.0)
        cross_border_ratio = data.get("cross_border_ratio", 0.0)
        transaction_volume = data.get("transaction_volume", 0.0)
        client_id = data.get("client_id", "UNKNOWN")

        for rule in self._rules:
            if not rule.get("active", True):
                continue
            code = rule["code"]
            weight = rule.get("weight", RULE_WEIGHTS.get(code, 0))
            triggered_flag = False

            if code == "SANCTIONS_COUNTRY" and country in SANCTIONED_COUNTRIES:
                triggered_flag = True
                details[code] = f"Country {country} is on sanctions list"

            elif code == "PEP_FLAG" and pep_flag:
                triggered_flag = True
                details[code] = "Client is a Politically Exposed Person"

            elif code == "ADVERSE_MEDIA" and adverse_media:
                triggered_flag = True
                details[code] = "Adverse media coverage detected"

            elif code == "HIGH_RISK_INDUSTRY":
                for hi in HIGH_RISK_INDUSTRIES:
                    if hi in industry:
                        triggered_flag = True
                        details[code] = f"Industry '{industry}' is high-risk"
                        break

            elif code == "MEDIUM_RISK_INDUSTRY" and not triggered_flag:
                for med in MEDIUM_RISK_INDUSTRIES:
                    if med in industry:
                        triggered_flag = True
                        details[code] = f"Industry '{industry}' is medium-risk"
                        break

            elif code == "HIGH_CASH_RATIO" and cash_ratio > 0.30:
                triggered_flag = True
                details[code] = f"Cash ratio {cash_ratio:.0%} exceeds 30% threshold"

            elif code == "HIGH_INTERNATIONAL_RATIO" and cross_border_ratio > 0.60:
                triggered_flag = True
                details[code] = f"International ratio {cross_border_ratio:.0%} exceeds 60% threshold"

            elif code == "VERY_HIGH_VOLUME" and transaction_volume > 10_000_000:
                triggered_flag = True
                details[code] = f"Monthly volume ${transaction_volume:,.0f} exceeds $10M threshold"

            elif code == "HIGH_COUNTRY_RISK" and country in HIGH_RISK_COUNTRIES:
                triggered_flag = True
                details[code] = f"Country {country} is classified as high-risk"

            elif code == "CRYPTO_EXPOSURE" and ("crypto" in industry or "blockchain" in industry):
                triggered_flag = True
                details[code] = "Business operates in cryptocurrency/blockchain sector"

            if triggered_flag:
                score += weight
                triggered.append(rule["name"])
                logger.debug(f"Rule '{rule['name']}' triggered for {client_id}: +{weight} pts")

        final_score = min(score, 100.0)
        return {
            "client_id": client_id,
            "rule_score": final_score,
            "triggered_rules": triggered,
            "rule_details": details,
            "evaluated_at": datetime.utcnow().isoformat(),
        }

    def get_rules(self) -> List[Dict]:
        return self._rules
