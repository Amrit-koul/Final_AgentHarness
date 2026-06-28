"""Enterprise score explainability layer."""
from typing import Any, Dict

def explain_scores(scores: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze scoring engine output for top positive and negative factors."""
    positive_factors = []
    negative_factors = []
    
    # We'll pull from the structured outputs of the new scoring engine
    for key, data in scores.items():
        if isinstance(data, dict):
            # The new format guarantees positive_factors and negative_factors
            pos = data.get("positive_factors", [])
            neg = data.get("negative_factors", [])
            
            # Label them by score type
            label = key.replace("_", " ").title()
            for p in pos:
                positive_factors.append(f"[{label}] {p}")
            for n in neg:
                negative_factors.append(f"[{label}] {n}")
                
    # Sort or rank them if needed, here we just take the top 5 of each
    return {
        "overall_summary": "Score explanation generated from enterprise evidence-based engine",
        "top_positive_factors": positive_factors[:5],
        "top_negative_factors": negative_factors[:5],
    }


