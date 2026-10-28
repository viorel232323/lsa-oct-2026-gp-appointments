# Presentation notes

## The one problem I solved
- **Problem:** quality check 9 showed the duration file covering only 90.9–92.2% of appointments. It looked like data was being lost.
- **What I did:** read `metadata_nhs.txt` (duration = "the consultation that took place"), then tested the idea: each month, I compared duration's share with the share of Attended appointments.
- **Result:** identical to 0.1% in all 7 months. Nothing was lost; the two files simply measure different things. I kept the check at 90% and documented why (D30).
- **Why it matters:** forcing two differently-collected figures to agree is how real reporting errors are made.

## Backup story
Moving to a second laptop mid-week exposed hard-coded paths and a missing file. Fixed with `config.py`, `data/source` and README instructions from a clean clone, and proven by running the full pipeline on the new laptop.