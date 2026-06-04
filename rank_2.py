#!/usr/bin/env python3
import json
import csv
import re
import sys
import argparse
from datetime import datetime
from pathlib import Path

# ============================================================================
# Constants & Reference Patterns (Version 2)
# ============================================================================
SERVICES_KEYWORDS = [
    "tcs", "tata consultancy", "infosys", "wipro", "cognizant", "capgemini",
    "accenture", "tech mahindra", "mindtree", "hcl", "hexaware", "l&t", "ltts"
]

HIGH_VALUE_TITLE_PATTERNS = [
    r"\b(ai|ml|machine learning|nlp|nlp/ir|search|retrieval|ranking|re-ranking)\s+engineer\b",
    r"\bapplied\s+(ml|ai)\s+engineer\b",
    r"\b(data\s+scientist|ml\s+researcher)\b"
]

DISQUALIFYING_TITLE_PATTERNS = [
    r"\bmarketing\b", r"\bhr\b", r"\bhuman\s+resources\b", r"\boperations\b",
    r"\bsales\b", r"\bgraphic\s+designer\b", r"\baccountant\b", r"\bcustomer\s+support\b",
    r"\bfinance\b", r"\brecruiter\b"
]

SEARCH_NLP_KEYWORDS = [
    "recommendation system", "recommender system", "recommendation engine", "collaborative filtering",
    "search engine", "information retrieval", "vector search", "semantic search", "hybrid search",
    "bm25", "elasticsearch", "opensearch", "vector database", "pinecone", "milvus", "qdrant",
    "chroma", "faiss", "rag", "embeddings", "ranking", "re-ranking", "retrieval", "ann index",
    "dense retrieval", "reranking", "neural search", "k-nn", "knn", "nearest neighbor"
]

# ============================================================================
# Helper Functions
# ============================================================================
def clean_string(s):
    return s.strip().lower() if s else ""

def parse_date(date_str):
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return None

def is_consulting_company(company_name):
    name_lower = clean_string(company_name)
    return any(kw in name_lower for kw in SERVICES_KEYWORDS)

def extract_candidate_id_num(cid):
    m = re.match(r"^CAND_([0-9]{7})$", cid)
    return int(m.group(1)) if m else 9999999

# ============================================================================
# Honeypot / Trap Detection
# ============================================================================
def check_is_honeypot(candidate):
    """
    Returns True if the profile exhibits logical contradictions (honeypot/trap).
    """
    profile = candidate.get("profile", {})
    total_exp = profile.get("years_of_experience", 0)
    career_history = candidate.get("career_history", [])
    skills = candidate.get("skills", [])
    education = candidate.get("education", [])

    # 1. Experience duration checks
    if not career_history:
        return True # Suspicious if they claim years of experience but have no jobs listed
    
    # Find oldest job start date
    oldest_start = None
    for job in career_history:
        s_date = parse_date(job.get("start_date"))
        if s_date:
            if oldest_start is None or s_date < oldest_start:
                oldest_start = s_date
                
    if oldest_start:
        ref_year = 2026
        max_possible_years = ref_year - oldest_start.year
        if total_exp > max_possible_years + 2:
            return True

    # 2. Skill duration checks
    for skill in skills:
        dur_months = skill.get("duration_months", 0)
        dur_years = dur_months / 12.0
        if dur_years > total_exp + 1.5:
            return True

    # 3. Superhuman skill profiles (Expert status across multiple skills with 0 months)
    expert_empty_skills = 0
    for skill in skills:
        if skill.get("proficiency") == "expert" and skill.get("duration_months", 0) == 0:
            expert_empty_skills += 1
    if expert_empty_skills >= 5:
        return True

    # 4. Job duration mismatch
    for job in career_history:
        s_date = parse_date(job.get("start_date"))
        e_date = parse_date(job.get("end_date"))
        stated_months = job.get("duration_months", 0)
        
        if s_date and e_date:
            actual_months = (e_date.year - s_date.year) * 12 + (e_date.month - s_date.month)
            if stated_months > actual_months + 12:
                return True

    return False

