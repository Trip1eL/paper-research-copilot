"""High-precision deterministic question screening before research retrieval."""

import re

from paper_research_copilot.agent.models import QuestionScreening

_UNRESOLVED_REFERENCE = re.compile(
    r"(?:刚才|前面|上面|此前|之前|前文).{0,10}"
    r"(?:提到|讨论|说过|介绍).{0,10}(?:论文|文章|方法|工作|模型)"
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
        if _UNRESOLVED_REFERENCE.search(normalized):
            return QuestionScreening(
                decision="ambiguous",
                rule_id="unresolved_reference",
                reason="问题引用了当前请求中不存在的前文对象",
            )
        if _UNSCOPED_SUPERLATIVE.search(normalized):
            return QuestionScreening(
                decision="ambiguous",
                rule_id="unscoped_superlative",
                reason="问题要求判断最佳方案，但没有给出任务、数据集或评价标准",
            )
        if _UNDERSPECIFIED_SELECTION.search(normalized):
            return QuestionScreening(
                decision="ambiguous",
                rule_id="underspecified_selection",
                reason="问题要求选择论文方法，但没有给出使用目标或约束",
            )
        return QuestionScreening(
            decision="clear",
            reason="问题包含可直接检索的研究目标",
        )
