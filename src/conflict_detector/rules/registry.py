from src.conflict_detector.rules.basic_rules import BASIC_RULES
from src.conflict_detector.rules.constraint_rules import CONSTRAINT_RULES
from src.conflict_detector.rules.dependency_rules import DEPENDENCY_RULES
from src.conflict_detector.rules.index_rules import INDEX_RULES
from src.conflict_detector.rules.reference_rules import REFERENCE_RULES


DEFAULT_RULES = [
    *BASIC_RULES,
    *DEPENDENCY_RULES,
    *REFERENCE_RULES,
    *CONSTRAINT_RULES,
    *INDEX_RULES,
]
