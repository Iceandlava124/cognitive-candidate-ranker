import streamlit as st
import json
import pandas as pd
import io
import os
# Import evaluation and logic from rank_2.py
from rank_2 import evaluate_candidate_v2, generate_reasoning_v2, extract_candidate_id_num

st.set_page_config(page_title="Cognitive Candidate Ranker", page_icon="🚀", layout="wide")

st.title("🚀 Cognitive Candidate Discovery & Ranking Sandbox")
st.write("This interactive sandbox evaluates and ranks candidates for the **Senior AI Engineer (Founding Team)** role at Redrob.")

st.markdown("""
### How it works:
1. **Sanitizes Honeypots**: Programmatically eliminates logical contradictions (time-travel records, impossible skill durations).
2. **Product Experience Check**: Enforces >5 years product engineering experience (excluding consulting/IT services like TCS, Wipro, Infosys).
3. **Relevance Fit**: Multi-dimensional scoring of technical titles, search/NLP keywords in history, and skill endorsements.
4. **Behavioral scaling**: Multiplies score based on platform activity (notice periods, recruiter response rates, GitHub contribution score).
""")

# Preloaded data option or file upload
uploaded_file = st.file_uploader("Upload candidates.jsonl file (or JSON array)", type=["jsonl", "json"])
use_sample = st.checkbox("Use pre-loaded sample candidates (50 candidates)", value=True)

if st.button("Run Ranker", type="primary"):
    candidates = []
    
    if uploaded_file is not None:
        content = uploaded_file.getvalue().decode("utf-8")
        if content.strip().startswith("["):
            try:
                candidates = json.loads(content)
            except Exception as e:
                st.error(f"Error parsing JSON array: {e}")
        else:
            for line in content.splitlines():
                if line.strip():
                    try:
                        candidates.append(json.loads(line))
                    except Exception as e:
                        pass
    elif use_sample:
        # Load local sample candidates
        sample_path = os.path.join(os.path.dirname(__file__), "sample_candidates.json")
        try:
            with open(sample_path, "r", encoding="utf-8") as f:
                candidates = json.load(f)
        except Exception as e:
            st.error(f"Error loading sample_candidates.json: {e}")

    if candidates:
        st.info(f"Loaded {len(candidates)} candidates. Evaluating...")
        scored_candidates = []
        
        for c in candidates:
            score, gaps, details = evaluate_candidate_v2(c)
            if score > 0.0:
                open_to_work = c.get("redrob_signals", {}).get("open_to_work_flag", False)
                github_score = c.get("redrob_signals", {}).get("github_activity_score", -1)
                scored_candidates.append({
                    "candidate_id": c.get("candidate_id"),
                    "score": score,
                    "gaps": gaps,
                    "details": details,
                    "open_to_work": open_to_work,
                    "github_score": github_score,
                    "raw_candidate": c
                })
        
        # Sort
        scored_candidates.sort(key=lambda x: (
            -x["score"],
            not x["open_to_work"],
            -x["github_score"],
            extract_candidate_id_num(x["candidate_id"])
        ))
        
        # Build output dataframe
        rows = []
        for idx, item in enumerate(scored_candidates):
            rank = idx + 1
            cid = item["candidate_id"]
            score = round(item["score"], 4)
            reasoning = generate_reasoning_v2(item["raw_candidate"], score, item["gaps"], item["details"])
            
            details = item["details"]
            rows.append({
                "Rank": rank,
                "Candidate ID": cid,
                "Score": score,
                "Current Title": details.get("current_title"),
                "Location": details.get("location"),
                "Exp (Product)": round(details.get("relevant_exp"), 1),
                "Reasoning": reasoning
            })
            
        df = pd.DataFrame(rows)
        st.success(f"Ranking complete! Found {len(df)} qualified candidates.")
        
        # Display table
        st.dataframe(df, use_container_width=True)
        
        # CSV Download Button
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        st.download_button(
            label="Download Ranked CSV",
            data=csv_buffer.getvalue(),
            file_name="sandbox_ranked_candidates.csv",
            mime="text/csv"
        )
    else:
        st.warning("No candidates loaded.")
