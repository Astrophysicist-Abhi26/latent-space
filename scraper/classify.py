"""
Turns one raw posting into the features the site filters and ranks on.

  topics   sub-field ids from taxonomy.py
  kind     phd | internship | fellowship | technician | scientist | other | postdoc | faculty
           (phd and student posts are recognised so the pipeline can drop them)
  sector   academic | industry | ai-bio | public-health | nonprofit
  lab      wet | hybrid | dry | unknown
  coding   True when the role needs substantial programming
  level    junior | mid | senior
  phd      True when a doctorate is asked for
  visa     sponsors | no-sponsorship | unknown
  relevant False for off-topic or non-research posts (sales, software, finance ...)

Everything is keyword based and explainable; the optional Claude step
(llm_fit.py) can overrule lab / coding / visa for the best matches.
"""

import re

import taxonomy as T
from geo import COUNTRIES, locate

KINDS = {"phd": "PhD position", "internship": "Internship / summer project", "fellowship": "Fellowship / funding",
         "technician": "Research assistant / project role", "scientist": "Scientist (research / industry)",
         "other": "Other", "postdoc": "Postdoc", "faculty": "Faculty / group leader"}
import os as _os, yaml as _yaml
SITE = _yaml.safe_load(open(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "site.yaml"), encoding="utf-8"))
DROP_KINDS = set(SITE.get("drop_kinds") or [])
MASTERS_OK = re.compile(r"\b(m\.?\s?sc|m\.?\s?s\.?|master'?s|m\.?\s?tech|bachelor'?s|b\.?\s?sc)\b", re.I)
SECTORS = {"ai-lab": "Frontier AI lab", "tech": "Tech & AI company", "quant": "Quant & trading firm",
           "academic": "Academia & institutes", "industry": "Industry", "ai-bio": "AI × biology company",
           "public-health": "Public health agency", "nonprofit": "Non-profit / foundation"}
LABS = {"wet": "Wet lab", "hybrid": "Wet + dry", "dry": "Computational", "unknown": "Not stated"}
VISA = {"sponsors": "Visa sponsorship mentioned", "no-sponsorship": "No sponsorship", "unknown": "Not stated"}
LEVELS = {"junior": "Junior", "mid": "Mid-level", "senior": "Senior"}


def _rx(*parts, flags=re.I):
    return re.compile("|".join(parts), flags)


# ── what kind of position ──────────────────────────────────────────────────
PHD_TITLE = _rx(r"\bph\.?\s?d\.?\s*(student|candidate|position|studentship|scholarship|project|programme|program|researcher|fellow(ship)?)s?\b",
                r"\bdoctoral (candidate|student|researcher|position|scholarship|programme|fellowship)s?\b",
                r"\bstudentships?\b", r"\b(doktorand|doctorant|promovend)\w*", r"\bdphil\b",
                r"^ph\.?\s?d\.?\b", r"\bph\.?\s?d\.? (in|on)\b")
STUDENT_TITLE = _rx(r"\bintern(ship)?s?\b", r"\bmaster'?s? (thesis|student|project|position)\b", r"\bundergraduate\b",
                    r"\bsummer (student|school)\b", r"\btrainee(ship)?s?\b", r"\bco-?op\b", r"\bapprentice\w*",
                    r"\bwinter (school|internship)\b", r"\bpraktik\w*")
POSTDOC = _rx(r"\bpost-?\s?docs?\b", r"\bpostdoctoral\b", r"\bpost doctoral\b", r"\bproject scientist\b",
              r"\bwissenschaftliche[rn]? mitarbeiter\w*", r"\bresearch fellow\b", r"\bpostdoktor\w*", r"\bpostdoctorant\b")
FELLOWSHIP = _rx(r"\bfellowships?\b", r"\bcall for (applications|proposals)\b", r"\bgrants? (programme|program|call)\b",
                 r"\bscholarships? for (postdoc|researchers)")
