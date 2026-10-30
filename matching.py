
import re
import math
from collections import Counter


# =========================================================
# CONFIGURATION
# =========================================================

PROFILE_WEIGHT = 0.60
TEXT_WEIGHT = 0.40

PROFILE_WEIGHTS = {
    "skills": 0.35,
    "interests": 0.15,
    "availability": 0.20,
    "location": 0.10,
    "experience": 0.10,
    "mode": 0.10
}

EXPERIENCE_LEVELS = {
    "beginner": 1,
    "basic": 1,
    "no experience": 1,
    "intermediate": 2,
    "moderate": 2,
    "advanced": 3,
    "expert": 4,
    "professional": 4
}

# Small synonym dictionary for related volunteer skills
SYNONYMS = {
    "teaching": {"education", "tutoring", "training"},
    "education": {"teaching", "tutoring", "training"},
    "tutoring": {"teaching", "education"},
    "coding": {"programming", "software"},
    "programming": {"coding", "software development"},
    "healthcare": {"medical", "health", "medicine"},
    "medical": {"healthcare", "health", "medicine"},
    "environment": {"environmental", "nature", "conservation"},
    "environmental": {"environment", "conservation"},
    "fundraising": {"fundraising", "donations", "funding"},
    "design": {"graphic design", "creative design"},
    "communication": {"public speaking", "content writing"},
    "writing": {"content writing", "content creation"}
}


# =========================================================
# GENERAL HELPERS
# =========================================================

def get_value(data, *keys, default=""):
    """Safely read values from dictionaries or database rows."""

    if data is None:
        return default

    for key in keys:
        try:
            value = data[key]
            if value is not None:
                return value
        except (KeyError, IndexError, TypeError):
            continue

    return default


def normalize_text(value):
    if value is None:
        return ""

    return re.sub(r"\s+", " ", str(value).lower()).strip()


def make_list(value):
    """Convert comma-separated strings or lists into normalized lists."""

    if value is None:
        return []

    if isinstance(value, (list, tuple, set)):
        items = value
    else:
        items = re.split(r"[,;|\n]", str(value))

    return [
        normalize_text(item)
        for item in items
        if normalize_text(item)
    ]


def tokenize(text):
    """Extract meaningful words from text."""

    text = normalize_text(text)

    return re.findall(r"[a-z0-9]+", text)


def canonical_skill(skill):
    """Normalize common related skill names."""

    skill = normalize_text(skill)

    for main_skill, related_skills in SYNONYMS.items():
        if skill == main_skill or skill in related_skills:
            return main_skill

    return skill


def similarity_between_items(first, second):
    first = canonical_skill(first)
    second = canonical_skill(second)

    if first == second:
        return 1.0

    first_tokens = set(tokenize(first))
    second_tokens = set(tokenize(second))

    if not first_tokens or not second_tokens:
        return 0.0

    intersection = first_tokens.intersection(second_tokens)

    return len(intersection) / len(first_tokens.union(second_tokens))


# =========================================================
# PROFILE MATCHING
# =========================================================

def skill_match(volunteer_skills, required_skills):

    volunteer_skills = make_list(volunteer_skills)
    required_skills = make_list(required_skills)

    if not volunteer_skills or not required_skills:
        return None

    matched = 0

    for required in required_skills:

        best_match = max(
            (
                similarity_between_items(volunteer, required)
                for volunteer in volunteer_skills
            ),
            default=0
        )

        if best_match >= 0.5:
            matched += 1

    return matched / len(required_skills)


def interest_match(volunteer_interests, opportunity):

    interests = make_list(volunteer_interests)

    opportunity_text = normalize_text(
        " ".join([
            str(get_value(opportunity, "cause")),
            str(get_value(opportunity, "title")),
            str(get_value(opportunity, "description"))
        ])
    )

    if not interests or not opportunity_text:
        return None

    matches = 0

    for interest in interests:

        interest_tokens = set(tokenize(interest))
        opportunity_tokens = set(tokenize(opportunity_text))

        if interest_tokens and interest_tokens.intersection(opportunity_tokens):
            matches += 1

    return matches / len(interests)


def location_match(volunteer_location, opportunity_location):

    volunteer_location = normalize_text(volunteer_location)
    opportunity_location = normalize_text(opportunity_location)

    if not volunteer_location or not opportunity_location:
        return None

    remote_terms = {"remote", "online", "virtual"}

    if (
        volunteer_location in remote_terms
        or opportunity_location in remote_terms
    ):
        return 1.0

    if volunteer_location == opportunity_location:
        return 1.0

    return 0.0


def availability_match(volunteer_availability, opportunity_availability):

    volunteer_days = set(make_list(volunteer_availability))
    opportunity_days = set(make_list(opportunity_availability))

    if not volunteer_days or not opportunity_days:
        return None

    if "flexible" in volunteer_days or "anytime" in volunteer_days:
        return 1.0

    overlap = volunteer_days.intersection(opportunity_days)

    return len(overlap) / len(opportunity_days)


