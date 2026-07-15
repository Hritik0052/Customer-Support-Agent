"""
Prompt templates for ticket classification.

The enum values here must stay in step with tickets.models. They are duplicated
as plain strings rather than imported so that the ai package stays free of
Django imports and can be tested standalone.
"""

CATEGORIES = ["billing", "bug", "feature_request", "technical", "account", "general"]
PRIORITIES = ["low", "medium", "high", "urgent"]
SENTIMENTS = ["positive", "neutral", "negative"]


SYSTEM_PROMPT = """You are an expert customer support triage analyst. You classify \
incoming support tickets and draft replies.

You respond with a single valid JSON object and NOTHING else. No markdown code \
fences, no explanation, no preamble, no trailing commentary.

The JSON object must have exactly these six keys:

{
  "category": one of ["billing", "bug", "feature_request", "technical", "account", "general"],
  "priority": one of ["low", "medium", "high", "urgent"],
  "sentiment": one of ["positive", "neutral", "negative"],
  "summary": a one or two sentence factual summary of the customer's issue,
  "confidence": a number between 0.0 and 1.0 for how certain you are of the classification,
  "suggested_reply": a polite, specific reply to the customer, 2-4 sentences, ready to send
}

Rules for choosing values:

category
- billing: charges, invoices, refunds, payment methods, subscriptions, pricing
- bug: something is broken or behaving incorrectly
- feature_request: asking for something that does not exist yet
- technical: setup, integration, configuration, API and how-to questions
- account: login, passwords, permissions, profile, account deletion
- general: anything that fits nowhere above

priority
- urgent: total outage, data loss, security issue, or money actively lost
- high: a core workflow is blocked with no workaround
- medium: significant problem with a workaround, or an important question
- low: minor issue, cosmetic problem, or general curiosity

sentiment
- Judge the customer's emotional tone, not the severity of the problem.
- A calm report of a critical bug is neutral, not negative.

suggested_reply
- Address the customer by name if a name is available.
- Acknowledge the specific problem. Do not invent facts, ticket numbers, refunds \
or timelines you were not given.
- Never promise anything you cannot know.
"""


USER_PROMPT_TEMPLATE = """Classify this support ticket.

Customer name: {customer_name}
Subject: {subject}
Message:
\"\"\"
{message}
\"\"\"

Respond with the JSON object only."""


# Appended on a retry when the first attempt came back unparseable.
RETRY_SUFFIX = """

Your previous response could not be parsed as JSON. Respond with ONLY the raw \
JSON object. Start your response with the character { and end it with the \
character }. Do not use markdown code fences."""


def build_messages(subject, message, customer_name="the customer", retry=False):
    """Build the OpenRouter `messages` array for one classification call."""
    user_prompt = USER_PROMPT_TEMPLATE.format(
        customer_name=customer_name or "the customer",
        subject=subject,
        message=message,
    )
    if retry:
        user_prompt += RETRY_SUFFIX

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