FACULTY = _rx(r"\b(assistant|associate|full|adjunct)?\s*professor(ship)?\b", r"\blecturer\b", r"\btenure[- ]track\b",
              r"\b(junior |senior |independent )?group leaders?\b", r"\bprincipal investigator\b", r"\bhead of (lab|group)\b",
              r"\bfaculty\b")
TECHNICIAN = _rx(r"\b(lab(oratory)? |research |senior )?technicians?\b", r"\btechnical (officer|assistant|specialist)\b",
                 r"\bresearch (assistant|technician)\b", r"\bJRF\b|\bjunior research fellow\b", r"\bproject (associate|assistant)\b",
                 r"\blab(oratory)? (assistant|attendant|operations associate)\b", r"\bassociate scientist\b",
                 r"\blab(oratory)? specialist\b", r"\bresearch associate i\b|\bresearch associate 1\b")
RESEARCH_ASSOCIATE = _rx(r"\bresearch associate\b")
SRF = _rx(r"\b(SRF|senior research fellow)\b")
SCIENTIST = _rx(r"\bscientists?\b", r"\bmicrobiologists?\b", r"\bbiologists?\b", r"\bvirologists?\b", r"\bimmunologists?\b",
                r"\bbioinformaticians?\b", r"\bresearchers?\b", r"\bresearch engineer\b", r"\bmember of (technical|scientific) staff\b",
                r"\bwissenschaftler\w*", r"\bchercheur\w*")

# ── posts that are not research jobs (dropped) ─────────────────────────────
NOT_RESEARCH = _rx(
    r"\baccount(ant|ing|s| executive| manager)\b", r"\bsales\b", r"\bmarketing\b", r"\brecruit(er|ing|ment (partner|coordinator))\b",
    r"\btalent (acquisition|partner)\b", r"\bhuman resources\b", r"\bHR (business|manager|partner|generalist)\b",
    r"\blegal\b", r"\bcounsel\b", r"\bparalegal\b", r"\bfinanc(e|ial)\b", r"\bpayroll\b", r"\bprocurement\b",
    r"\bfacilities (manager|coordinator|technician)\b", r"\breceptionist\b", r"\bexecutive assistant\b",
    r"\badministrat(ive|or)\b", r"\boffice manager\b", r"\bcommunications?\b", r"\b(graphic|product|ux|ui) designer\b",
    r"\bsoftware engineer\w*\b", r"\bfront-?end\b", r"\bback-?end\b", r"\bfull[- ]stack\b", r"\bdevops\b",
    r"\bsite reliability\b", r"\bSRE\b", r"\bsecurity engineer\b", r"\bdata engineer\b", r"\binfrastructure engineer\b",
    r"\bproduct manager\b", r"\bprogram(me)? manager\b", r"\bcustomer (success|support)\b", r"\bsupport engineer\b",
    r"\bnurse\b", r"\bphysician\b", r"\bclinical fellow\b", r"\bmedical officer\b", r"\bdriver\b", r"\bchef\b|\bcook\b",
    r"\bjanitor\b", r"\bhousekeep\w*", r"\bteacher\b", r"\bteaching assistant\b", r"\blibrarian\b", r"\bpolicy\b",
    r"\bgovernment affairs\b", r"\bbusiness development\b", r"\binvestor relations\b", r"\bcopywriter\b",
    r"\bevent(s)? (manager|coordinator)\b", r"\bit (support|technician|manager)\b", r"\bnetwork engineer\b")

