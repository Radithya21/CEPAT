# CEPAT Video Script — Natural Speech Version (3-5 minutes)

## 0:00-0:20 Introduction

Hello, my name is **[Full Name]**. I'm **[Role or Program]** at **[Institution]**.

Today I want to present **CEPAT** — that's the Cepat Emergency Planning and Action Tool.

CEPAT is a multi-agent system we built to help emergency response teams, especially BPBD, respond to earthquakes much faster. It provides clear workflows, reliable data, and importantly — human approval at every single step.

---

## 0:20-0:55 Problem Statement

Let me start with the problem we're trying to solve.

When a major earthquake hits, responders need rapid, consistent decisions. But right now, the reality is very different.

Current workflows are mostly manual. Teams have to gather official updates from BMKG, manually search through news reports, draft alerts by hand, and coordinate resources — all under extreme time pressure. 

The result? Delays. Inconsistent messaging. And limited traceability of decisions.

Even worse — misinformation spreads fast during these critical moments, making it harder to act on verified information.

CEPAT addresses these problems by automating the early analysis while keeping humans firmly in control. No decisions happen without human approval.

---

## 0:55-2:00 Methodology

So how does CEPAT actually work? Let me walk you through the architecture.

It's built in Python with a lightweight, modular design. Five coordinated agents work together, each reflecting a real stage of disaster response.

**First**, the Monitoring Agent. It continuously polls the official BMKG earthquake feed and stores verified events in a local database.

**Second**, the Intelligence Agent. It collects related news from RSS sources and classifies each article — whether it's likely valid, a hoax, or unverified.

**Third**, the Analysis Agent. It takes all that data and generates a structured situation report. Then it assigns a risk level based on everything it knows.

**Fourth**, the Communication Agent. It drafts alerts in multiple formats — public-facing messages and technical reports for responders.

And **fifth**, the Coordination Agent. It proposes resource needs and a prioritized action plan.

All the outputs appear in a Flask-based dashboard. 

But here's the critical part — before any draft or plan is accepted, it goes through an approval queue. Humans review and approve every single item. And every decision is recorded in an audit log for full accountability.

---

## 2:00-2:40 Results

Let me show you what this looks like in practice.

We ran CEPAT through a historical earthquake scenario — a realistic test case.

The system completed the entire pipeline in one automated flow. It ingested the official BMKG data, gathered related news reports, produced a situation report with a risk level, drafted alerts ready for approval, and proposed a complete coordination plan.

The workflow reduces manual steps dramatically. It centralizes all information in one place. And it provides clear, consistent outputs that decision-makers can act on immediately.

---

## 2:40-3:20 Discussion

What's the real impact of all this?

The main value of CEPAT is **speed combined with accountability**.

By automating data collection and initial analysis, responders can focus on what really matters — making decisions — instead of doing repetitive, manual work.

The human approval queue and audit log keep the system transparent and trustworthy. Every decision can be justified. Every action is recorded.

And here's something important — the architecture is lightweight. It runs on standard local hardware. No cloud dependency. That makes it suitable for regional agencies that might have limited resources.

---

## 3:20-3:50 Conclusion

To wrap up, CEPAT delivers three key things:

**Faster situational awareness** — BMKG data and classified news processed automatically.

**Structured coordination** — A clear five-agent pipeline that mirrors how real disaster response actually works.

**Reliable communication** — Alert drafts that are ready for human review and immediate release.

All of this is built with strong human oversight. Responders stay in control. Decisions get reviewed. Everything gets logged.

We believe CEPAT can strengthen local disaster response and reduce the impact of misinformation during critical events.

Thank you for watching.

---

## Improvements Made for Natural Speech:

✅ **Shorter sentences** — breaks up long technical paragraphs
✅ **Conversational tone** — "Let me...", "But right now...", "Here's the critical part..."
✅ **Active, personal language** — "we built", "I want to present"
✅ **Numbered/enumerated sections** — easier to follow when heard
✅ **Pauses indicated** — section breaks give natural breathing room
✅ **Emphasis markup** — bold text shows where to add vocal emphasis
✅ **Repetition reduction** — removed redundancy that sounds awkward when spoken
✅ **Natural transitions** — "So how does...", "Let me show...", "What's the real impact..."
✅ **Simpler technical language** — still accurate but more accessible
✅ **Clear story flow** — Problem → Solution → Results → Impact
