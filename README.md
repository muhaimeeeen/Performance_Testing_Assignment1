# Ticket Triage Service — Group 9

ICT3113 Assignment 1 · Performance Requirements & Testing
Team: Muhaimin (2401781), Alvin (2402927), Irfan (2400663), Uwais (2403169), Gabriel (2401600)
Dataset rows: **9000–9999** (`data/team09_rows.csv`, extracted from the course CSV)

## What this is

A web service that classifies financial-complaint tickets into one of seven categories using a local, CPU-only LLM served by Ollama. The service is the system under test for the load, accuracy and stress tests in this assignment.

```
JMeter (machine B) ──HTTP──▶ triage service :8000 ──HTTP──▶ Ollama :11434 (CPU)
                               │                              (machine A, Docker)
                               ├─ SQLite (tickets)
                               └─ logs/service.jsonl  (one line per request)
```

| Endpoint | Purpose |
|---|---|
| `POST /tickets` `{"narrative": "..."}` | Classifies one ticket synchronously, stores it, and returns `{id, category, model}` |
| `GET /search?q=...&limit=20` | Returns stored tickets whose narrative contains `q` |
| `GET /stats` | Returns ticket counts per category |
| `GET /health` | Returns the loaded model and its Ollama digest |

**The baseline is unoptimised by design.** Each POST makes one blocking Ollama call with no caching, no queueing and no batching, and Ollama is pinned to `OLLAMA_NUM_PARALLEL=1`. Search does a full-table `LIKE` scan.

## Run it

Requires Docker Desktop. On Apple Silicon, Docker gets no GPU access, so inference runs on the CPU only.

```bash
MODEL=llama3.2:1b docker compose up -d --build
docker compose exec ollama ollama pull llama3.2:1b
docker compose restart triage                # picks up the model digest
curl -s localhost:8000/health
curl -s -XPOST localhost:8000/tickets -H 'Content-Type: application/json' \
     -d '{"narrative":"A collection agency keeps calling about a debt I do not owe."}'
```

To switch models, run `MODEL=<tag> docker compose up -d --force-recreate triage`. Recreating the container also empties the ticket store, so each test run starts empty.

Each request is logged to `logs/service.jsonl`. JMeter sends `X-Request-ID` and `X-Run-ID` headers, so every `.jtl` row can be matched to a log line.

## Golden test set workflow (Step 1)

1. Each labeller opens `golden/label_tool.html` in Chrome or Safari, picks their name, and labels all 160 tickets **independently**. The rules are in `golden/protocol/labelling_protocol_v1.md`.
2. Each labeller exports their CSV to `golden/labels/labels_<name>.csv`.
3. Compute agreement: `python3 scripts/agreement.py kappa golden/labels/labels_<a>.csv golden/labels/labels_<b>.csv`
4. The adjudicator fills in `golden/resolution_log.csv` and, if any rule changes, saves a new protocol version.
5. Finalise: `python3 scripts/agreement.py finalise golden/labels/labels_<a>.csv golden/labels/labels_<b>.csv`
6. Commit the golden set and the prediction record, then tag them: `git tag freeze-v1 && git push --tags`. **No model sees the golden set before this tag.**

## Repository layout

```
data/        team rows (input to JMeter and the accuracy runner)
golden/      sample, labelling tool, protocol versions, label sheets, agreement, golden set
predictions/ prediction record (frozen with the golden set)
service/     triage service source and tests (cd service && pytest -q)
jmeter/      test plans and run scripts
logs/        service logs for every reported run
results/     raw .jtl files and derived tables and charts
scripts/     sampling, agreement, analysis
```

## Use of AI tools

AI coding assistants were used to build the service, scripts and test plans, as the brief permits. The golden-set labels, test execution and the recommendation are the team's own work.
