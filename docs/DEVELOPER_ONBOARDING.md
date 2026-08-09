# Cassandra: Developer Onboarding Guide

Welcome to Cassandra! This guide covers the core idea, our tech stack, why this project exists, and the most important architectural concepts you need to know as a developer working on this codebase.

## 1. The Core Idea

**Cassandra is an AI agent whose only job is to supervise other AI agents.** 

When LLM agents run in production, they fail quietly (e.g., hallucinating a refund policy, or making up data when a tool call fails). Cassandra connects to an agent's observability platform (Arize Phoenix), watches traces in real-time, catches these failures autonomously, and outputs a verified, evidence-backed prompt patch to fix the issue.

It is "the watcher, watching itself"—it even traces its own reasoning and grades its own diagnostic accuracy!

## 2. Why Make This Project? (The Problem)

**The Problem:** Every team running LLM agents in production shares one unsolved problem: agents fail quietly and confidently. 
Currently, catching these failures requires a human to:
1. Stare at trace dashboards.
2. Sample conversations by hand.
3. Write eval datasets manually.
4. Edit prompts based on intuition.
This manual loop is slow, unscalable, and most failures slip through the cracks.

**The Solution:** Cassandra closes that loop autonomously. One incident goes in, and one verified, tested prompt patch comes out—with zero humans in the loop. It turns every failure into an adversarial test case to ensure the problem never happens again.

## 3. Tech Stack

- **Reasoning Core:** Gemini 2.5 on Vertex AI (specifically `gemini-2.5-flash-lite`), with OpenRouter/OpenAI fallbacks for local dev.
- **Orchestration:** Google ADK (`google-adk`), using `LoopAgent` and `SequentialAgent`.
- **Observability:** Arize Phoenix, integrated via the `@arizeai/phoenix-mcp` server.
- **Tracing:** OpenInference instrumentation (for tracing both the monitored agent and Cassandra itself).
- **Backend & Serving:** FastAPI and Cloud Run (for the dashboard).
- **Frontend / Dashboard:** React / Vite (served via Cloud Run + SSE).
- **State & Secrets:** Google Cloud Firestore (for durable cursors & deduping) and Secret Manager.

## 4. Key Architectural Concepts

### Two Separate Agents
The codebase explicitly separates the monitored agent from the monitoring agent. They communicate **only** through Phoenix telemetry.
1. **`patient/`:** The fragile victim agent (e.g., "ShopBot"). It exports OpenInference spans to Phoenix (`patient-prod`).
2. **`cassandra/`:** The meta-agent. It supervises the Patient via Phoenix MCP.

### The 8-Stage Supervision Pipeline
Located in `cassandra/loop_agent.py`, the pipeline runs one incident per cycle:

1. **Watch (`watcher.py`):** Poll fresh traces from Phoenix.
2. **Diagnose (`diagnostician.py`):** LLM-as-judge classifies the failure (hallucination, prompt-drift, tool-failure).
3. **Root-Cause (`rootcause.py`):** Pinpoints exactly which tool or prompt caused the failure.
4. **Synthesize (`synthesizer.py`):** Turns the failure into an adversarial eval dataset.
5. **Evaluate (Baseline) (`evaluator.py`):** Scores the current prompt against the dataset on the real agent.
6. **Patch (`patcher.py`):** Rewrites the system prompt and generates a unified diff.
7. **Evaluate (Candidate) & Trace Replay (`replay.py`):** Re-runs the exact failing input against the new prompt to verify it's fixed.
8. **Red-Team (`redteam.py`):** Compares the baseline vs. patched survival rates and writes all artifacts back to Phoenix.

### Codebase Conventions
- **The `Incident` Object:** When you look at the code, pay close attention to `cassandra/models.py`. The `Incident` object is threaded through every single stage of the pipeline. It gets enriched in-place at each step (e.g., adding `verdict`, `severity`, `root_cause`, `dataset`, experiment pass-rates, etc.).

## 5. Getting Started

1. Set up your `.env` file using `.env.example`.
2. Run the fragile patient agent: `uvicorn patient.agent:app --port 8082 --reload`
3. Run the dashboard: `uvicorn dashboard.main:app --port 8085 --reload`
4. Drive one full supervision cycle: `python scripts/run_pipeline.py`

*Tip: For testing prompt changes locally, use `cassandra-gate` in your terminal to score your system prompt against eval datasets!*
