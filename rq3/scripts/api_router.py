#!/usr/bin/env python3
"""Shared Azure OpenAI v1 Responses API client for the RQ3 experiments."""

import os


def get_chat_completion(messages: list[dict[str, str]]) -> str:
    """Run one Responses API request using the configured Azure deployment."""
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "The openai package is required to run the RQ3 API calls"
        ) from exc

    client = OpenAI(
        base_url=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
    )
    response = client.responses.create(
        model=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5.6-sol"),
        input=messages,
        reasoning={"effort": "medium"},
        max_output_tokens=20000,
    )
    content = response.output_text
    if not content:
        raise RuntimeError("Azure OpenAI returned empty message content")
    return content
