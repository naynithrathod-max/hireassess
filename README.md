# Standardized Hiring Assessment Platform

A working prototype of Phase 0–1 of the blueprint, built to demonstrate cloud
computing and virtualization.

A candidate registers, gives consent, sits a timed analytical round and a written
communication round, and receives a scorecard with a percentile. Partner
companies see a filtered pool containing only candidates who consented. A human
reviewer confirms every written-round score before it is released.

---

## Start here

**New to this?** Open `SETUP.md` and follow Layer A. Fifteen minutes and you have
a running demo. No coding required.

| File | What it is |
|---|---|
| `SETUP.md` | Click-by-click setup, deployment and the demo script |
| `ARCHITECTURE.md` | The architecture diagram, the cloud justification, and the questions you will be asked |
| `app.py` | The web application |
| `scorer.py` | The scoring engines, rule-based and optional AI |
| `storage.py` | Scorecard storage: local disk or Azure Blob |
| `questions.json` | Question bank, rubric and round weights |
| `Dockerfile` | How the container is built |
| `docker-compose.yml` | Shortcut for running it |

---

## Quick start

```
docker build -t hireassess:latest .
docker run -d --name hireassess -p 8000:8000 -v assessment-data:/data hireassess:latest
```

Open `http://localhost:8000`.

To run it without Docker, for a fast check:

```
pip install -r requirements.txt
DB_PATH=./data/app.db SCORECARD_DIR=./data/scorecards python app.py
```

---

## The screens

| Path | What it is | Passcode |
|---|---|---|
| `/` | Candidate landing page | — |
| `/register` | Registration with the consent checkbox | — |
| `/test/<id>` | Timed analytical and situational round | — |
| `/written/<id>` | Timed written case round | — |
| `/scorecard/<id>` | Scores, percentile, rubric breakdown, consent toggle | — |
| `/company` | Hiring partner pool, filtered by consent and threshold | `partner2026` |
| `/reviewer` | Human review queue for written answers | `reviewer2026` |
| `/admin/info` | Which host served you, storage backend, stored objects | — |
| `/health` | JSON health check for load balancers | — |

Change the passcodes with the `COMPANY_PASSCODE` and `REVIEWER_PASSCODE`
environment variables.

---

## How scoring works

| Round | Weight | Method |
|---|---|---|
| Speed & working ability | 15% | Completion rate, with pace as a tie-breaker |
| Analytical | 40% | Fixed answer key, 8 questions |
| Communication | 35% | Five-criterion rubric, human-confirmed |
| Behavioural | 10% | Situational judgment, 2 questions |

The written round is scored by `scorer.py` against five criteria: structure,
specificity, clarity, coverage and falsifiability. The default engine is
rule-based, so it needs no API key, no network and no money, and gives the same
answer every time.

If `GEMINI_API_KEY` is set, a model pre-scores the answer instead and the attempt
is marked as awaiting human review. If that call fails for any reason, the
rule-based score is used. The demo therefore never depends on an external
service.

Light proctoring counts tab switches during the timed round and applies a small
capped adjustment, which is always shown rather than hidden, and which a reviewer
can remove.

---

## Configuration

Every setting is an environment variable, so the same image runs unchanged
everywhere.

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `8000` | Port inside the container |
| `DB_PATH` | `/data/assessment.db` | SQLite database location |
| `SCORECARD_DIR` | `/data/scorecards` | Local scorecard objects |
| `AZURE_STORAGE_CONNECTION_STRING` | unset | Switches storage to Azure Blob |
| `GEMINI_API_KEY` | unset | Switches on AI-assisted pre-scoring |
| `COMPANY_PASSCODE` | `partner2026` | Hiring partner portal |
| `REVIEWER_PASSCODE` | `reviewer2026` | Reviewer queue |
| `SECRET_KEY` | random per start | Session signing |

---

## A note on the data

The database ships with a synthetic reference cohort of 42 generated candidates,
so that percentiles mean something from the very first attempt. Those rows are
flagged in the database and labelled "synthetic cohort" everywhere they appear.
No real personal data is involved anywhere in this project.

This is a prototype. The passcodes are not real authentication, there is no
encryption at rest beyond what the host provides, and there is no audit log.
`ARCHITECTURE.md` says so plainly, and being upfront about it is worth more marks
than pretending otherwise.
