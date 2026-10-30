
import re
import math
from collections import Counter


# =====================================================
# BASIC HELPERS
# =====================================================

def get_value(data, key, default=""):
    """Safely read values from dictionaries or database rows."""
    try:
        value = data[key]
        return default if value is None else value
    except (KeyError, IndexError, TypeError):
        return default


def make_list(value):
    """Convert comma/semicolon separated values into a list."""
    if not value:
        return []

    if isinstance(value, (list, tuple, set)):
        return [
            str(item).strip().lower()
            for item in value if str(item).strip()
        ]

    return [
        item.strip().lower()
        for item in re.split(r"[,;]", str(value))
        if item.strip()
    ]


def normalize_text(value):
    return re.sub(r"\s+", " ", str(value or "").lower()).strip()


# =====================================================
# PROFILE MATCHING
# =====================================================

def skill_match(volunteer_skills, required_skills):
    volunteer = set(make_list(volunteer_skills))
    required = set(make_list(required_skills))

    if not volunteer or not required:
        return 0

    return len(volunteer & required) / len(required)


def interest_match(volunteer_interests, opportunity_cause):
    interests = set(make_list(volunteer_interests))
    cause = normalize_text(opportunity_cause)

    if not interests or not cause:
        return 0

    for interest in interests:
        if interest == cause or interest in cause or cause in interest:
            return 1

    return 0


def location_match(volunteer_location, opportunity_location):
    volunteer = normalize_text(volunteer_location)
    opportunity = normalize_text(opportunity_location)

    if not volunteer or not opportunity:
        return 0

    if volunteer == opportunity:
        return 1

    if "remote" in opportunity or "online" in opportunity:
        return 1

    return 0


def availability_match(volunteer_availability, opportunity_availability):
    volunteer = set(make_list(volunteer_availability))
    opportunity = set(make_list(opportunity_availability))

    if not volunteer or not opportunity:
        return 0

    return len(volunteer & opportunity) / len(opportunity)


def experience_match(volunteer_experience, required_experience):
    levels = {
        "beginner": 1,
        "basic": 1,
        "no experience": 1,
        "intermediate": 2,
        "moderate": 2,
        "advanced": 3,
        "expert": 4
    }

    volunteer = normalize_text(volunteer_experience)
    required = normalize_text(required_experience)

    if not volunteer or not required:
        return 0

    if required in ("", "any", "none", "not required"):
        return 1

    volunteer_level = levels.get(volunteer)
    required_level = levels.get(required)

    if volunteer_level is None or required_level is None:
        return 1 if volunteer == required else 0

    if volunteer_level >= required_level:
        return 1

    return volunteer_level / required_level


def mode_match(volunteer_mode, opportunity_mode):
    volunteer = normalize_text(volunteer_mode)
    opportunity = normalize_text(opportunity_mode)

    if not volunteer or not opportunity:
        return 0

    if volunteer == opportunity:
        return 1

    if volunteer == "hybrid" or opportunity == "hybrid":
        return 1

    return 0


# =====================================================
# PROFILE SCORE
# =====================================================

PROFILE_WEIGHTS = {
    "skills": 0.35,
    "interests": 0.15,
    "availability": 0.20,
    "location": 0.10,
    "experience": 0.10,
    "mode": 0.10
}


def get_profile_factors(volunteer, opportunity):
    """Calculate individual profile matching factors."""

    factors = {}

    volunteer_skills = get_value(volunteer, "skills")
    required_skills = get_value(opportunity, "required_skills")

    if volunteer_skills and required_skills:
        factors["skills"] = skill_match(
            volunteer_skills, required_skills
        )

    volunteer_interests = get_value(volunteer, "interests")
    cause = get_value(opportunity, "cause")

    if volunteer_interests and cause:
        factors["interests"] = interest_match(
            volunteer_interests, cause
        )

    volunteer_availability = get_value(volunteer, "availability")
    opportunity_availability = get_value(opportunity, "availability")

    if volunteer_availability and opportunity_availability:
        factors["availability"] = availability_match(
            volunteer_availability, opportunity_availability
        )

    volunteer_location = get_value(volunteer, "location")
    opportunity_location = get_value(opportunity, "location")

    if volunteer_location and opportunity_location:
        factors["location"] = location_match(
            volunteer_location, opportunity_location
        )

    volunteer_experience = get_value(volunteer, "experience")
    required_experience = get_value(opportunity, "experience_required")

    if volunteer_experience and required_experience:
        factors["experience"] = experience_match(
            volunteer_experience, required_experience
        )

    volunteer_mode = get_value(volunteer, "preferred_mode")
    opportunity_mode = get_value(opportunity, "mode")

    if volunteer_mode and opportunity_mode:
        factors["mode"] = mode_match(
            volunteer_mode, opportunity_mode
        )

    return factors


def calculate_score(volunteer, opportunity):
    """Calculate profile-based score out of 100."""

    factors = get_profile_factors(volunteer, opportunity)

    if not factors:
        return 0

    available_weight = sum(
        PROFILE_WEIGHTS[key] for key in factors
    )

    if available_weight == 0:
        return 0

    score = sum(
        factors[key] * PROFILE_WEIGHTS[key]
        for key in factors
    ) / available_weight

    return round(score * 100, 2)


def get_score_breakdown(volunteer, opportunity):
    factors = get_profile_factors(volunteer, opportunity)

    breakdown = {
        key: round(value * 100, 2)
        for key, value in factors.items()
    }

    breakdown["final_score"] = calculate_score(
        volunteer, opportunity
    )

    return breakdown


# =====================================================
# NLP: TF-IDF AND COSINE SIMILARITY
# =====================================================