# ── wet / dry / coding ─────────────────────────────────────────────────────
STRONG_WET = [re.compile(p, re.I) for p in (r"wet[- ]lab", r"\bbench(top)?\b", r"hands-on (bench|lab|laboratory|experiment)\w*")]
WET = [re.compile(p, re.I) for p in ( r"laboratory (work|experience|skills|techniques)",
    r"(cell|tissue|bacterial) culture", r"cultur(e|ing) (of )?(bacteria|cells|microorganisms|isolates)", r"aseptic",
    r"\bBSL-?[23]\b|containment level [23]", r"\b(q|RT-?q?)PCR\b", r"\bcloning\b", r"western blot", r"\bELISA\b",
    r"flow cytometr", r"microscop", r"assay development", r"protein (expression|purification)", r"in vivo",
    r"animal (work|models|handling)", r"\bmice\b|\bmouse\b", r"zebrafish", r"sample (processing|preparation)",
    r"susceptibility testing", r"minimum inhibitory", r"\bfermentation\b", r"pipett", r"liquid[- ]handl",
    r"\bisolates?\b", r"library prep", r"\bCRISPR\b", r"experimental (work|biology|design)", r"\bexperiments?\b",
    r"laborator(y|ies)", r"\bplate[- ]based\b", r"\bmicrobiological techniques\b")]
DRY = [re.compile(p, re.I) for p in (
    r"\bcomputational\b", r"bioinformatic", r"machine learning", r"deep learning", r"data scien",
    r"\bsoftware\b", r"\bPython\b", r"\bprogramming\b", r"\bpipelines?\b", r"\bmodel(l)?ing\b", r"statistical genetics",
    r"\bin silico\b", r"\balgorithms?\b", r"\bcloud\b", r"\bPyTorch\b|TensorFlow|\bJAX\b", r"\bLLMs?\b",
    r"\bengineer(ing)?\b", r"\bcode\b", r"\bdatabases?\b")]
DRY_TITLE = _rx(r"machine learning", r"\bML\b", r"\bAI\b (scientist|engineer|researcher)", r"computational", r"bioinformatic",
                r"data scien", r"software", r"research engineer", r"\bengineer\b", r"statistic", r"modell?er",
                r"forward deployed", r"member of technical staff", r"\bcomputational\b", r"\bin silico\b")
WET_TITLE = _rx(r"wet[- ]lab", r"\bbench\b", r"\blab(oratory)?\b", r"experimental", r"\bin vitro\b", r"\bin vivo\b",
                r"(?<!computational )(?<!systems )\b(micro)?biologists?\b", r"\bvirologist", r"phage", r"\bculture",
                r"cell (biology|culture)", r"microbiolog", r"assay", r"technician", r"research associate", r"biochem",
                r"molecular biolog", r"\bcellular\b", r"pharmacolog")
CODING_REQ = _rx(r"(proficien\w+|fluen\w+|strong|expert\w*|extensive|solid|advanced)\s+(skills?\s+)?(in|with)?\s*"
                 r"(python|programming|software|coding|pytorch|tensorflow|jax|c\+\+|rust|machine learning)",
                 r"software engineering (experience|skills|practices)", r"production[- ](quality )?code",
                 r"\bML engineering\b", r"machine learning engineering", r"build and maintain (the )?(engineering )?infrastructure",
                 r"(\d\+?|several|multiple) years of (experience )?(applying|in|with) (ml|machine learning|software)")

# ── seniority, PhD, visa ───────────────────────────────────────────────────
SENIOR_TITLE = _rx(r"\b(senior|sr\.?|principal|staff|lead|head|director|chief|vp|vice president|manager|associate director)\b")
JUNIOR_TITLE = _rx(r"\b(junior|entry|graduate|scientist i\b|scientist 1\b|associate scientist|research associate)\b")
YEARS = re.compile(r"(\d{1,2})\+?\s*(?:-\s*\d{1,2}\s*)?(?:years|yrs)\b[^.]{0,60}?(post-?(?:doc\w*|ph\.?d)|experience)", re.I)
PHD_REQ = _rx(r"\bph\.?\s?d\b", r"\bdoctoral degree\b", r"\bdoctorate\b", r"\bpostdoctoral\b", r"\bdphil\b")
VISA_REFUSED = _rx(r"(unable|not able|cannot|can ?not|will not|won'?t|do(es)? not|don'?t|are not able) to "
                   r"(provide|offer|support|sponsor)\s+(visa |work |employment )?(sponsorship|visas?)",
                   r"(unable|not able|cannot|can ?not|will not|won'?t|do(es)? not|don'?t) sponsor\b",
                   r"\bno (visa )?sponsorship\b", r"sponsorship (is )?not (available|provided|offered|possible)",
                   r"without (the need for )?(visa |current or future |employer )?sponsorship")
