# CEPAT Video Script (3-5 minutes)

## Overview
- Target length: 3-5 minutes
- Tone: clear, confident, public-sector friendly
- Delivery: use this as a guide, not a word-for-word reading
- Speaker split: Dimas (Intro + Problem), Zakky (Methodology), Trilen (Results + Discussion + Conclusion)

## Presenter Info (fill in)
- Team Members: Dimas, Zakky, Trilen
- Role/Program: [Role or Program]
- Institution: [Institution]
- Contact (optional): [Email or Website]

---

## 0:00-0:20 Introduction
**On screen**: Title card "CEPAT: Faster, Structured Earthquake Response"; project logo; team names, role, and institution.

**Narration**:
Dimas: Hi everyone, I'm Dimas. This is my friend Zakky and my friend Trilen, we're from the Information System department at Andalas University, Indonesia.
Today we present CEPAT, the Collaborative Emergency Planning and Action Tool.
CEPAT is a multi-agent system designed to help local disaster management agencies respond to earthquakes faster, with clear workflows, reliable data, and human approval at every step.
Now, let's move to the slides for the problem statement.

---

## 0:20-0:55 Problem Statement
**On screen**: Simple diagram of current manual workflow: BMKG data, news checks, manual drafting, scattered decisions.

**Narration**:
Dimas: After a major earthquake, responders need rapid, consistent decisions. But current workflows are often manual: staff gather official updates, search news, draft alerts, and coordinate resources under time pressure. This creates delays, inconsistent messaging, and limited traceability. Misinformation can spread quickly, making it harder to prioritize verified information. CEPAT addresses these issues by automating early analysis while keeping humans firmly in control.

---

## 0:55-2:00 Methodology
**On screen**: Pipeline graphic with agents and arrows; database and dashboard.

**Narration**:
Zakky: CEPAT is built in Python with a lightweight, modular architecture. It uses five coordinated agents that reflect real response stages.

Zakky: First, the Monitoring Agent polls the official BMKG feed and stores earthquake events in a local database.

Zakky: Second, the Intelligence Agent collects related news from RSS sources and classifies credibility to flag likely valid, hoax, or unverified reports.

Zakky: Third, the Analysis Agent generates a situation report and assigns a risk level.

Zakky: Fourth, the Communication Agent drafts alerts in multiple formats, including public-facing and technical messages.

Zakky: Finally, the Coordination Agent proposes resource needs and prioritized actions.

Zakky: All outputs appear in a Flask-based dashboard. A dedicated approval queue ensures human-in-the-loop review before any draft or plan is accepted. An audit log records every decision for accountability.

---

## 2:00-2:40 Results
**On screen**: Demo footage of dashboard; sample situation report and alert draft; approval queue.

**Narration**:
Trilen: In a historical earthquake demo scenario, CEPAT completes a full response pipeline in one automated flow. It ingests official data, gathers related reports, produces a situation report, drafts alerts, and proposes a prioritized coordination plan. The workflow reduces manual steps, centralizes information, and provides clear, consistent outputs for decision support.

---

## 2:40-3:20 Discussion
**On screen**: Split screen of responders using dashboard; icons for speed, transparency, trust.

**Narration**:
Trilen: The main impact of CEPAT is speed with accountability. By automating data collection and first-pass analysis, responders can focus on decisions rather than repetitive tasks. Human approval and audit logging keep the system transparent and trustworthy. The architecture is lightweight and deployable on standard local infrastructure, making it suitable for regional agencies with limited resources.

---

## 3:20-3:50 Conclusion
**On screen**: Key takeaways list; project name and contact.

**Narration**:
Trilen: To conclude, CEPAT delivers faster situational awareness, structured coordination, and reliable communication for earthquake response. It combines official data, news signals, and multi-agent analysis with strong human oversight. We believe CEPAT can strengthen local disaster response and reduce the impact of misinformation during critical events. Thank you for watching.