STOP_WORDS = {
    "the", "a", "an", "and", "or", "is", "are",
    "to", "of", "in", "on", "for", "with", "by",
    "this", "that", "from", "will", "be", "as",
    "at", "it", "we", "our", "you", "your"
}


def tokenize(text):
    words = re.findall(r"[a-zA-Z0-9]+", normalize_text(text))

    return [
        word for word in words
        if len(word) > 1 and word not in STOP_WORDS
    ]


def build_volunteer_document(volunteer):
    fields = [
        get_value(volunteer, "skills"),
        get_value(volunteer, "interests"),
        get_value(volunteer, "experience"),
        get_value(volunteer, "preferred_mode"),
        get_value(volunteer, "location")
    ]

    return " ".join(str(value) for value in fields if value)


def build_opportunity_document(opportunity):
    fields = [
        get_value(opportunity, "title"),
        get_value(opportunity, "description"),
        get_value(opportunity, "cause"),
        get_value(opportunity, "required_skills"),
        get_value(opportunity, "location"),
        get_value(opportunity, "mode"),
        get_value(opportunity, "experience_required")
    ]

    return " ".join(str(value) for value in fields if value)


def tfidf_vector(tokens, document_frequency, total_documents):
    counts = Counter(tokens)
    total_words = len(tokens)

    if total_words == 0:
        return {}

    vector = {}

    for word, count in counts.items():
        tf = count / total_words

        idf = math.log(
            (1 + total_documents) /
            (1 + document_frequency[word])
        ) + 1

        vector[word] = tf * idf

    return vector


def cosine_similarity(vector_a, vector_b):
    if not vector_a or not vector_b:
        return 0

    common_words = set(vector_a) & set(vector_b)

    dot_product = sum(
        vector_a[word] * vector_b[word]
        for word in common_words
    )

    magnitude_a = math.sqrt(
        sum(value ** 2 for value in vector_a.values())
    )

    magnitude_b = math.sqrt(
        sum(value ** 2 for value in vector_b.values())
    )

    if magnitude_a == 0 or magnitude_b == 0:
        return 0

    return dot_product / (magnitude_a * magnitude_b)


def calculate_text_similarity(volunteer, opportunity):
    volunteer_text = tokenize(
        build_volunteer_document(volunteer)
    )

    opportunity_text = tokenize(
        build_opportunity_document(opportunity)
    )

    if not volunteer_text or not opportunity_text:
        return 0

    documents = [volunteer_text, opportunity_text]

    document_frequency = Counter()

    for document in documents:
        document_frequency.update(set(document))

    volunteer_vector = tfidf_vector(
        volunteer_text, document_frequency, len(documents)
    )

    opportunity_vector = tfidf_vector(
        opportunity_text, document_frequency, len(documents)
    )

    similarity = cosine_similarity(
        volunteer_vector, opportunity_vector
    )

    return round(similarity * 100, 2)


# =====================================================
# RECOMMENDATION EXPLANATIONS
# =====================================================

def get_recommendation_reasons(volunteer, opportunity):
    reasons = []
    factors = get_profile_factors(volunteer, opportunity)

    if factors.get("skills", 0) > 0:
        reasons.append("Your skills match this opportunity")

    if factors.get("interests", 0) > 0:
        reasons.append("Matches your interests")

    if factors.get("availability", 0) > 0:
        reasons.append("Your availability matches")

    if factors.get("location", 0) > 0:
        reasons.append("Suitable location")

    if factors.get("experience", 0) > 0:
        reasons.append("Your experience is suitable")

    if factors.get("mode", 0) > 0:
        reasons.append("Matches your preferred work mode")

    if not reasons:
        reasons.append("Related profile and opportunity information")

    return reasons


# =====================================================
# HYBRID RECOMMENDATION SYSTEM
# =====================================================

def rank_opportunities(
    volunteer,
    opportunities,
    top_n=5,
    exclude_ids=None
):
    """
    Hybrid recommendation:
    60% profile matching
    40% TF-IDF text similarity

    Returns flat dictionaries compatible with the dashboard.
    """

    exclude_ids = set(exclude_ids or [])
    ranked = []

    for opportunity in opportunities:

        opportunity_data = dict(opportunity)

        opportunity_id = get_value(
            opportunity_data, "opportunity_id"
        )

        # Skip opportunities already applied to
        if opportunity_id in exclude_ids:
            continue

        profile_score = calculate_score(
            volunteer, opportunity_data
        )

        text_score = calculate_text_similarity(
            volunteer, opportunity_data
        )

        # If profile information is missing, use text matching.
        # If text information is missing, use profile matching.
        has_profile = bool(get_profile_factors(
            volunteer, opportunity_data
        ))

        has_text = bool(
            tokenize(build_volunteer_document(volunteer))
            and tokenize(build_opportunity_document(opportunity_data))
        )

        if has_profile and has_text:
            final_score = (
                0.60 * profile_score +
                0.40 * text_score
            )
        elif has_profile:
            final_score = profile_score
        elif has_text:
            final_score = text_score
        else:
            final_score = 0

        reasons = get_recommendation_reasons(
            volunteer, opportunity_data
        )

        if text_score >= 15:
            reasons.append(
                "Your profile is textually similar to this opportunity"
            )

        # Flat structure: compatible with volunteer_dashboard.html
        opportunity_data["score"] = round(final_score, 2)
        opportunity_data["profile_score"] = profile_score
        opportunity_data["text_score"] = text_score
        opportunity_data["reasons"] = reasons

        ranked.append(opportunity_data)

    ranked.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    if top_n is None:
        return ranked

    return ranked[:top_n]