VISA_RESTRICTED = _rx(r"must (already )?(be|have) (legally )?(eligible|authori[sz]ed) to work",
                      r"work authori[sz]ation (is )?required", r"\b(us|u\.s\.) (citizens?|citizenship) (only|required|is required)\b",
                      r"security clearance", r"(eu|eea) (citizenship|nationality|nationals?) (is )?(required|only|mandatory)",
                      r"only (eu|eea) (citizens|nationals)")
VISA_YES = _rx(r"visa sponsorship (is |may be )?(available|provided|offered|possible)", r"we (do |can |will )?sponsor (work )?visas?",
               r"eligible for (visa |skilled worker )?sponsorship", r"sponsor(ship)? (for )?(a |your )?(skilled worker|work) visa",
               r"skilled worker (visa|route)", r"global talent visa", r"relocation (support|package|assistance|allowance)",
               r"international (applicants|candidates) (are )?(welcome|encouraged)", r"visa (support|assistance)",
               r"\bblue card\b")

# ── sector from the organisation ───────────────────────────────────────────
PUBLIC_HEALTH = _rx(r"\bWorld Health Organi[sz]ation\b|\bWHO\b", r"\bCDC\b|Centers? for Disease Control", r"\bUKHSA\b",
                    r"\bECDC\b", r"\bRIVM\b", r"Robert Koch", r"Statens Serum", r"\bNCDC\b", r"public health (agency|england|scotland|wales)",
                    r"Sant[ée] publique", r"\bInstitute of Public Health\b")
NONPROFIT = _rx(r"\bGARDP\b", r"\bDNDi\b", r"\bPATH\b", r"\bIVI\b|International Vaccine Institute", r"\bWellcome\b(?! Sanger)",
                r"\bGates Foundation\b|Gates MRI", r"\bCARB-X\b", r"\bFIND\b", r"\bMSF\b|M[ée]decins Sans Fronti[èe]res",
                r"\bfoundation\b", r"Phare Bio", r"\bnon-?profit\b")
ACADEMIC = _rx(r"universit", r"universit[äé]t|universiteit|universidad|università|universidade|uniwersytet", r"\bcollege\b",
               r"\binstitut", r"\bcent(re|er)\b", r"\bhospital\b|\bklinikum\b|\bUMC\b|medical cent|charit[ée]|\bNHS\b",
               r"\bschool of\b", r"\bacademy\b", r"\bEMBL\b|Max Planck|Helmholtz|Leibniz|Fraunhofer|Pasteur|\bCNRS\b|\bINSERM\b",
               r"\bETH\b|\bEPFL\b|\bKTH\b|\bDTU\b", r"\bCSIC\b|\bCNR\b", r"\bICMR\b|\bCSIR\b|\bDBT\b|\bBRIC\b|\bIIT\b|\bIISER\b|\bAIIMS\b",
               r"\blaborator(y|ies)\b")
COMPANY = _rx(r"\b(GmbH|Ltd\.?|Limited|Inc\.?|LLC|S\.?A\.?S?|B\.?V\.?|AG|A/S|AB|Pvt\.?|plc|Corp(oration)?\.?|SE|S\.?r\.?l\.?)\b",
              r"\btherapeutics\b|\bbiosciences?\b|\bpharma(ceuticals?)?\b|\bbiotech\b|\bdiagnostics\b|\bgenomics inc\b")
AI_CUES = _rx(r"machine learning", r"\bAI\b", r"artificial intelligence", r"deep learning", r"foundation model",
              r"generative", r"autonomous (lab|science)", r"lab automation", r"closed[- ]loop", r"\bLLMs?\b")


