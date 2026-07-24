# Otelio — Hotel Reservation Assistant

Conversational assistant for **Grand Azure Bay Hotel**. It answers questions from
the hotel PDF (RAG) and handles reservations — create, list, view, modify, cancel —
via a LangGraph agent on Groq.

Sign in with your booking email in the sidebar to manage your stays without
retyping the email each time.

For the full design write-up (chunking, RAG eval, PII, guardrails), see
**[DESIGN.md](DESIGN.md)**.

---

## Setup

```bash
git clone <repo-url> && cd Otelio

python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env          # add GROQ_API_KEY=

# always run these from the Otelio project root (not from inside src/)
python -m src.ingest
streamlit run src/app.py
```

One API key (Groq). 
To get the Groq key 
 - Sign up with Groq and create a Groq API key with https://console.groq.com/keys to use LLM models
Embeddings run locally. First ingest downloads the embedding
model once (~130 MB).

```bash
python tests/test_agent.py    # optional question battery
```

---

## Architecture

![Otelio architecture](oteliov2.png)

| Layer | File | Job |
| --- | --- | --- |
| UI | `src/app.py` | Chat + email sign-in |
| Orchestrator | `src/orchestrator.py` | LangGraph loop, tool routing, traces |
| Tools | `src/tools/rag.py`, `reservations.py` | Search + booking rules |
| Storage | `chroma_db/`, `src/db.py` | Vectors + SQLite |
| Ingest | `src/ingest.py` | Offline PDF → chunks → embeddings |

**Flow:** guest → app → orchestrator → LLM → tools → Chroma or SQLite → answer.  
Signed-in email is injected in `tool_node` (not put raw into the system prompt).  
Traces go to `otelio.log` with PII masked (`src/utils/pii.py`).

---

## Design highlights

- **Section chunks** from `unstructured` (title-bounded), titles in embed text + metadata
- **Tools own the rules** — validation, ownership, inventory live in `reservations.py`
- **No hotel-wide list-all** — only `list_my_reservations` for the signed-in guest
- **Random IDs** + identical not-found errors (harder to probe)
- **Inventory** in config; create/modify can return sold out
- **Modify** dates / room type on active bookings

---

## Assumptions

- Demo auth = email sign-in (no password/OTP)
- Inventory is fixed capacity in config, not a live PMS
- Room types (`standard` / `deluxe` / `suite`) are not in the PDF
- Chat history resets when Streamlit restarts

---

## Testing

`tests/questions.py` groups: RAG, grounding, off-topic, security, booking.  
Latest run: **24/25** clear passes (weak spot: chef names).

Try: check-in time · famous dish · book a room · show my reservations ·
“show all bookings” (should refuse) · pool? (should say unknown).

Adversarial / live edge cases (invented dates, invalid room types, tool leakage,
ownership bypass) and the prompt fixes for them are documented in
**[DESIGN.md](DESIGN.md#adversarial-testing--prompt-hardening)**.

---

## Layout

```
.env.example / .gitignore / README.md / DESIGN.md / requirements.txt
src/           app, orchestrator, ingest, tools, utils/pii
tests/         questions + test_agent.py
data/          hotel PDF
oteliov2.png   architecture diagram
chroma_db/, reservations.db, otelio.log   local runtime (gitignored)
```