# ============================================================================
# Experience and Fit Scoring (Version 2)
# ============================================================================
def evaluate_candidate_v2(candidate):
    """
    Evaluates a candidate profile and returns (score, gaps, details)
    """
    profile = candidate.get("profile", {})
    career_history = candidate.get("career_history", [])
    skills = candidate.get("skills", [])
    education = candidate.get("education", [])
    signals = candidate.get("redrob_signals", {})
    candidate_id = candidate.get("candidate_id")

    # --- Step 1: Honeypot Exclusion ---
    if check_is_honeypot(candidate):
        return 0.0, ["Honeypot/contradictory profile detected"], {}

    # --- Step 2: Calculate Relevant Product Experience ---
    total_exp = profile.get("years_of_experience", 0)
    consulting_months = 0
    for job in career_history:
        if is_consulting_company(job.get("company", "")):
            consulting_months += job.get("duration_months", 0)
            
    consulting_years = consulting_months / 12.0
    relevant_exp = max(0.0, total_exp - consulting_years)

    # Hard cutoff on Relevant Product Experience (Must be >= 5.0 years)
    if relevant_exp < 5.0:
        return 0.0, ["Less than 5.0 years of relevant product experience"], {}

    # --- Step 3: Location and Relocation Filter ---
    location_str = clean_string(profile.get("location", ""))
    country_str = clean_string(profile.get("country", ""))
    willing_to_relocate = signals.get("willing_to_relocate", False)
    
    is_local = any(city in location_str for city in ["pune", "noida"])
    is_tier1_india = any(city in location_str for city in ["delhi", "mcr", "ncr", "gurgaon", "ghaziabad", "faridabad", "mumbai", "bangalore", "hyderabad", "chennai"])
    is_india = (country_str == "india") or is_local or is_tier1_india

    if not is_india:
        if not willing_to_relocate:
            return 0.0, ["Located outside India and unwilling to relocate"], {}
        location_multiplier = 0.4
    elif is_local:
        location_multiplier = 1.0
    elif is_tier1_india and willing_to_relocate:
        location_multiplier = 0.95  # Slightly boosted for good India candidates
    elif willing_to_relocate:
        location_multiplier = 0.75
    else:
        location_multiplier = 0.5

    # --- Step 4: Compute Relevance Score Components ---
    score = 0.0
    gaps = []

    # 4.1 Title Fit (Max 3.0 pts)
    current_title = clean_string(profile.get("current_title", ""))
    
    # Check for hard disqualifiers
    if any(re.search(pat, current_title) for pat in DISQUALIFYING_TITLE_PATTERNS):
        return 0.0, ["Current title is a non-technical / disqualified role"], {}
        
    title_score = 0.0
    has_high_value_title = False
    for pat in HIGH_VALUE_TITLE_PATTERNS:
        if re.search(pat, current_title):
            title_score = 3.0
            has_high_value_title = True
            break
            
    if not has_high_value_title:
        # Check historical titles
        for job in career_history:
            j_title = clean_string(job.get("title", ""))
            if any(re.search(pat, j_title) for pat in HIGH_VALUE_TITLE_PATTERNS):
                title_score = 2.0
                break
        if title_score == 0.0:
            if "backend" in current_title or "software" in current_title or "data" in current_title:
                title_score = 1.5
            else:
                title_score = 0.5
                gaps.append("Current title lacks explicit AI/ML or engineering alignment")
                
    score += title_score

    # 4.2 NLP / Recommendation Search in Career History (Max 3.5 pts)
    desc_matches = 0
    desc_text = " ".join(clean_string(job.get("description", "")) for job in career_history)
    for kw in SEARCH_NLP_KEYWORDS:
        if kw in desc_text:
            desc_matches += 1
            
    history_score = min(3.5, desc_matches * 0.7)
    if history_score < 1.0:
        gaps.append("Limited search, recommendation, or IR keywords in career history")
    score += history_score

    # 4.3 Skill Match (Max 2.5 pts)
    core_ai_skills = [
        "nlp", "vector database", "pinecone", "milvus", "qdrant", "faiss", "elasticsearch",
        "opensearch", "bm25", "information retrieval", "embeddings", "sentence transformers",
        "fine-tuning llms", "lora", "pytorch", "python", "search", "retrieval", "rag"
    ]
    skill_matches = 0
    candidate_skills = {clean_string(s.get("name")): s for s in skills}
    
    for c_skill in core_ai_skills:
        if c_skill in candidate_skills:
            skill_info = candidate_skills[c_skill]
            prof = skill_info.get("proficiency", "beginner")
            prof_mult = 1.0 if prof == "expert" else 0.8 if prof == "advanced" else 0.5 if prof == "intermediate" else 0.2
            endorse = skill_info.get("endorsements", 0)
            endorse_mult = min(1.2, 1.0 + (endorse / 100.0))
            
            skill_matches += prof_mult * endorse_mult
            
    skill_score = min(2.5, skill_matches * 0.5)
    if skill_score < 0.8:
        gaps.append("Lacks deep native vector search, embedding or RAG skills")
    score += skill_score

    # 4.4 Experience Curve Score (Max 1.0 pts)
    # Sweet spot is 6-8 years (1.0), decay outside. Minimum is already 5.0.
    if 6.0 <= relevant_exp <= 8.0:
        exp_score = 1.0
    elif 5.0 <= relevant_exp < 6.0:
        exp_score = 0.7 + (relevant_exp - 5.0) * 0.3
    else: # > 8.0
        exp_score = max(0.5, 1.0 - (relevant_exp - 8.0) * 0.15)
    score += exp_score

    # Apply location multiplier to raw relevance score
    score = score * location_multiplier

    # --- Step 5: Compute Behavioral Multipliers ---
    last_act = parse_date(signals.get("last_active_date"))
    recency_mult = 1.0
    if last_act:
        days_inactive = (datetime(2026, 6, 4) - last_act).days
        if days_inactive > 180:
            recency_mult = 0.5
            gaps.append("Inactive on the platform for over 6 months")
        elif days_inactive > 90:
            recency_mult = 0.8
            gaps.append("Inactive on the platform for over 3 months")

    resp_rate = signals.get("recruiter_response_rate", 0.0)
    resp_mult = 0.6 + (resp_rate * 0.8)

    notice = signals.get("notice_period_days", 0)
    if notice <= 30:
        notice_mult = 1.1
    elif notice >= 90:
        notice_mult = 0.7
        gaps.append(f"Long notice period of {notice} days")
    else:
        notice_mult = 1.0

    verified_mult = 1.0
    if signals.get("verified_email") and signals.get("verified_phone"):
        verified_mult = 1.05
        
    github_act = signals.get("github_activity_score", -1)
    github_mult = 1.0
    if github_act > 70:
        github_mult = 1.1
    elif github_act == -1:
        github_mult = 0.95
        gaps.append("No active GitHub repository linked")

    behavior_multiplier = recency_mult * resp_mult * notice_mult * verified_mult * github_mult
    final_score = score * behavior_multiplier

    details = {
        "relevant_exp": relevant_exp,
        "current_title": profile.get("current_title", ""),
        "location": profile.get("location", ""),
        "is_local": is_local,
        "is_tier1": is_tier1_india,
        "willing_to_relocate": willing_to_relocate,
        "notice_period": notice,
        "response_rate": resp_rate,
        "github_score": github_act,
        "skills": list(candidate_skills.keys())[:3]
    }

    return final_score, gaps, details

