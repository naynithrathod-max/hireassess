"""
Scoring engine for the Standardized Hiring Assessment Platform.

Two scorers live here:

  rule_based_score()  - no API, no cost, no network. This is the default and
                        it is what the demo runs on.
  ai_assisted_score() - optional. Only used when an API key is present in the
                        environment. It pre-scores the written answer and a
                        human reviewer confirms or overrides it, which is the
                        "AI-assisted, human-reviewed" model from the blueprint.

The rest of the app only ever calls score_written(). It decides which of the
two to use, so switching the AI on or off never touches the application code.
"""

import os
import re

# Each rubric criterion is scored 0-5, then weighted into a 0-100 score.
RUBRIC_WEIGHTS = {
    "structure": 0.25,
    "specificity": 0.20,
    "clarity": 0.20,
    "coverage": 0.25,
    "falsifiability": 0.10,
}

FILLER = [
    "basically", "actually", "really", "very", "just", "quite", "sort of",
    "kind of", "i think", "i feel", "in my opinion", "obviously", "literally",
]

RECOMMENDATION_MARKERS = [
    "i recommend", "my recommendation", "recommend", "should", "my answer",
    "the chain should", "they should", "i would", "i'd advise", "advise",
    "do not", "don't", "yes,", "no,",
]

ORDERING_MARKERS = [
    "first", "second", "third", "finally", "because", "therefore", "however",
    "the reason", "this is because", "in addition", "moreover", "on the other hand",
]


def _sentences(text):
    parts = re.split(r"[.!?]+", text)
    return [p.strip() for p in parts if p.strip()]


def _words(text):
    return re.findall(r"[a-zA-Z'\-]+", text)


def _clamp(value, low=0.0, high=5.0):
    return max(low, min(high, value))


def _score_structure(text, lowered):
    """Does the answer lead with a recommendation and then order its reasoning?"""
    sents = _sentences(text)
    if not sents:
        return 0.0

    score = 0.0
    # A recommendation in the opening two sentences is the key signal.
    opening = " ".join(sents[:2]).lower()
    if any(m in opening for m in RECOMMENDATION_MARKERS):
        score += 2.5
    elif any(m in lowered for m in RECOMMENDATION_MARKERS):
        score += 1.0  # present, but buried

    # Ordered reasoning.
    markers_found = sum(1 for m in ORDERING_MARKERS if m in lowered)
    score += min(1.5, markers_found * 0.4)

    # Multi-paragraph or multi-part answers read as structured.
    if text.count("\n\n") >= 1 or len(sents) >= 6:
        score += 1.0

    return _clamp(score)


def _score_specificity(text, lowered):
    """Numbers and concrete nouns rather than generalities."""
    numbers = re.findall(r"\d+(?:\.\d+)?%?", text)
    score = min(3.0, len(numbers) * 0.6)

    # Reusing the figures given in the prompt is a strong signal.
    for given in ["18", "25", "8", "eight", "two"]:
        if given in lowered:
            score += 0.4

    return _clamp(score)


def _score_clarity(text, lowered):
    """Moderate sentence length, little filler, enough substance to judge."""
    sents = _sentences(text)
    words = _words(text)
    if not sents or not words:
        return 0.0

    avg_len = len(words) / len(sents)
    # 10-22 words a sentence reads cleanly; penalise either extreme.
    if 10 <= avg_len <= 22:
        score = 3.5
    elif 8 <= avg_len <= 28:
        score = 2.5
    else:
        score = 1.0

    filler_hits = sum(lowered.count(f) for f in FILLER)
    score -= min(1.5, filler_hits * 0.3)

    # Length discipline: the brief asked for 150-250 words.
    if 140 <= len(words) <= 270:
        score += 1.5
    elif 100 <= len(words) < 140 or 270 < len(words) <= 330:
        score += 0.75

    return _clamp(score)


def _score_coverage(lowered, terms):
    """Does the answer engage with the real tension in the case?"""
    hits = sum(1 for t in terms if t in lowered)
    return _clamp(hits * 0.8)


def _score_falsifiability(lowered, terms):
    """Does the candidate name evidence that would change their mind?"""
    hits = sum(1 for t in terms if t in lowered)
    return _clamp(hits * 1.2)