def experience_match(volunteer_experience, required_experience):

    volunteer_experience = normalize_text(volunteer_experience)
    required_experience = normalize_text(required_experience)

    if not volunteer_experience or not required_experience:
        return None

    volunteer_level = EXPERIENCE_LEVELS.get(volunteer_experience)
    required_level = EXPERIENCE_LEVELS.get(required_experience)

    if volunteer_level is None or required_level is None:
        return None

    if volunteer_level >= required_level:
        return 1.0

    return volunteer_level / required_level


def mode_match(volunteer_mode, opportunity_mode):

    volunteer_mode = normalize_text(volunteer_mode)
    opportunity_mode = normalize_text(opportunity_mode)

    if not volunteer_mode or not opportunity_mode:
        return None

    if volunteer_mode == opportunity_mode:
        return 1.0

    if "hybrid" in (volunteer_mode, opportunity_mode):
        return 1.0

    return 0.0


# =========================================================
# PROFILE SCORE
# =========================================================

def calculate_profile_score(volunteer, opportunity):

    results = {
        "skills": skill_match(
            get_value(volunteer, "skills"),
            get_value(opportunity, "required_skills", "skills")
        ),

        "interests": interest_match(
            get_value(volunteer, "interests"),
            opportunity
        ),

        "availability": availability_match(
            get_value(volunteer, "availability"),
            get_value(opportunity, "availability")
        ),

        "location": location_match(
            get_value(volunteer, "location"),
            get_value(opportunity, "location")
        ),

        "experience": experience_match(
            get_value(volunteer, "experience"),
            get_value(opportunity, "experience_required", "required_experience")
        ),

        "mode": mode_match(
            get_value(volunteer, "preferred_mode"),
            get_value(opportunity, "mode")
        )
    }

    weighted_score = 0
    total_weight = 0

    for factor, score in results.items():

        if score is not None:

            weight = PROFILE_WEIGHTS[factor]

            weighted_score += score * weight
            total_weight += weight

    if total_weight == 0:
        return 0.0, results

    final_score = weighted_score / total_weight

    return round(final_score * 100, 2), results


# =========================================================
# NLP: TF-IDF AND COSINE SIMILARITY
# =========================================================

def build_volunteer_document(volunteer):

    fields = [
        get_value(volunteer, "skills"),
        get_value(volunteer, "interests"),
        get_value(volunteer, "experience"),
        get_value(volunteer, "location"),
        get_value(volunteer, "preferred_mode"),
        get_value(volunteer, "availability")
    ]

    return " ".join(str(field) for field in fields if field)


def build_opportunity_document(opportunity):

    fields = [
        get_value(opportunity, "title"),
        get_value(opportunity, "description"),
        get_value(opportunity, "cause"),
        get_value(opportunity, "required_skills", "skills"),
        get_value(opportunity, "location"),
        get_value(opportunity, "mode"),
        get_value(opportunity, "experience_required", "required_experience")
    ]

    return " ".join(str(field) for field in fields if field)


def tfidf_similarity(volunteer_document, opportunity_documents):

    volunteer_tokens = tokenize(volunteer_document)

    if not volunteer_tokens:
        return [0.0] * len(opportunity_documents)

    opportunity_tokens = [
        tokenize(document)
        for document in opportunity_documents
    ]

    all_documents = [volunteer_tokens] + opportunity_tokens

    document_count = len(all_documents)

    document_frequency = Counter()

    for document in all_documents:
        document_frequency.update(set(document))

    def calculate_vector(tokens):

        word_counts = Counter(tokens)
        total_words = len(tokens)

        vector = {}

        if total_words == 0:
            return vector

        for word, count in word_counts.items():

            tf = count / total_words

            idf = math.log(
                (document_count + 1) /
                (document_frequency[word] + 1)
            ) + 1

            vector[word] = tf * idf

        return vector

    volunteer_vector = calculate_vector(volunteer_tokens)

    opportunity_vectors = [
        calculate_vector(tokens)
        for tokens in opportunity_tokens
    ]

    def cosine_similarity(first, second):

        if not first or not second:
            return 0.0

        common_words = set(first).intersection(second)

        dot_product = sum(
            first[word] * second[word]
            for word in common_words
        )

        first_magnitude = math.sqrt(
            sum(value ** 2 for value in first.values())
        )

        second_magnitude = math.sqrt(
            sum(value ** 2 for value in second.values())
        )

        if first_magnitude == 0 or second_magnitude == 0:
            return 0.0

        return dot_product / (
            first_magnitude * second_magnitude
        )

    return [
        round(
            cosine_similarity(volunteer_vector, vector) * 100,
            2
        )
        for vector in opportunity_vectors
    ]


# =========================================================
# HYBRID SCORE
# =========================================================