NO_PHD = re.compile(r"\b(don'?t|do not|doesn'?t|no|not|without)\b[^.]{0,25}\bph\.?\s?d\b|\bph\.?\s?d\.?\b[^.]{0,15}\bnot (required|necessary|needed)", re.I)
AI_FELLOW = re.compile(r"\bfellows?\b|\bfellowship\b|\bresidency\b|\bresident\b", re.I)


def kind_of(title, text, hint=None, country="", sector=""):
    t = title or ""
    if SITE.get("domain") == "ai" and AI_FELLOW.search(t) and not PHD_TITLE.search(t) and not STUDENT_TITLE.search(t):
        return "fellowship"
    if PHD_TITLE.search(t) and not POSTDOC.search(t):
        return "phd"
    if STUDENT_TITLE.search(t) and not POSTDOC.search(t):
        return "internship"
    if re.search(r"\b(JRF|junior research fellow(ship)?)\b", t, re.I):
        return "technician"                       # Indian pre-PhD fellowship
    if SRF.search(t) and country == "IN":
        return "technician"
    if POSTDOC.search(t):
        return "postdoc"
    if FACULTY.search(t):
        return "faculty"
    if FELLOWSHIP.search(t) and not re.search(r"\bfellows?\b(?!hip)", t, re.I):
        return "fellowship"
    if RESEARCH_ASSOCIATE.search(t):
        # India: RA-I/II/III all require a PhD. UK/EU academia: a postdoc post.
        # US and industry (incl. "Research Associate I/II"): a BSc/MSc bench role.
        if country == "IN":
            return "postdoc"
        if re.search(r"\bresearch associate[- ]?(i{1,3}|[123])\b", t, re.I) or sector in ("industry", "ai-bio"):
            return "technician"
        if sector == "academic" and country not in ("US", "CA"):
            return "postdoc"
        return "technician"
    if SRF.search(t):
        return "technician" if country == "IN" else "postdoc"
    if TECHNICIAN.search(t):
        return "technician"
    if hint in ("postdoc", "fellowship", "phd"):
        return hint                               # e.g. EURAXESS "Recognised Researcher (R2)"
    if SCIENTIST.search(t):
        return "scientist"
    if hint in KINDS:
        return hint
    if POSTDOC.search(text or "") and len(t) < 90:
        return "postdoc"
    return "other"


def sector_of(org, hint=None, text=""):
    o = org or ""
    if PUBLIC_HEALTH.search(o):
        return "public-health"
    if hint in ("ai-bio", "ai-lab", "tech", "quant"):
        return hint
    if hint in ("industry", "biotech", "pharma"):
        return "ai-bio" if AI_CUES.search(text or "") and hint == "biotech" else "industry"
    if hint == "nonprofit" or (NONPROFIT.search(o) and not ACADEMIC.search(o)):
        return "nonprofit"
    if hint == "academic":
        return "academic"
    if COMPANY.search(o) and not re.search(r"universit|institut|hospital|\bcent(re|er)\b", o, re.I):
        return "industry"
    return "academic"


def lab_of(title, text):
    t, d = title or "", text or ""
    wet = sum(1 for rx in WET if rx.search(d)) + 2 * sum(1 for rx in STRONG_WET if rx.search(d))
    dry = sum(1 for rx in DRY if rx.search(d))
    if WET_TITLE.search(t):
        wet += 3
    if DRY_TITLE.search(t):
        dry += 3
    if wet >= 3 and dry >= 3:
        return "hybrid" if min(wet, dry) >= 0.5 * max(wet, dry) else ("wet" if wet > dry else "dry")
    if wet >= 2 and wet > dry:
        return "wet"
    if dry >= 2 and dry > wet:
        return "dry"
    return "unknown"


def coding_of(title, text, lab):
    if DRY_TITLE.search(title or ""):
        return True
    if lab == "wet":
        return False
    return bool(CODING_REQ.search(text or ""))


