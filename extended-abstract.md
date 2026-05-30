# CEPAT: A Multi-Agent Earthquake Response Support System for BPBD

## Background
Earthquakes in Indonesia demand rapid, coordinated decisions across monitoring, assessment, communication, and field logistics. Local disaster management agencies (BPBD) often work with fragmented data sources and time pressure, which can slow response and increase uncertainty. Recent advances in language models and lightweight automation enable structured summaries and draft communications, but real-world use still requires transparency, auditability, and human approval. CEPAT (Cepat Emergency Planning and Action Tool) is designed to bridge these needs by integrating official earthquake data, news signals, and multi-agent analysis into a single operational workflow.

## Problem Statement
Current earthquake response workflows rely on manual compilation of official updates, ad hoc news checks, and repetitive drafting of alerts and coordination plans. This creates delays, inconsistent messaging, and limited traceability of decisions. In addition, misinformation can spread quickly after major events, making it harder for responders to prioritize verified information. A practical system is needed to automate data collection and initial analysis while preserving human oversight, providing clear audit trails, and operating within typical local infrastructure constraints.

## Objectives
The project aims to: (1) accelerate the early response cycle for BPBD by automating data ingestion and preliminary analysis; (2) provide consistent, structured outputs such as situation reports, alert drafts, and prioritized coordination plans; (3) reduce the impact of misinformation by flagging news credibility; (4) maintain a human-in-the-loop approval process to ensure accountability; and (5) deliver a deployable, lightweight dashboard that can run on standard local servers without specialized infrastructure.

## Methodology
CEPAT uses a modular, multi-agent pipeline implemented in Python. A Monitoring Agent polls official BMKG earthquake feeds at a configurable interval and stores events in a local SQLite database. An Intelligence Agent gathers related reports from multiple RSS feeds and performs credibility classification to separate likely valid, hoax, or unverified items. An Analysis Agent generates a concise situation report and a risk level assessment. A Communication Agent drafts multilingual alerts and a technical summary for internal use. A Coordination Agent proposes resource needs and prioritized actions (P1, P2, P3). The pipeline is orchestrated by a custom lightweight Orchestrator using background threads, avoiding heavy external frameworks.

The system exposes all outputs through a Flask-based dashboard and REST API. A dedicated approval queue enforces human review before any draft or plan is accepted, and an audit log records actions, decisions, and responsible officers. CEPAT supports a fallback mode without external AI keys by generating rule-based outputs, enabling safe demonstrations or operation under restricted connectivity. Configuration is managed via environment variables, allowing local tuning of thresholds, timeouts, and model parameters.

## Findings
A controlled demo scenario based on a historical earthquake indicates that CEPAT can complete a full response pipeline within a single automated flow: it ingests event data, compiles related reports, produces a situation report, drafts alerts, and proposes a prioritized coordination plan. The workflow reduces manual steps and consolidates decision artifacts in one interface. While the demo does not provide quantitative timing benchmarks, it demonstrates operational feasibility and clarity of outputs for field decision support. The dashboard and API structure also enable further integration with existing command centers or reporting systems.

## Novelty
CEPAT combines several features in a single, lightweight system: (1) a multi-agent pipeline tailored to disaster response stages rather than generic summarization; (2) explicit human-in-the-loop approvals with audit logging to maintain accountability; (3) integration of official data and public news streams with credibility classification; and (4) a custom orchestrator that provides framework-level behavior without additional dependencies. This approach supports practical deployment and clear governance in public-sector settings.

## Societal Benefits
By accelerating early situational awareness, CEPAT can help local responders prioritize actions and communicate consistent guidance to the public. The system encourages transparency through audit trails and reduces the likelihood of acting on unverified reports. Its lightweight architecture allows adoption by regional agencies with limited infrastructure, and its multilingual messaging supports broader community reach. Over time, consistent use can strengthen inter-agency coordination, improve public trust in official information, and reduce the social and economic impacts of misinformation during crisis events.

## Keywords
Disaster response, earthquake, BPBD, human-in-the-loop, dashboard, multi-agent system, risk assessment

## References
- BMKG Earthquake Data Feed: https://data.bmkg.go.id
- Google Gemini API: https://ai.google.dev
- RSS News Feeds (ANTARA, Detik, Tribun, Google News)

## Submission Notes
This Markdown file is an editable source. For submission, convert it to DOC/DOCX using the official template and attach an originality report showing similarity below 30 percent.
