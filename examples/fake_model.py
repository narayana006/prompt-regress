"""A stand-in for a real model so the examples run offline.

In your own project this module would call whatever model you use and return
its text answer. The only contract is: take the prompt string, return a string.

`reply` behaves like yesterday's prompt. `reply_v2` simulates what happens
after someone "improves" the wording: one answer is rephrased harmlessly and
another silently stops returning JSON.
"""

import json


def reply(prompt: str) -> str:
    text = prompt.lower()
    if "extract" in text:
        return json.dumps({"order_id": "A-1042", "intent": "refund", "urgent": False})
    if "refund" in text:
        return "You can request a refund within 30 days of purchase from the Orders page."
    if "capital of france" in text:
        return "Paris"
    return "Hello! How can I help you today?"


def reply_v2(prompt: str) -> str:
    text = prompt.lower()
    if "extract" in text:
        return "Sure! The order is A-1042 and the customer wants a refund."
    if "refund" in text:
        return "Refunds are available for 30 days after purchase. Open the Orders page to start one."
    return reply(prompt)


def judge(rubric: str, output: str, prompt: str) -> float:
    """A toy grader: the share of rubric keywords (words in CAPS) the answer
    mentions. A real judge would ask a grading model and return its score."""
    keywords = [word.strip(".,").lower() for word in rubric.split() if word.isupper()]
    if not keywords:
        return 1.0
    hits = sum(1 for word in keywords if word in output.lower())
    return hits / len(keywords)
