"""
How close is a posting to the CV?  similarity(cv_text, job_texts) -> [0..1, ...]

A small TF-IDF cosine (words + word pairs, light stemming) with no dependencies, so it
runs anywhere and is fully testable. The raw cosine is scaled by CAP so that a strong
match reaches 1.0; profiles.yaml turns it into points (cv: 20 -> up to +20).
"""

import math
import re
from collections import Counter

CAP = 0.22          # a cosine of 0.22 or more counts as a perfect match

STOP = set("""a about above after again against all also am an and any are as at be because been before being
below between both but by can could did do does doing down during each either etc few for from further had has
have having he her here hers him his how i if in into is it its itself just may me might more most must my no nor
not now of off on once only or other our ours out over own per same shall she should so some such than that the
their theirs them then there these they this those through to too under until up upon us very via was we were what
when where which while who whom why will with within without would you your yours
ability able apply application applications applicant applicants candidate candidates career careers closing
contract date deadline department description duties employer employment experience full good group help including
interest interested job jobs join knowledge looking new offer offers opportunity opportunities part people please
position positions post posted provide required requirement requirements responsibilities role roles salary skills
start strong successful support team time understanding university well work working year years""".split())
_WORD = re.compile(r"[a-z][a-z0-9]+(?:-[a-z0-9]+)*")


def _stem(w):
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 4 and w.endswith("s") and not w.endswith(("ss", "us", "is")):
        return w[:-1]
    return w


def tokens(text):
    words = [_stem(w) for w in _WORD.findall((text or "").lower()) if w not in STOP and len(w) > 2]
    return words + [a + " " + b for a, b in zip(words, words[1:])]


def _vector(counts, idf):
    v = {t: (1 + math.log(c)) * idf.get(t, 0.0) for t, c in counts.items()}
    norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
    return {t: x / norm for t, x in v.items()}


def similarity(cv_text, job_texts):
    """Scaled similarity of each job text to the CV, in [0, 1], rounded to 2 places."""
    docs = [Counter(tokens(cv_text))] + [Counter(tokens(t)) for t in job_texts]
    n = len(docs)
    df = Counter()
    for d in docs:
        df.update(d.keys())
    idf = {t: math.log((n + 1) / (c + 1)) + 1.0 for t, c in df.items()}
    cv = _vector(docs[0], idf)
    out = []
    for d in docs[1:]:
        v = _vector(d, idf)
        cos = sum(x * cv.get(t, 0.0) for t, x in v.items())
        out.append(round(min(1.0, cos / CAP), 2))
    return out
