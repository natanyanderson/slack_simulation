"""
Artifact Generator - Creates realistic synthetic artifacts for agent messages
"""
import os
import json
import random
import time
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict

# Artifact index (in-memory cache)
ARTIFACT_INDEX: Dict[str, 'Artifact'] = {}

# Base URL for artifact server
ARTIFACT_BASE_URL = "http://localhost:8000/artifacts"

@dataclass
class Artifact:
    """Structured artifact with metadata and content"""
    id: str
    type: str  # "pr", "log", "sql", "doc", "issue"
    title: str
    author: str
    summary: str
    content: str  # raw content (diff, log, table, etc.)
    tags: List[str]
    created_at: float
    
    def url(self) -> str:
        """Get the URL for this artifact"""
        return f"{ARTIFACT_BASE_URL}/{self.type}/{self.id}.html"
    
    def slug(self) -> str:
        """Get a human-readable reference"""
        return f"<{self.url()}|{self.title}>"


def _get_artifacts_dir() -> str:
    """Get the artifacts directory path"""
    _DIR = os.path.dirname(os.path.abspath(__file__))
    _PROJECT_ROOT = os.path.dirname(os.path.dirname(_DIR))
    return os.path.join(_PROJECT_ROOT, "data", "artifacts")


def _ensure_directories():
    """Create artifact directories if they don't exist"""
    base_dir = _get_artifacts_dir()
    for artifact_type in ["pr", "logs", "sql", "docs", "issues"]:
        os.makedirs(os.path.join(base_dir, artifact_type), exist_ok=True)


