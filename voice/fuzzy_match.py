
"""
Given a raw transcript, find the best-matching command from a dictionary using
token-aware fuzzy matching that tolerates mishearing ("eskalate" -> "escalate")
and Hinglish code-switching ("isko DJB ko escalate kar do").

Returns a decision:
  - "act"     (high confidence)     -> execute immediately
  - "clarify" (medium confidence)   -> ask "did you mean X or Y?"
  - "repeat"  (low confidence)      -> ask user to repeat
"""

import difflib
import re

HIGH_THRESHOLD   = 0.82   # >= -> act
MEDIUM_THRESHOLD = 0.55   # >= -> clarify (between medium and high)
# < MEDIUM_THRESHOLD -> repeat


def _normalize(text):
    text = (text or "").lower().strip()
    text = re.sub(r"[^\w\s]", " ", text)     # strip punctuation
    text = re.sub(r"\s+", " ", text)
    return text


def _phrase_score(transcript, phrase):
    """Score how well `phrase` appears within `transcript`.

    Combines:
      - whole-string similarity (difflib ratio)
      - substring bonus (phrase keywords present as tokens)
    Handles Hinglish: if the key action word appears anywhere, score high even
    if surrounded by other-language filler words.
    """
    t = _normalize(transcript)
    p = _normalize(phrase)
    if not t or not p:
        return 0.0

    # 1. direct substring -> very strong signal
    if p in t:
        return 1.0

    # 2. token overlap: how many phrase tokens appear (fuzzily) in transcript
    t_tokens = t.split()
    p_tokens = p.split()
    matched = 0
    for pt in p_tokens:
        best = max((difflib.SequenceMatcher(None, pt, tt).ratio() for tt in t_tokens), default=0)
        if best >= 0.8:
            matched += 1
    token_score = matched / len(p_tokens) if p_tokens else 0

    # 3. whole-string fuzzy ratio (catches single-word mishearing)
    ratio = difflib.SequenceMatcher(None, t, p).ratio()

    # weighted blend — token overlap matters most for Hinglish
    return max(token_score * 0.9 + ratio * 0.1, ratio)


def match_command(transcript, commands):
    """
    Returns dict:
      {
        "decision": "act" | "clarify" | "repeat",
        "best": <command or None>,
        "score": float,
        "alternatives": [<command>, ...]   # for clarify
      }
    """
    scored = []
    for cmd in commands:
        phrases = cmd.get("phrases_en", []) + cmd.get("phrases_hi", [])
        best_phrase_score = max((_phrase_score(transcript, ph) for ph in phrases), default=0)
        scored.append((best_phrase_score, cmd))

    scored.sort(key=lambda x: x[0], reverse=True)
    if not scored:
        return {"decision": "repeat", "best": None, "score": 0, "alternatives": []}

    top_score, top_cmd = scored[0]
    second_score, second_cmd = scored[1] if len(scored) > 1 else (0, None)

    if top_score >= HIGH_THRESHOLD:
        # If two commands are near-tied and both high, ask to clarify to be safe
        if second_cmd and (top_score - second_score) < 0.08:
            return {"decision": "clarify", "best": top_cmd, "score": top_score,
                    "alternatives": [top_cmd, second_cmd]}
        return {"decision": "act", "best": top_cmd, "score": top_score, "alternatives": []}

    if top_score >= MEDIUM_THRESHOLD:
        alts = [top_cmd]
        if second_cmd and second_score >= MEDIUM_THRESHOLD:
            alts.append(second_cmd)
        return {"decision": "clarify", "best": top_cmd, "score": top_score, "alternatives": alts}

    return {"decision": "repeat", "best": None, "score": top_score, "alternatives": []}