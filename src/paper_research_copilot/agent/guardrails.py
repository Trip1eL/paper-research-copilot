"""High-precision deterministic question screening before research retrieval."""

import re

from paper_research_copilot.agent.models import ClarificationRequest, QuestionScreening

CLARIFIED_QUESTION_TEMPLATE = """原研究问题：
{original_question}

用户补充：
{clarification_response}

请结合用户补充回答原研究问题。"""

_CLARIFIED_QUESTION = re.compile(
    r"^原研究问题：\s*(?P<question>.+?)\s*用户补充：\s*(?P<response>.+?)\s*"
    r"请结合用户补充回答原研究问题。$",
    re.DOTALL,
)

_UNRESOLVED_REFERENCE = re.compile(
    r"(?:刚才|刚刚|前面|上面|此前|之前|前文).{0,10}"
    r"(?:提到|讨论|说过|介绍).{0,10}(?:论文|文章|方法|工作|模型)"
)
_UNRESOLVED_DEICTIC_REFERENCE = re.compile(
    r"(?:刚才|刚刚|前面|上面|此前|之前|前文).{0,10}"
    r"(?:提到|讨论|说过|介绍).{0,8}(?:这|那|该)(?:篇|个|种|项)"
)
_UNSCOPED_SUPERLATIVE = re.compile(
    r"(?:目前|现在|当前)?(?:最好|最佳|最强|最优|最先进).{0,20}"
    r"(?:方法|论文|模型|方案|工作)"
)
_UNDERSPECIFIED_SELECTION = re.compile(
    r"我应该(?:使用|选择|采用).{0,8}(?:哪篇|哪个|哪种).{0,20}"
    r"(?:论文|方法|模型)"
)


class QuestionAmbiguityGate:
    """Reject only question forms that cannot be grounded without clarification."""

    def screen(self, question: str) -> QuestionScreening:
        normalized = " ".join(question.split())
        clarified = _CLARIFIED_QUESTION.match(question.strip())
        original = (
            " ".join(clarified.group("question").split()) if clarified else normalized
        )
        response = " ".join(clarified.group("response").split()) if clarified else None
        if _has_unresolved_reference(original) and not _resolves_reference(response):
            return QuestionScreening(
                decision="ambiguous",
                rule_id="unresolved_reference",
                reason="问题引用了当前请求中不存在的前文对象",
            )
        if _UNSCOPED_SUPERLATIVE.search(original) and not _adds_decision_scope(response):
            return QuestionScreening(
                decision="ambiguous",
                rule_id="unscoped_superlative",
                reason="问题要求判断最佳方案，但没有给出任务、数据集或评价标准",
            )
        if _UNDERSPECIFIED_SELECTION.search(original) and not _adds_decision_scope(response):
            return QuestionScreening(
                decision="ambiguous",
                rule_id="underspecified_selection",
                reason="问题要求选择论文方法，但没有给出使用目标或约束",
            )
        return QuestionScreening(
            decision="clear",
            reason="问题包含可直接检索的研究目标",
        )


def clarification_for(screening: QuestionScreening) -> ClarificationRequest | None:
    """Translate a deterministic ambiguity rule into an actionable follow-up."""
    if screening.decision != "ambiguous" or screening.rule_id is None:
        return None
    requests = {
        "unresolved_reference": ClarificationRequest(
            rule_id="unresolved_reference",
            prompt="你指的是哪一篇论文或哪一个方法？",
            required_information=("论文标题、作者、arXiv ID 或明确的方法名称",),
        ),
        "unscoped_superlative": ClarificationRequest(
            rule_id="unscoped_superlative",
            prompt="你希望针对什么任务，并用哪些标准判断“最好”？",
            required_information=("目标任务或使用场景", "评价标准或优先级"),
        ),
        "underspecified_selection": ClarificationRequest(
            rule_id="underspecified_selection",
            prompt="你准备把这个方法用于什么目标，有哪些关键约束？",
            required_information=("使用目标", "数据、成本、延迟等关键约束"),
        ),
    }
    return requests.get(
        screening.rule_id,
        ClarificationRequest(
            rule_id=screening.rule_id,
            prompt="请补充能够明确研究范围的信息。",
            required_information=("研究对象、目标或评价标准",),
        ),
    )


def build_clarified_question(original_question: str, response: str) -> str:
    """Build a self-contained question while preserving clarification provenance."""
    return CLARIFIED_QUESTION_TEMPLATE.format(
        original_question=" ".join(original_question.split()),
        clarification_response=" ".join(response.split()),
    )


def _resolves_reference(response: str | None) -> bool:
    if response is None:
        return False
    generic = {"这篇论文", "那篇论文", "这个方法", "那个方法", "刚才那个", "前面那个"}
    return response not in generic and len(response) >= 3


def _has_unresolved_reference(question: str) -> bool:
    return bool(
        _UNRESOLVED_REFERENCE.search(question)
        or _UNRESOLVED_DEICTIC_REFERENCE.search(question)
    )


def _adds_decision_scope(response: str | None) -> bool:
    return response is not None and len(response) >= 5
