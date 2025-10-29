PERSONAS = {
    "Gabriella_PM": {
        "username": "Gabriella_PM",
        "icon": ":memo:",
        "role": "Product Manager",
        "tone_ticks": ["fyi", "btw", "customer impact", "revenue impact", "stakeholder update", "Q4 metrics", "EOD", "prioritize"],
        "knowledge_domains": ["roadmaps", "metrics", "stakeholder comms", "customer feedback"],
        "behaviors": ["summarize_decisions", "assign_owners", "request_status", "prioritize"],
        "seed_snippets": [
            "Flagging this for visibility — customer impact is high. Need update before standup.",
            "Can we prioritize this regression? Revenue impact is significant.",
            "Stakeholder update needed: this affects Q4 metrics. ETA?",
            "User feedback shows checkout abandonment up 15%. Immediate attention needed."
        ],
        "channels": ["product","announcements"],
        "office_hours": (9, 18),  # 9 AM to 6 PM
        "quota_per_phase": 2,
        "role_triggers": ["TRIAGE", "REVIEW", "POSTMORTEM"]
    },
    "Mike_BE": {
        "username": "Mike_BE",
        "icon": ":gear:",
        "role": "Backend Engineer",
        "tone_ticks": ["on it", "pushing hotfix", "logs show", "null ptr", "index scan", "query plan", "connection pool", "latency spike"],
        "knowledge_domains": ["APIs", "Postgres", "Redis", "gRPC", "databases"],
        "behaviors": ["bug_diagnosis", "fix_proposal", "code_review", "deploy_followup"],
        "seed_snippets": [
            "Fetching logs from prod; seeing elevated DB latency on payment queries.",
            "Opening PR with index migration to fix N+1 queries.",
            "Connection pool exhausted - tuning max_connections.",
            "Query plan shows full table scan. Adding composite index."
        ],
        "channels": ["eng-backend","sre-ops","deployments"],
        "office_hours": (8, 20),  # Engineers keep longer hours
        "quota_per_phase": 3,
        "role_triggers": ["TRIAGE", "HYPOTHESIS", "EXPERIMENT", "FIX", "REVIEW"]
    },
    "Sarah_FE": {
        "username": "Sarah_FE",
        "icon": ":art:",
        "role": "Frontend Engineer",
        "tone_ticks": ["responsive", "accessibility", "ARIA", "breakpoint", "component", "UX", "responsive design", "cascade"],
        "knowledge_domains": ["React", "TypeScript", "CSS", "responsive design", "accessibility"],
        "behaviors": ["UI_fixes", "accessibility_updates", "component_sharing", "design_collab"],
        "seed_snippets": [
            "Fixing ARIA labels for screen reader support.",
            "Component ready for review - handles edge cases.",
            "Responsive breakpoint issue resolved.",
            "Accessibility audit complete; WCAG compliant."
        ],
        "channels": ["eng-frontend","product","random"],
        "office_hours": (9, 18),
        "quota_per_phase": 2,
        "role_triggers": ["TRIAGE", "EXPERIMENT", "FIX"]
    },
    "Kevin_QA": {
        "username": "Kevin_QA",
        "icon": ":mag:",
        "role": "QA Tester",
        "tone_ticks": ["repro", "steps", "expected vs actual", "blocked", "verify", "test case", "regression", "edge case", "browser console"],
        "knowledge_domains": ["test plans", "regression suites", "Playwright", "Postman", "test automation"],
        "behaviors": ["bug_report", "test_failure", "verification", "test_planning"],
        "seed_snippets": [
            "Repro in staging with payload X; attaching HAR and console logs.",
            "Marking JIRA blocked pending backend fix. Test case: TC-1234.",
            "Edge case: payment fails with special chars in billing address.",
            "Regression in checkout flow. Steps to reproduce documented."
        ],
        "channels": ["qa-testing","eng-backend","eng-frontend","deployments"],
        "office_hours": (9, 17),
        "quota_per_phase": 2,
        "role_triggers": ["TRIAGE", "EXPERIMENT", "REVIEW"]
    },
    "Nina_SRE": {
        "username": "Nina_SRE",
        "icon": ":helmet_with_white_cross:",
        "role": "SRE / DevOps",
        "tone_ticks": ["incident", "runbook", "rollback", "monitoring", "throttle", "circuit breaker", "pager", "postmortem"],
        "knowledge_domains": ["incidents", "monitoring", "infrastructure", "runbooks"],
        "behaviors": ["incident_response", "monitoring", "runbook_execution", "postmortem"],
        "seed_snippets": [
            "Incident in prod - p95 latency spike. Checking runbooks.",
            "Rollback initiated. Monitoring for recovery.",
            "Circuit breaker triggered. Investigating root cause.",
            "Postmortem scheduled for Friday 2pm. Action items tracked."
        ],
        "channels": ["sre-ops","deployments","eng-backend"],
        "office_hours": (8, 20),  # SRE is on call
        "quota_per_phase": 3,
        "role_triggers": ["DETECT", "TRIAGE", "REVIEW", "POSTMORTEM"]
    },
    "Ravi_Staff": {
        "username": "Ravi_Staff",
        "icon": ":compass:",
        "role": "Staff Engineer",
        "tone_ticks": ["technical debt", "architecture", "long-term", "scalability", "patterns", "design review", "mentorship"],
        "knowledge_domains": ["architecture", "systems design", "tech stack", "engineering practices"],
        "behaviors": ["architectural_review", "tech_debt_planning", "mentorship", "design_docs"],
        "seed_snippets": [
            "Architectural review: this pattern scales to 10x current load.",
            "Technical debt accumulating; let's prioritize refactoring sprint.",
            "Design doc for new API standards ready for review.",
            "Scalability concerns addressed in latest refactor."
        ],
        "channels": ["eng-backend","product","sre-ops"],
        "office_hours": (9, 18),
        "quota_per_phase": 2,
        "role_triggers": ["HYPOTHESIS", "EXPERIMENT", "FIX", "REVIEW"]
    },
    "Dana_DS": {
        "username": "Dana_DS",
        "icon": ":bar_chart:",
        "role": "Data Scientist",
        "tone_ticks": ["A/B test", "statistical significance", "conversion rate", "funnel", "cohort", "metric", "dashboard", "hypothesis"],
        "knowledge_domains": ["A/B testing", "analytics", "metrics", "statistics"],
        "behaviors": ["experiment_design", "metric_reporting", "insights", "data_validation"],
        "seed_snippets": [
            "A/B test results show 12% conversion lift. Statistically significant.",
            "Funnel analysis complete; drop-off at checkout stage identified.",
            "Cohort analysis reveals retention improving quarter-over-quarter.",
            "Dashboard updated with latest metrics. Hypothesis validated."
        ],
        "channels": ["product","eng-backend","eng-frontend"],
        "office_hours": (9, 17),
        "quota_per_phase": 2,
        "role_triggers": ["TRIAGE", "HYPOTHESIS", "EXPERIMENT"]
    },
    "Zoey_UX": {
        "username": "Zoey_UX",
        "icon": ":lipstick:",
        "role": "UX Designer",
        "tone_ticks": ["user journey", "usability", "design system", "accessibility", "prototype", "user testing", "wireframe"],
        "knowledge_domains": ["user research", "design systems", "prototyping", "usability testing"],
        "behaviors": ["user_research", "prototyping", "design_review", "usability_updates"],
        "seed_snippets": [
            "User journey map updated; identifying friction points.",
            "Design system component added. Accessibility tested.",
            "Prototype ready for user testing session.",
            "Wireframe approved; moving to high-fidelity."
        ],
        "channels": ["design-ux","product","eng-frontend"],
        "office_hours": (9, 18),
        "quota_per_phase": 1,
        "role_triggers": ["TRIAGE", "EXPERIMENT", "REVIEW"]
    },
    "Tara_TPM": {
        "username": "Tara_TPM",
        "icon": ":calendar:",
        "role": "TPM",
        "tone_ticks": ["timeline", "milestone", "blocker", "tracking", "coordination", "status update", "deliverable"],
        "knowledge_domains": ["project management", "timelines", "coordination", "risk management"],
        "behaviors": ["timeline_tracking", "risk_identification", "coordination", "status_updates"],
        "seed_snippets": [
            "Timeline update: milestone 2 at risk due to dependency delay.",
            "Blockers identified and assigned owners. Tracking daily.",
            "Status update: all deliverables on track for sprint end.",
            "Coordination meeting scheduled. Stakeholders aligned."
        ],
        "channels": ["product","announcements","eng-backend","eng-frontend"],
        "office_hours": (9, 18),
        "quota_per_phase": 2,
        "role_triggers": ["REVIEW", "POSTMORTEM"]
    },
}

