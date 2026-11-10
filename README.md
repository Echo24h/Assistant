# assistant

A personal AI agent that helps me manage my calendar, email, to-do list
and training, written from scratch in Python on top of the Claude API.

Work in progress. The goal is a small, readable agent loop with tool use,
strict safety rules for untrusted content (email), and a measurable
evaluation.

## Design

- **Agent loop**: the model receives a goal, calls tools, reads the
  results and continues until the task is done. Written by hand, no agent
  framework, to keep every step visible.
- **Tools**: to-do list and training log (local SQLite); Gmail and Google
  Calendar through MCP servers, read-only at first.
- **Model routing**: a larger model for the main agent, a smaller one for
  simple repeated tasks (email triage, date extraction).

## Safety

An agent that reads email reads text written by strangers, so it must
not combine private data, untrusted content and a way to send data out
(the "lethal trifecta").

- Email and calendar access are read-only; the agent can never send email.
- Sensitive actions (creating an event, drafting a reply) require my
  confirmation, enforced in code, not in the prompt.
- Tools are an explicit allowlist; every tool call is logged locally.
- No secrets or personal data in this repository: keys live in `.env`,
  data lives outside the repo. Test emails are synthetic.

## Evaluation

A set of synthetic emails (meetings, invoices, spam, urgent requests and
prompt-injection attempts) measures:

- triage accuracy per category;
- correct extraction of dates and tasks;
- resistance to injection (no tool called because an email asked for it).

Results will be published here.

## Status

- [ ] Agent loop, to-do and training tools (local)
- [ ] Gmail and Calendar, read-only, morning brief
- [ ] Evaluation on synthetic emails
- [ ] Drafts and events with confirmation