# ============================================================================
# Dynamic Reasoning Generation (Version 2)
# ============================================================================
def generate_reasoning_v2(candidate, final_score, gaps, details):
    cid = candidate.get("candidate_id")
    cid_num = extract_candidate_id_num(cid)
    
    title = details.get("current_title", "Engineer")
    exp = round(details.get("relevant_exp", 5.0), 1)
    skills = details.get("skills", [])
    loc = details.get("location", "India")
    notice = details.get("notice_period", 60)
    resp = int(details.get("response_rate", 0.0) * 100)
    github = details.get("github_score", -1)

    skill_str = ", ".join(s.title() for s in skills[:2]) if skills else "NLP and engineering"
    reloc_str = "local candidate" if details.get("is_local") else "relocation candidate"
    
    gap_parts = []
    if notice >= 90:
        gap_parts.append(f"notice period is {notice} days")
    if details.get("github_score") == -1:
        gap_parts.append("no GitHub profile linked")
    if details.get("response_rate", 1.0) < 0.3:
        gap_parts.append("low response rate")
    gap_clause = "but " + " and ".join(gap_parts) if gap_parts else ""

    style = cid_num % 4

    if style == 0:
        reasoning = f"{title} with {exp} years of product experience, demonstrating competency in {skill_str}. Based in {loc} ({reloc_str}) with {resp}% response rate{', ' + gap_clause if gap_clause else ''}."
    elif style == 1:
        reasoning = f"Offers {exp} years of background as {title}, having active exposure to {skill_str}. Currently located in {loc}; is {reloc_str} with {resp}% recruiter response{', ' + gap_clause if gap_clause else ''}."
    elif style == 2:
        reasoning = f"Strong fit with {exp} years experience as {title} and proven hands-on work in {skill_str}. Based in {loc} ({reloc_str}){' ' + gap_clause if gap_clause else ''}. GitHub activity score is {github}."
    else:
        reasoning = f"{exp}-year engineering background in product companies (current title: {title}), showing capabilities in {skill_str}. Local/relocation match: {loc} ({reloc_str}){', ' + gap_clause if gap_clause else ''}."

    return reasoning.strip()