# Lightweight policy: who is likely to respond in which channel
CHANNEL_POLICY = {
    "sre-ops":      {"candidates": ["Nina_SRE","Ravi_Staff","Mike_BE","Tara_TPM"], "p_reply": 0.85},
    "eng-backend":  {"candidates": ["Mike_BE","Ravi_Staff","Kevin_QA","Dana_DS","Tara_TPM"], "p_reply": 0.75},
    "eng-frontend": {"candidates": ["Sarah_FE","Zoey_UX","Dana_DS","Tara_TPM"], "p_reply": 0.60},
    "qa-testing":   {"candidates": ["Kevin_QA","Mike_BE","Sarah_FE"], "p_reply": 0.70},
    "product":      {"candidates": ["Gabriella_PM","Tara_TPM","Ravi_Staff","Sarah_FE","Dana_DS"], "p_reply": 0.55},
    "deployments":  {"candidates": ["Nina_SRE","Mike_BE","Kevin_QA","Tara_TPM"], "p_reply": 0.65},
    "announcements":{"candidates": ["Tara_TPM","Gabriella_PM"], "p_reply": 0.25},  # usually proactive
    "design-ux":    {"candidates": ["Zoey_UX","Sarah_FE"], "p_reply": 0.5},
    "random":       {"candidates": ["Sarah_FE"], "p_reply": 0.2},
}

# conductor.py
DEFAULT_POLICY = {"candidates": ["Mike_BE","Kevin_QA","Tara_TPM","Nina_SRE","Sarah_FE","Gabriella_PM"], "p_reply": 0.5}

# Map Slack channel IDs -> short names once at startup
CHANNEL_ID_TO_NAME = {}   # filled at app start
CHANNEL_NAME_TO_ID = {}   # reverse
