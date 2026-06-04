# Cognitive Candidate Discovery & Ranking System (V2)

This repository contains our entry for the Redrob Intelligent Candidate Discovery & Ranking Challenge.

## Quick Start
To reproduce our submission CSV from the candidates pool, run:
```bash
python rank_2.py --candidates ./candidates.jsonl --out ./team_test_2.csv
```

## Setup & Dependencies
* Python 3.11+
* Zero external dependencies (uses only Python standard libraries)
* Total runtime: ~24 seconds for 100,000 records.

## Architecture
Our pipeline uses a 5-Stage Heuristic Filter and Multiplier:
1. **Integrity Sanitation**: Programmatic checks to instantly disqualify logical honeypots (time-travelers, skill duration contradictions, superhuman profiles).
2. **Product Experience Cutoff**: Hard-filters candidates with less than 5.0 years of product engineering experience, subtracting any tenure spent at IT services/consulting firms (TCS, Wipro, Infosys, etc.).
3. **Relevance Scoring**: Heuristics checking title matches (focusing on senior ML/AI roles), keyword mining in description histories (to capture hidden Tier-5 matches), and core skill weights.
4. **Behavioral Scaling**: Scales match scores using platform activity recency, message response rates, notice periods, and GitHub activity.
5. **Deterministic Tie-Breaking**: Sorts descending by score, and breaks ties using open-to-work flag, GitHub activity score, and candidate ID ascending.