def rule_based_score(text, written_spec):
    """Score a written answer against the rubric with no external service."""
    text = (text or "").strip()
    lowered = text.lower()
    words = _words(text)

    if len(words) < 25:
        # Too short to assess against the rubric.
        breakdown = {k: 0.0 for k in RUBRIC_WEIGHTS}
        return {
            "score": 0.0,
            "breakdown": breakdown,
            "word_count": len(words),
            "engine": "rule-based",
            "note": "Answer too short to score against the rubric (under 25 words).",
        }

    breakdown = {
        "structure": round(_score_structure(text, lowered), 2),
        "specificity": round(_score_specificity(text, lowered), 2),
        "clarity": round(_score_clarity(text, lowered), 2),
        "coverage": round(_score_coverage(lowered, written_spec["coverage_terms"]), 2),
        "falsifiability": round(
            _score_falsifiability(lowered, written_spec["falsifiability_terms"]), 2
        ),
    }

    weighted = sum(breakdown[k] / 5.0 * RUBRIC_WEIGHTS[k] for k in RUBRIC_WEIGHTS)
    return {
        "score": round(weighted * 100, 1),
        "breakdown": breakdown,
        "word_count": len(words),
        "engine": "rule-based",
        "note": "",
    }


def ai_assisted_score(text, written_spec):
    """
    Optional AI pre-score. Returns None when no key is configured or the call
    fails, so the caller falls back to the rule-based score and the demo never
    depends on a paid or rate-limited service.
    """
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None

    try:
        import json
        import urllib.request

        criteria = "\n".join(f"- {k}: {v}" for k, v in written_spec["rubric"].items())
        instruction = (
            "You are scoring a candidate's written answer in a hiring assessment.\n"
            "Score each criterion from 0 to 5.\n\n"
            f"CRITERIA:\n{criteria}\n\n"
            f"CASE PROMPT:\n{written_spec['prompt']}\n\n"
            f"CANDIDATE ANSWER:\n{text}\n\n"
            'Reply with JSON only: {"structure":n,"specificity":n,"clarity":n,'
            '"coverage":n,"falsifiability":n,"comment":"one sentence"}'
        )

        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            "gemini-2.0-flash:generateContent"
        )
        payload = json.dumps(
            {"contents": [{"parts": [{"text": instruction}]}]}
        ).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": api_key,
            },
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        raw = data["candidates"][0]["content"]["parts"][0]["text"]
        match = re.search(r"\{.*\}", raw, re.S)
        if not match:
            return None
        parsed = json.loads(match.group(0))

        breakdown = {
            k: _clamp(float(parsed.get(k, 0))) for k in RUBRIC_WEIGHTS
        }
        weighted = sum(breakdown[k] / 5.0 * RUBRIC_WEIGHTS[k] for k in RUBRIC_WEIGHTS)
        return {
            "score": round(weighted * 100, 1),
            "breakdown": {k: round(v, 2) for k, v in breakdown.items()},
            "word_count": len(_words(text)),
            "engine": "ai-assisted (pending human review)",
            "note": str(parsed.get("comment", ""))[:300],
        }
    except Exception:
        # Any failure (no network, rate limit, bad response) falls back silently.
        return None


def score_written(text, written_spec):
    """Public entry point. Tries AI, falls back to rules."""
    result = ai_assisted_score(text, written_spec)
    if result is not None:
        return result
    return rule_based_score(text, written_spec)


def score_speed(elapsed_seconds, limit_seconds, answered_count, total_count):
    """
    Speed and working ability: how much of the paper was completed, and how
    efficiently. Finishing everything with time to spare scores highest;
    finishing fast by skipping questions does not.
    """
    if total_count == 0:
        return 0.0
    completion = answered_count / total_count
    if elapsed_seconds <= 0:
        pace = 1.0
    else:
        pace = _clamp(1.0 - (elapsed_seconds / max(limit_seconds, 1)), 0.0, 1.0)
    # Completion dominates; pace is the tie-breaker.
    return round((completion * 0.7 + pace * 0.3) * 100, 1)


def integrity_penalty(tab_switches):
    """
    Light proctoring signal. Each tab switch during the timed round costs a
    small amount, capped, and is always shown to the reviewer rather than
    silently applied.
    """
    return min(10.0, tab_switches * 2.5)