def level_of(title, text, kind):
    years = [int(m.group(1)) for m in YEARS.finditer(text or "") if int(m.group(1)) < 30]
    post_phd = [int(m.group(1)) for m in YEARS.finditer(text or "")
                if re.search(r"post", m.group(2), re.I) and int(m.group(1)) < 30]
    if SENIOR_TITLE.search(title or "") and not re.search(r"senior (project associate|research fellow|technician)",
                                                            title or "", re.I):
        return "senior"
    if (post_phd and max(post_phd) >= 4) or (years and max(years) >= 7):
        return "senior"
    if kind in ("technician", "internship", "phd") or (JUNIOR_TITLE.search(title or "") and kind != "postdoc"):
        return "junior"
    return "mid"


def visa_of(text):
    """An explicit refusal beats everything; a welcome beats a generic work-permit line."""
    t = text or ""
    if VISA_REFUSED.search(t):
        return "no-sponsorship"
    if VISA_YES.search(t):
        return "sponsors"
    if VISA_RESTRICTED.search(t):
        return "no-sponsorship"
    return "unknown"


AI_CORE = ("ml", "ds", "quant")          # domain "ai": at least one of these must be present
DOMAIN = SITE.get("domain", "bio")


def relevant(title, topics, keep_untagged=False, company=False):
    if DOMAIN == "ai":
        if NOT_RESEARCH.search(title or "") and not re.search(r"\b(ML|AI)\b|machine learning|scien|research|data|quant", title or "", re.I):
            return False
        return any(t.split(".")[0] in AI_CORE for t in topics) or (keep_untagged and not topics)
    if NOT_RESEARCH.search(title or "") and not re.search(r"scien|biolog|lab|research", title or "", re.I):
        return False
    if re.search(r"\bsoftware engineer|\bdata engineer|\bdevops\b|\bfull[- ]stack|\bIT (department|dept|support)\b|\bengineer trainee\b", title or "", re.I):
        return False
    core = [t for t in topics if t not in T.CONTEXT_ONLY or (company and t in T.COMPANY_CORE)]
    return bool(core) or keep_untagged


def classify(job):
    """Adds the feature fields to a normalised job dict in place and returns it."""
    title = job.get("title", "")
    text = " ".join(x for x in (job.get("description", ""), job.get("fields_text", "")) if x)
    hints = job.get("hints") or {}
    tags = T.tag(title, text[:6000])
    topics = [sid for sid, _ in tags]
    if not topics and hints.get("topics"):
        topics = list(hints["topics"])
    where = locate(job.get("location", ""), job.get("org", ""), title)
    if not where["country"] and hints.get("country") in COUNTRIES:
        cc = hints["country"]
        where = {"country": cc, "region": COUNTRIES[cc][1], "remote": where["remote"]}
    sector = sector_of(job.get("org", ""), hints.get("sector"), title + " " + text[:3000])
    kind = kind_of(title, text, hints.get("kind"), where["country"], sector)
    lab = hints.get("lab") or lab_of(title, text)
    job.update(
        topics=topics,
        fields=sorted({T.field_of(t) for t in topics}),
        country=where["country"],
        region=where["region"],
        remote=where["remote"],
        sector=sector,
        kind=kind,
        lab=lab,
        coding=coding_of(title, text, lab),
        level=level_of(title, text, kind),
        phd=bool(PHD_REQ.search(title + " " + text)),
        needs_phd=kind in ("scientist", "technician", "other", "postdoc", "faculty") and bool(PHD_REQ.search(title + " " + text))
                  and not MASTERS_OK.search(title + " " + text) and not NO_PHD.search(title + " " + text),
        visa=visa_of(text),
        relevant=relevant(title, topics, hints.get("keep_untagged", False),
                          hints.get("sector") in ("ai-bio", "biotech", "pharma")) and kind not in DROP_KINDS,
    )
    return job