# ============================================================================
# Main Execution (Version 2)
# ============================================================================
def main():
    parser = argparse.ArgumentParser(description="Cognitive Candidate Ranker V2")
    parser.add_argument("--candidates", required=True, help="Path to candidates.jsonl")
    parser.add_argument("--out", required=True, help="Path to output submission.csv")
    args = parser.parse_args()

    candidates_path = Path(args.candidates)
    if not candidates_path.exists():
        print(f"Error: Candidate file {args.candidates} does not exist.")
        sys.exit(1)

    scored_candidates = []

    print("Streaming and scoring candidates (V2)...")
    
    with open(candidates_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                candidate = json.loads(line)
            except json.JSONDecodeError:
                continue

            cid = candidate.get("candidate_id")
            final_score, gaps, details = evaluate_candidate_v2(candidate)
            
            if final_score <= 0.0:
                continue

            signals = candidate.get("redrob_signals", {})
            open_to_work = signals.get("open_to_work_flag", False)
            github_score = signals.get("github_activity_score", -1)

            scored_candidates.append({
                "candidate_id": cid,
                "score": final_score,
                "gaps": gaps,
                "details": details,
                "open_to_work": open_to_work,
                "github_score": github_score,
                "raw_candidate": candidate
            })

    # Sort Candidates with V2 logic:
    # 1. Score descending
    # 2. Open to Work descending (True first)
    # 3. GitHub Activity Score descending (Higher first)
    # 4. Candidate ID ascending (secondary sorting)
    print(f"Scoring complete. Sorting {len(scored_candidates)} valid candidates...")
    
    scored_candidates.sort(key=lambda x: (
        -x["score"],
        not x["open_to_work"],
        -x["github_score"],
        extract_candidate_id_num(x["candidate_id"])
    ))

    top_100 = scored_candidates[:100]

    print("Writing CSV submission...")
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w", encoding="utf-8", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["candidate_id", "rank", "score", "reasoning"])
        
        for idx, item in enumerate(top_100):
            rank = idx + 1
            cid = item["candidate_id"]
            score = round(item["score"], 4)
            reasoning = generate_reasoning_v2(item["raw_candidate"], score, item["gaps"], item["details"])
            writer.writerow([cid, rank, score, reasoning])

    print(f"Successfully ranked top 100 candidates. Output written to {args.out}")

if __name__ == "__main__":
    main()