def calculate_score(volunteer, opportunity):

    profile_score, breakdown = calculate_profile_score(
        volunteer,
        opportunity
    )

    volunteer_document = build_volunteer_document(volunteer)
    opportunity_document = build_opportunity_document(opportunity)

    text_score = tfidf_similarity(
        volunteer_document,
        [opportunity_document]
    )[0]

    # If there is no usable profile information,
    # rely on the NLP similarity score.
    if not any(value is not None for value in breakdown.values()):
        final_score = text_score

    elif not volunteer_document.strip():
        final_score = profile_score

    else:
        final_score = (
            profile_score * PROFILE_WEIGHT
            + text_score * TEXT_WEIGHT
        )

    return round(min(max(final_score, 0), 100), 2)


def get_score_breakdown(volunteer, opportunity):

    profile_score, breakdown = calculate_profile_score(
        volunteer,
        opportunity
    )

    volunteer_document = build_volunteer_document(volunteer)
    opportunity_document = build_opportunity_document(opportunity)

    text_score = tfidf_similarity(
        volunteer_document,
        [opportunity_document]
    )[0]

    final_score = calculate_score(volunteer, opportunity)

    return {
        "profile_score": profile_score,
        "text_similarity": text_score,
        "skills": breakdown["skills"],
        "interests": breakdown["interests"],
        "availability": breakdown["availability"],
        "location": breakdown["location"],
        "experience": breakdown["experience"],
        "mode": breakdown["mode"],
        "final_score": final_score
    }


# =========================================================
# RECOMMENDATION EXPLANATIONS
# =========================================================

def get_recommendation_reasons(volunteer, opportunity):

    reasons = []

    volunteer_skills = make_list(
        get_value(volunteer, "skills")
    )

    required_skills = make_list(
        get_value(opportunity, "required_skills", "skills")
    )

    for required in required_skills:

        if any(
            similarity_between_items(skill, required) >= 0.5
            for skill in volunteer_skills
        ):
            reasons.append(
                "Your skills match: " + required
            )

    interests = make_list(
        get_value(volunteer, "interests")
    )

    cause = normalize_text(
        get_value(opportunity, "cause")
    )

    if cause and any(
        interest in cause or cause in interest
        for interest in interests
    ):
        reasons.append(
            "Matches your interest in " + cause
        )

    location = location_match(
        get_value(volunteer, "location"),
        get_value(opportunity, "location")
    )

    if location == 1.0:
        reasons.append("Suitable location")

    mode = mode_match(
        get_value(volunteer, "preferred_mode"),
        get_value(opportunity, "mode")
    )

    if mode == 1.0:
        reasons.append("Matches your preferred work mode")

    if not reasons:
        reasons.append(
            "Recommended based on your overall profile and opportunity description"
        )

    return reasons


# =========================================================
# FINAL RANKING FUNCTION
# =========================================================

def rank_opportunities(
    volunteer,
    opportunities,
    top_n=5,
    exclude_ids=None
):

    exclude_ids = {
        str(item) for item in (exclude_ids or [])
    }

    eligible_opportunities = []

    for opportunity in opportunities:

        opportunity_id = get_value(
            opportunity,
            "opportunity_id",
            "id"
        )

        if opportunity_id is not None:
            if str(opportunity_id) in exclude_ids:
                continue

        eligible_opportunities.append(opportunity)

    if not eligible_opportunities:
        return []

    volunteer_document = build_volunteer_document(volunteer)

    opportunity_documents = [
        build_opportunity_document(opportunity)
        for opportunity in eligible_opportunities
    ]

    text_scores = tfidf_similarity(
        volunteer_document,
        opportunity_documents
    )

    recommendations = []

    for index, opportunity in enumerate(eligible_opportunities):

        profile_score, breakdown = calculate_profile_score(
            volunteer,
            opportunity
        )

        text_score = text_scores[index]

        if not any(value is not None for value in breakdown.values()):
            final_score = text_score

        elif not volunteer_document.strip():
            final_score = profile_score

        else:
            final_score = (
                profile_score * PROFILE_WEIGHT
                + text_score * TEXT_WEIGHT
            )

        final_score = round(
            min(max(final_score, 0), 100),
            2
        )

        # Preserve all original opportunity fields.
        try:
            result = dict(opportunity)
        except (TypeError, ValueError):
            result = {}

            for key in (
                "opportunity_id",
                "title",
                "cause",
                "ngo_name",
                "location",
                "mode",
                "hours_required",
                "description",
                "required_skills"
            ):
                value = get_value(opportunity, key, default=None)

                if value is not None:
                    result[key] = value

        result["score"] = final_score
        result["match_score"] = final_score

        result["score_breakdown"] = {
            "profile_score": profile_score,
            "text_similarity": text_score,
            "skills": breakdown["skills"],
            "interests": breakdown["interests"],
            "availability": breakdown["availability"],
            "location": breakdown["location"],
            "experience": breakdown["experience"],
            "mode": breakdown["mode"]
        }

        result["recommendation_reasons"] = (
            get_recommendation_reasons(
                volunteer,
                opportunity
            )
        )

        recommendations.append(result)

    recommendations.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    if top_n is not None:
        recommendations = recommendations[:top_n]

    return recommendations