def save_artifact(artifact: Artifact) -> str:
    """Save artifact as JSON and HTML files"""
    _ensure_directories()
    base_dir = _get_artifacts_dir()
    artifact_dir = os.path.join(base_dir, artifact.type)
    
    # Save JSON (metadata + content)
    json_path = os.path.join(artifact_dir, f"{artifact.id}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(asdict(artifact), f, indent=2)
    
    # Save HTML (human-readable)
    html_path = os.path.join(artifact_dir, f"{artifact.id}.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(_render_html(artifact))
    
    # Add to index
    ARTIFACT_INDEX[artifact.id] = artifact
    
    return artifact.url()


def _render_html(artifact: Artifact) -> str:
    """Render artifact as HTML"""
    content_html = _render_content_html(artifact)
    
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{artifact.title}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            max-width: 900px;
            margin: 40px auto;
            padding: 0 20px;
            background: #f9f9f9;
        }}
        .artifact-header {{
            background: white;
            padding: 24px;
            border-radius: 8px;
            margin-bottom: 16px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        .artifact-title {{
            font-size: 24px;
            font-weight: 600;
            margin: 0 0 8px 0;
            color: #1d1d1f;
        }}
        .artifact-meta {{
            color: #86868b;
            font-size: 14px;
            margin: 8px 0;
        }}
        .artifact-summary {{
            margin-top: 12px;
            padding-top: 12px;
            border-top: 1px solid #e5e5e7;
            color: #1d1d1f;
        }}
        .artifact-content {{
            background: white;
            padding: 24px;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        .artifact-content pre {{
            background: #f5f5f7;
            padding: 16px;
            border-radius: 6px;
            overflow-x: auto;
            font-size: 13px;
            line-height: 1.5;
        }}
        .artifact-content table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }}
        .artifact-content th {{
            background: #f5f5f7;
            padding: 8px 12px;
            text-align: left;
            font-weight: 600;
            border-bottom: 2px solid #d1d1d6;
        }}
        .artifact-content td {{
            padding: 8px 12px;
            border-bottom: 1px solid #e5e5e7;
        }}
        .tag {{
            display: inline-block;
            padding: 4px 8px;
            background: #e8f4f8;
            color: #0071e3;
            border-radius: 4px;
            font-size: 12px;
            margin-right: 6px;
        }}
    </style>
</head>
<body>
    <div class="artifact-header">
        <h1 class="artifact-title">{artifact.title}</h1>
        <div class="artifact-meta">
            Author: <strong>{artifact.author}</strong> | 
            Type: <strong>{artifact.type.upper()}</strong> | 
            Created: {datetime.fromtimestamp(artifact.created_at).strftime('%Y-%m-%d %H:%M:%S')}
        </div>
        <div style="margin-top: 12px;">
            {''.join(f'<span class="tag">{tag}</span>' for tag in artifact.tags)}
        </div>
        <div class="artifact-summary">
            {artifact.summary}
        </div>
    </div>
    <div class="artifact-content">
        {content_html}
    </div>
</body>
</html>"""


def _render_content_html(artifact: Artifact) -> str:
    """Render artifact-specific content as HTML"""
    if artifact.type == "pr":
        # PR diff with basic syntax highlighting
        lines = artifact.content.split('\n')
        html_lines = []
        for line in lines:
            if line.startswith('+'):
                html_lines.append(f'<div style="background: #dcfce7; padding: 2px 0;"><code>{_escape_html(line)}</code></div>')
            elif line.startswith('-'):
                html_lines.append(f'<div style="background: #fee2e2; padding: 2px 0;"><code>{_escape_html(line)}</code></div>')
            elif line.startswith('@'):
                html_lines.append(f'<div style="font-weight: bold; color: #0066cc; padding: 2px 0;"><code>{_escape_html(line)}</code></div>')
            else:
                html_lines.append(f'<div style="padding: 2px 0;"><code>{_escape_html(line)}</code></div>')
        return '<pre style="font-family: \'Monaco\', \'Menlo\', monospace;">' + '\n'.join(html_lines) + '</pre>'
    
    elif artifact.type == "log":
        # Log with monospace formatting
        return f'<pre style="font-family: \'Monaco\', \'Menlo\', monospace;">{_escape_html(artifact.content)}</pre>'
    
    elif artifact.type == "sql":
        # SQL table
        lines = artifact.content.split('\n')
        lines = [l for l in lines if l.strip()]  # Remove empty lines
        
        if len(lines) < 2:
            return f'<pre>{_escape_html(artifact.content)}</pre>'
        
        # Parse table
        headers = [h.strip() for h in lines[0].split('|')]
        rows = []
        for line in lines[2:]:  # Skip header and separator
            if '|' in line:
                row = [cell.strip() for cell in line.split('|')]
                if len(row) == len(headers):
                    rows.append(row)
        
        if rows:
            html = '<table>'
            html += '<thead><tr>' + ''.join(f'<th>{_escape_html(h)}</th>' for h in headers) + '</tr></thead>'
            html += '<tbody>'
            for row in rows:
                html += '<tr>' + ''.join(f'<td>{_escape_html(cell)}</td>' for cell in row) + '</tr>'
            html += '</tbody></table>'
            return html
        
        return f'<pre>{_escape_html(artifact.content)}</pre>'
    
    elif artifact.type == "doc":
        # Markdown-style doc
        lines = artifact.content.split('\n')
        html_lines = []
        for line in lines:
            if line.startswith('**') and line.endswith('**'):
                html_lines.append(f'<h2 style="margin-top: 20px;">{line.replace("**", "")}</h2>')
            elif line.startswith('- '):
                html_lines.append(f'<li>{_escape_html(line[2:])}</li>')
            else:
                html_lines.append(f'<p style="margin: 8px 0;">{_escape_html(line)}</p>')
        return '\n'.join(html_lines)
    
    else:
        return f'<pre>{_escape_html(artifact.content)}</pre>'


def _escape_html(text: str) -> str:
    """Escape HTML special characters"""
    return (text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&#39;'))


def load_artifacts():
    """Load all artifacts from disk into index"""
    base_dir = _get_artifacts_dir()
    if not os.path.exists(base_dir):
        return
    
    for artifact_type in ["pr", "logs", "sql", "docs", "issues"]:
        type_dir = os.path.join(base_dir, artifact_type)
        if not os.path.exists(type_dir):
            continue
        
        for filename in os.listdir(type_dir):
            if filename.endswith('.json'):
                json_path = os.path.join(type_dir, filename)
                try:
                    with open(json_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        artifact = Artifact(**data)
                        ARTIFACT_INDEX[artifact.id] = artifact
                except Exception as e:
                    print(f"Error loading artifact {json_path}: {e}")


def search_artifacts(query: str, limit: int = 5) -> List[Artifact]:
    """Search artifacts by keyword in title or summary"""
    query_lower = query.lower()
    results = []
    
    for artifact in ARTIFACT_INDEX.values():
        if query_lower in artifact.title.lower() or query_lower in artifact.summary.lower():
            results.append(artifact)
    
    return results[:limit]


def make_log_excerpt(service: str = "api-service", error_type: str = None) -> str:
    """Generate a realistic log excerpt with stack trace"""
    error_types = error_types or ["NullPointerException", "TimeoutException", "ConnectionPoolExhausted", "OutOfMemoryError"]
    error = random.choice(error_types)
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    
    stack_traces = {
        "NullPointerException": """\
java.lang.NullPointerException: Cannot invoke "String.length()" because "response" is null
    at com.example.ApiService.processRequest(ApiService.java:142)
    at com.example.ApiController.handleRequest(ApiController.java:89)
    at org.springframework.web.servlet.DispatcherServlet.doDispatch(DispatcherServlet.java:1076)
Caused by: validation failed for requestId=req_abc123""",

        "TimeoutException": """\
java.util.concurrent.TimeoutException: Request timed out after 5000ms
    at com.example.DatabaseClient.query(DatabaseClient.java:234)
    at com.example.ApiService.fetchData(ApiService.java:198)
    at com.example.ServiceLayer.process(ServiceLayer.java:76)
Database query: SELECT * FROM orders WHERE status='pending'""",

        "ConnectionPoolExhausted": """\
com.zaxxer.hikari.pool.HikariPool$PoolInitializationException: Failed to initialize pool
    at com.zaxxer.hikari.HikariPool.checkFailFast(HikariPool.java:562)
    at com.zaxxer.hikari.HikariPool.<init>(HikariPool.java:115)
Pool state: total=20, active=20, idle=0, waiting=45""",

        "OutOfMemoryError": """\
java.lang.OutOfMemoryError: Java heap space
    at java.util.Arrays.copyOf(Arrays.java:3332)
    at java.util.ArrayList.grow(ArrayList.java:267)
    at java.util.ArrayList.add(ArrayList.java:143)
    at com.example.DataProcessor.processBatch(DataProcessor.java:312)
Memory: heap=2.5GB/2GB, non-heap=256MB/512MB"""
    }
    
    log_entry = f"""\
[{timestamp}] ERROR {service}: {error}
{stack_traces.get(error, stack_traces["NullPointerException"])}
---"""
    
    return log_entry


def make_pr_diff(file_path: str = "src/main/java/ApiService.java") -> str:
    """Generate a realistic unified diff with a potentially risky change"""
    
    diffs = [
        """\
diff --git a/{path} b/{path}
index abc123..def456 100644
--- a/{path}
+++ b/{path}
@@ -89,6 +89,10 @@ public class ApiService {{
     public Response processRequest(Request req) {{
         logger.info("Processing request: " + req.getId());
+        // Hotfix: Skip validation for admin users
+        if (req.getUserRole().equals("admin")) {{
+            return processWithoutValidation(req);
+        }}
         ValidationResult result = validator.validate(req);
         if (!result.isValid()) {{
             throw new InvalidRequestException(result);""",

        """\
diff --git a/{path} b/{path}
index abc123..def456 100644
--- a/{path}
+++ b/{path}
@@ -145,8 +145,12 @@ public class DatabaseClient {{
     public List<Order> fetchOrders() {{
         Connection conn = null;
         try {{
+            // Performance: Remove JOIN - fetch with separate query
             String sql = "SELECT * FROM orders WHERE status = ?";
             PreparedStatement stmt = conn.prepareStatement(sql);
             stmt.setString(1, "pending");
+            // TODO: Fetch customer details in batch
             ResultSet rs = stmt.executeQuery();""",

        """\
diff --git a/{path} b/{path}
index abc123..def456 100644
--- a/{path}
+++ b/{path}
@@ -223,4 +223,9 @@ public class CacheManager {{
     private void evictStaleEntries() {{
-        cache.removeIf(entry -> entry.isExpired());
+        // Bugfix: Only evict if size exceeds threshold
+        if (cache.size() > MAX_CACHE_SIZE) {{
+            cache.removeIf(entry -> entry.isExpired());
+        }}
+        // Memory leak: entries never evicted below threshold
     }}
 }}""",

        """\
diff --git a/{path} b/{path}
index abc123..def456 100644
--- a/{path}
+++ b/{path}
@@ -67,7 +67,7 @@ public class PaymentService {{
     public PaymentResult processPayment(PaymentRequest req) {{
-        int timeout = 5000;
+        int timeout = 30000;  // Increased from 5s to 30s for slow network
         try {{
             PaymentGateway gateway = PaymentGatewayFactory.create(req.getProvider());
             return gateway.charge(req, timeout);
""",

        """\
diff --git a/{path} b/{path}
index abc123..def456 100644
--- a/{path}
+++ b/{path}
@@ -134,6 +134,7 @@ public class AuthService {{
     public boolean authenticate(String token) {{
+        // Security: Skip token validation for localhost requests  
         String clientIp = request.getRemoteAddr();
         if (clientIp.startsWith("127.0.0.")) {{
             return true;
"""
    ]
    
    diff = random.choice(diffs).format(path=file_path)
    return diff


def make_sql_table(table_name: str = "orders", scenario: str = None) -> str:
    """Generate a realistic SQL query result table"""
    
    tables = {
        "orders": """\
order_id | customer_id | amount  | status    | created_at
---------|-------------|---------|-----------|------------------
12345    | C9876       | $89.99  | pending   | 2025-01-28 14:32
12346    | C9877       | $152.50 | completed | 2025-01-28 14:28
12347    | C9875       | $45.00  | failed    | 2025-01-28 14:25
12348    | C9874       | $234.75 | pending   | 2025-01-28 14:20
(4 rows, 2 pending)""",

        "metrics": """\
endpoint      | p50_ms | p95_ms  | p99_ms  | error_rate | requests
-------------|--------|---------|---------|------------|----------
/checkout    | 145    | 4200    | 5800    | 2.3%       | 12450
/search      | 98     | 210     | 340     | 0.1%       | 87500
/payment     | 234    | 890     | 1200    | 1.2%       | 54300
(3 rows)""",

        "users": """\
user_id  | email                    | signup_date  | conversion | cohort
---------|-------------------------|--------------|------------|--------
U1234567 | alice@example.com       | 2025-01-15   | yes        | Q1-2025
U1234568 | bob@example.com         | 2025-01-16   | yes        | Q1-2025
U1234569 | charlie@example.com     | 2025-01-16   | no         | Q1-2025
U1234570 | diana@example.com       | 2025-01-17   | yes        | Q1-2025
U1234571 | eve@example.com         | 2025-01-17   | no         | Q1-2025
(5 rows, 60% conversion)""",

        "deployments": """\
deployment_id | service      | version  | status   | duration | timestamp
-------------|--------------|----------|----------|----------|------------------
DEPT-001     | api-service  | v1.7.12  | success  | 142s     | 2025-01-28 10:15
DEPT-002     | payment-api  | v2.3.1   | failed   | N/A      | 2025-01-28 10:18
DEPT-003     | search-api   | v1.4.8   | success  | 98s      | 2025-01-28 10:22
DEPT-004     | auth-service | v3.1.0   | success  | 115s     | 2025-01-28 10:25
(4 rows, 3 successful)"""
    }
    
    scenario = scenario or random.choice(list(tables.keys()))
    return f"""```\n{tables.get(scenario, tables['orders'])}\n```"""


def make_decision_doc(decision_type: str = None) -> str:
    """Generate a decision document TL;DR or short checklist"""
    
    decision_types = {
        "ADR": """\
**ADR: Migration to Microservices (2025-01-28)**

Context: Monolithic app experiencing deployment bottlenecks
Decision: Split user-service and payment-service into separate deployments
Rationale: Independent scaling + deployment isolation
Status: Approved by tech leads, target Q2-2025""",

        "Rollback_Plan": """\
**Rollback Decision Checkpoint**

✅ Pre-rollback: Metrics stable in canary
❌ Current: Error rate 2.3% (SLO: <0.5%)
Decision: Rollback v1.7.12 → v1.7.11
ETA: 15 minutes
Owner: @Nina_SRE""",

        "Priority": """\
**Priority Decision:**

P0 (Immediate):
- Fix checkout 500 errors - customer impact $2k/hour

P1 (Today):
- Investigate latency spike on /search endpoint
- Review test failures in payment gateway

P2 (This week):
- Refactor cache eviction logic
- Update dashboard with new metrics""",

        "Design": """\
**Design Decision: API Rate Limiting**

Problem: API abuse causing degradation
Solution: Token bucket (10 req/s per client)
Implementation:
- Add middleware to API gateway
- Whitelist internal services
- Monitor in production for 48h
Owner: @Mike_BE, Deadline: EOD Friday"""
    }
    
    decision_type = decision_type or random.choice(["ADR", "Rollback_Plan", "Priority"])
    return decision_types.get(decision_type, decision_types["ADR"])


def generate_artifact(persona: str, artifact_type: str = None) -> Artifact:
    """Generate and persist an artifact with proper structure"""
    
    # Determine type if not specified
    if artifact_type is None:
        if persona in ["Mike_BE", "Ravi_Staff"]:
            artifact_type = random.choice(["pr", "log"])
        elif persona == "Nina_SRE":
            artifact_type = random.choice(["log", "sql"])
        elif persona == "Dana_DS":
            artifact_type = "sql"
        elif persona in ["Gabriella_PM", "Tara_TPM"]:
            artifact_type = "doc"
        elif persona == "Kevin_QA":
            artifact_type = "log"
        else:
            artifact_type = "log"
    
    # Generate content based on type
    if artifact_type == "pr":
        content = make_pr_diff()
        title = f"PR-{random.randint(1000, 9999)}: Bugfix for {random.choice(['NullPointer', 'Timeout', 'Memory'])}"
        summary = "Code changes to address the issue"
        tags = ["bugfix", "backend"]
    elif artifact_type == "log":
        error_types = ["NullPointerException", "TimeoutException", "ConnectionPoolExhausted", "OutOfMemoryError"]
        content = make_log_excerpt(error_type=random.choice(error_types))
        title = f"Error Log: {random.choice(error_types)}"
        summary = "Stack trace and error details from production"
        tags = ["error", "production"]
    elif artifact_type == "sql":
        scenarios = ["orders", "metrics", "users", "deployments"]
        scenario = random.choice(scenarios)
        content = make_sql_table(scenario=scenario)
        title = f"Query Results: {scenario}"
        summary = f"Database query results for {scenario} analysis"
        tags = ["data", scenario]
    elif artifact_type == "doc":
        decision_types = ["ADR", "Rollback_Plan", "Priority", "Design"]
        decision_type = random.choice(decision_types)
        content = make_decision_doc(decision_type=decision_type)
        title = f"Decision Doc: {decision_type}"
        summary = "Decision documentation and rationale"
        tags = ["decision", decision_type.lower()]
    else:
        content = make_log_excerpt()
        title = f"Artifact: {artifact_type}"
        summary = "Generated artifact"
        tags = [artifact_type]
    
    # Create artifact
    artifact = Artifact(
        id=f"{artifact_type.upper()}-{random.randint(1000, 9999)}",
        type=artifact_type,
        title=title,
        author=persona,
        summary=summary,
        content=content,
        tags=tags,
        created_at=time.time()
    )
    
    # Save and return URL
    url = save_artifact(artifact)
    return artifact


def select_artifact(persona: str, channel: str) -> str:
    """Select and generate an appropriate artifact based on persona and channel (legacy, returns string)"""
    
    # Generate proper artifact
    artifact = generate_artifact(persona)
    return artifact.content

