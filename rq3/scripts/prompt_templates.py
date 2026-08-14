#!/usr/bin/env python3
"""Shared prompt templates for the RQ3 explanation experiments."""

import textwrap


def build_explanation_prompt(group_logs: str, external_info: str) -> str:
    """Build the common baseline/RAG explanation prompt."""
    return textwrap.dedent(
        f"""
        You are given a group of contiguous system log lines from one case.
        You may also be given external information relevant to this case.

        Please explain what happened in this log group.

        Requirements:
        - Use the logs as the primary evidence.
        - Use the external information only when it is clearly relevant.
        - If the logs and external information conflict, trust the logs.
        - If there is not enough evidence for a field, say that the information is unclear.
        - Focus on the overall event or events represented by the whole log group.

        Log group:
        {group_logs}

        External information:
        {external_info}

        Please answer using this format:

        Meaning:
        Cause:
        Context:
        Impact:
        Solution:

        Dimension guidance:
        - Meaning explains the meaning of a log message.
        - Cause identifies the likely cause of the observed event.
        - Context describes the circumstances or execution scenarios under which the log message is emitted.
        - Impact estimates the impact of a log message.
        - Solution suggests possible remedies or evidence-supported follow-up actions.
        """
    ).strip()


## criteria for llm-as-a-judge evaluation
CRITERIA = """
1. Correctness: Is the explanation supported by the log evidence and does it avoid overclaiming the root cause?

- 5/5: All key claims are directly supported by the logs or clearly relevant external information; uncertainty is stated when evidence is insufficient; no unsupported root-cause claims are made.
- 4/5: Mostly evidence-supported, with only minor imprecision or weakly supported wording that does not materially change the interpretation.
- 3/5: Partially supported, but includes some unsupported assumptions, missed conflicts, or overconfident causal claims.
- 2/5: Contains major unsupported or contradicted claims that could mislead the operator about what happened or why.
- 1/5: Largely fabricated, contradicts the logs, or asserts a root cause with no meaningful evidence.

2. Completeness: Does the explanation cover the main event, relevant context, operational impact, and next diagnostic steps?

- 5/5: Covers the main event, likely cause or uncertainty, relevant context, operational impact, and evidence-supported follow-up actions.
- 4/5: Covers most important elements, with only minor omissions that do not prevent understanding the incident.
- 3/5: Covers the main event but misses one or more important elements such as context, impact, uncertainty, or follow-up actions.
- 2/5: Omits several important elements, leaving the incident only weakly explained.
- 1/5: Fails to identify the main event or provides almost no useful coverage of the incident.

3. Helpfulness: Does the explanation help an operator understand the incident and decide what to inspect next?

- 5/5: Clearly distinguishes important signals from background details, explains their operational meaning, and gives practical next inspection steps.
- 4/5: Generally useful for operator understanding, with minor gaps in prioritization or follow-up guidance.
- 3/5: Somewhat useful, but the operator would still need substantial interpretation to understand the incident or decide what to inspect.
- 2/5: Provides limited operational value and gives vague, impractical, or poorly prioritized guidance.
- 1/5: Does not help the operator understand the incident and may increase confusion.

4. Specificity: Does the explanation use concrete log signals rather than generic language?

- 5/5: Uses concrete evidence such as log messages, error codes, component names, timestamps, state changes, repeated patterns, or affected resources.
- 4/5: Refers to relevant log signals, with only minor generic phrasing or missing details.
- 3/5: Mixes some concrete signals with generic statements that could apply to many incidents.
- 2/5: Mostly generic, with few concrete references to the actual logs.
- 1/5: Provides boilerplate language with little or no connection to the specific log group.
"""
