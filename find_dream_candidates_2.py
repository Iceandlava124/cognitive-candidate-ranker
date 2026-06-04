#!/usr/bin/env python3
import json
import re
from pathlib import Path

# Consulting filters
SERVICES_KEYWORDS = ["tcs", "tata consultancy", "infosys", "wipro", "cognizant", "capgemini", "accenture", "tech mahindra", "mindtree", "hcl"]

def is_consulting(company):
    if not company:
        return False
    c_lower = company.lower()
    return any(kw in c_lower for kw in SERVICES_KEYWORDS)

def check_logical_contradiction(c):
    # Quick check for honeypots
    profile = c.get("profile", {})
    total_exp = profile.get("years_of_experience", 0)
    career_history = c.get("career_history", [])
    skills = c.get("skills", [])
    
    # 1. Experience duration vs first job start date
    oldest_year = None
    for job in career_history:
        start_date = job.get("start_date")
        if start_date:
            try:
                y = int(start_date.split("-")[0])
                if oldest_year is None or y < oldest_year:
                    oldest_year = y
            except ValueError:
                pass
    if oldest_year:
        max_possible = 2026 - oldest_year
        if total_exp > max_possible + 2:
            return True
            
    # 2. Skill duration exceeds experience
    for skill in skills:
        dur_years = skill.get("duration_months", 0) / 12.0
        if dur_years > total_exp + 1.5:
            return True
            
    return False

def main():
    script_dir = Path(__file__).resolve().parent
    candidates_path = script_dir / "candidates.jsonl"
    dream_candidates = []

    print("Scanning candidates for the 'Dream Profile'...")
    
    with open(candidates_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                c = json.loads(line)
            except json.JSONDecodeError:
                continue
                
            # Filter 1: Programmatic Honeypot Exclusions
            if check_logical_contradiction(c):
                continue
                
            profile = c.get("profile", {})
            career_history = c.get("career_history", [])
            skills = c.get("skills", [])
            signals = c.get("redrob_signals", {})
            
            # Filter 2: Title Fit (Must be Senior ML/AI/NLP or similar)
            title = profile.get("current_title", "").lower()
            if not any(kw in title for kw in ["ai engineer", "ml engineer", "machine learning", "nlp engineer", "search engineer", "retrieval engineer"]):
                continue
                
            # Filter 3: Experience check (5.0 to 9.0 years)
            total_exp = profile.get("years_of_experience", 0.0)
            if not (5.0 <= total_exp <= 9.0):
                continue
                
            # Filter 4: Non-consulting experience check
            has_consulting_only = True
            for job in career_history:
                if not is_consulting(job.get("company", "")):
                    has_consulting_only = False
                    break
            if has_consulting_only:
                continue
                
            # Filter 5: Skills (Must have Vector search or RAG or LLMs)
            skill_names = [s.get("name", "").lower() for s in skills]
            has_vector_skills = any(sk in skill_names for sk in ["pinecone", "milvus", "qdrant", "faiss", "vector database", "rag", "embeddings", "information retrieval", "fine-tuning llms", "lora"])
            if not has_vector_skills:
                continue
                
            # Filter 6: Location & Relocation
            loc = profile.get("location", "").lower()
            country = profile.get("country", "").lower()
            willing_relocate = signals.get("willing_to_relocate", False)
            is_local = any(city in loc for city in ["pune", "noida"])
            is_relocatable_india = (country == "india" or "india" in loc) and willing_relocate
            if not (is_local or is_relocatable_india):
                continue
                
            # Filter 7: High Activity & Availability
            open_to_work = signals.get("open_to_work_flag", False)
            resp_rate = signals.get("recruiter_response_rate", 0.0)
            notice = signals.get("notice_period_days", 90)
            
            # Require at least decent responsiveness and open to work
            if not open_to_work:
                continue
            if resp_rate < 0.6: # At least 60% response rate
                continue
            if notice > 60: # Under 60 days notice
                continue

            dream_candidates.append(c)

    print(f"Found {len(dream_candidates)} candidates matching the strict 'Dream Profile'.")
    
    # Save the reference list
    out_path = script_dir / "dream_candidates_ref_2.json"
    with open(out_path, "w", encoding="utf-8") as out_f:
        json.dump(dream_candidates, out_f, indent=2)
        
    print(f"Dream candidate reference list saved to {out_path}")

if __name__ == "__main__":
    main()
