"""Purchase checklist scoring and the optional OpenAI advisor of the file/purchase assistant."""
from .ai_advisor import AIAdvice, ShoppingAdvisorError, advise_purchase
from .evaluator import PurchaseAssessment, evaluate_purchase
from .models import ProductCandidate

__all__ = [
    "AIAdvice",
    "ProductCandidate",
    "PurchaseAssessment",
    "ShoppingAdvisorError",
    "advise_purchase",
    "evaluate_purchase",
]
