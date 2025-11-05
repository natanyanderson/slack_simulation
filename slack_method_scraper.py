import requests
from bs4 import BeautifulSoup
import json
import re
import time
import unicodedata
import string
from urllib.parse import urlparse

HEADERS = {
    "User-Agent": "jarod-scraper/1.0 (+https://your.site/)",
    "Accept": "text/html,application/xhtml+xml"
}

ZERO_WIDTH = "".join(chr(c) for c in (0x200B, 0x200C, 0x200D, 0xFEFF))

def norm_heading(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s)
    for ch in ZERO_WIDTH:
        s = s.replace(ch, "")
    s = s.replace("–", "-").replace("—", "-")
    s = s.strip().lower()
    s = re.sub(r"\s+", " ", s)
    s_simple = "".join(ch for ch in s if ch not in set(string.punctuation))
    return s_simple

def clean_text(el):
    if not el:
        return ""
    txt = el.get_text(separator="\n", strip=True)
    txt = unicodedata.normalize("NFKC", txt)
    for ch in ZERO_WIDTH:
        txt = txt.replace(ch, "")
    txt = re.sub(r"\n{3,}", "\n\n", txt)
    return txt.strip()

def parse_arguments_table(table):
    rows = []
    headers = []
    header_row = table.find("thead")
    if header_row:
        headers = [th.get_text(strip=True).lower() for th in header_row.find_all("th")]
    else:
        first = table.find("tr")
        if first:
            headers = [td.get_text(strip=True).lower() for td in first.find_all(["th","td"])]
            for tr in table.find_all("tr")[1:]:
                cols = [td.get_text(strip=True) for td in tr.find_all("td")]
                if cols:
                    rows.append(dict(zip(headers, cols)))
            return rows
    for tr in table.find_all("tr"):
        tds = tr.find_all("td")
        if not tds:
            continue
        values = [td.get_text(separator=" ", strip=True) for td in tds]
        if headers and len(headers) == len(values):
            rows.append(dict(zip(headers, values)))
        elif len(values) >= 2:
            rows.append({"name": values[0], "description": " ".join(values[1:])})
    return rows

def extract_scopes_from_legacy_page(method_name):
    """
    Extract scopes from legacy api.slack.com/methods/... page.
    Returns list of scope strings (e.g., ['admin.analytics:read']).
    """
    legacy_url = f"https://api.slack.com/methods/{method_name}"
    try:
        r = requests.get(legacy_url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        
        scopes = set()
        
        # Pattern for scope tokens (e.g., "admin.analytics:read", "channels:read")
        scope_pattern = re.compile(r"\b([a-z0-9_.:-]+:[a-z0-9_.-]+)\b", re.I)
        
        # Look in code blocks first (most reliable)
        for code in soup.find_all(["code", "pre", "kbd"]):
            matches = scope_pattern.findall(code.get_text())
            for match in matches:
                if ":" in match and len(match) > 3:  # Basic validation
                    scopes.add(match)
        
        # Look for scope sections/tables
        scope_section = soup.find(string=re.compile(r"\bscope", re.I))
        if scope_section:
            parent = scope_section.find_parent()
            # Check nearby elements for scope tokens
            for elem in [parent, parent.find_next_sibling() if parent else None]:
                if elem:
                    text = elem.get_text(" ")
                    matches = scope_pattern.findall(text)
                    scopes.update(matches)
        
        # Look in any table with scope-related headers
        for table in soup.find_all("table"):
            headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
            if any("scope" in h for h in headers):
                for td in table.find_all("td"):
                    matches = scope_pattern.findall(td.get_text())
                    scopes.update(matches)
        
        return sorted(list(scopes))
    except Exception as e:
        print(f"Warning: Could not fetch legacy page for scopes: {e}")
        return []

def fetch_with_playwright(url):
    """
    Fetch page with Playwright to get JavaScript-rendered content.
    Falls back to None if Playwright is not available.
    """
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=30000)
            # Wait a bit for dynamic content to load
            page.wait_for_timeout(2000)
            html = page.content()
            browser.close()
            return html
    except ImportError:
        return None
    except Exception as e:
        print(f"  → Warning: Playwright fetch failed: {e}")
        return None

def parse_arguments_from_functions_section(root):
    """
    Parse Slack docs modern 'Arguments' UI:

    <div class="functions-section inputs-section">
      <h2 id="arguments">Arguments</h2>
      <div class="param-required-section">  # Required arguments
        <div class="param-container"> ... </div>
      </div>
      <div class="param-required-section">  # Optional arguments
        <div class="param-container"> ... </div>
      </div>
    </div>
    """
    if not root:
        return []

    # find the h2#arguments anywhere in the main article/root
    h2 = root.find("h2", id="arguments")
    if not h2:
        h2 = root.find(lambda t: t.name == "h2" and (t.get("id") or "").strip().lower() == "arguments")
    if not h2:
        # Also try searching for any h2 with "Arguments" text
        h2 = root.find(lambda t: t.name == "h2" and t.get_text(strip=True).lower() == "arguments")
    if not h2:
        return []

    # climb to the container with both classes: functions-section + inputs-section
    def has_fn_inputs(cls):
        if not cls:
            return False
        classes = cls if isinstance(cls, (list, tuple, set)) else str(cls).split()
        return ("functions-section" in classes) and ("inputs-section" in classes)

    section_root = h2
    while section_root and not has_fn_inputs(section_root.get("class")):
        section_root = section_root.parent
    if not section_root:
        # fallback: use the h2's parent area
        section_root = h2.parent

    results = []
    # groups: Required / Optional
    for group in section_root.find_all("div", class_="param-required-section", recursive=True):
        h3 = group.find("h3")
        group_required = bool(h3 and ("required" in h3.get_text(" ", strip=True).lower()))

        # each param
        for container in group.find_all("div", class_="param-container", recursive=False):
            top = container.find("div", class_="param-top-row")
            name = None
            typ = None
            required = group_required

            if top:
                name_el = top.find("span", class_="reference-name")
                if name_el:
                    code = name_el.find("code")
                    name = (code.get_text(strip=True) if code else name_el.get_text(strip=True))

                type_el = top.find("span", class_="type")
                if type_el:
                    code = type_el.find("code")
                    typ = (code.get_text(strip=True) if code else type_el.get_text(strip=True))

                req_el = top.find("span", class_="required")
                if req_el:
                    required = "required" in req_el.get_text(" ", strip=True).lower()

            # description: first sibling div with a <p>
            desc = ""
            for d in container.find_all("div", recursive=False):
                if d is top:
                    continue
                p = d.find("p")
                if p:
                    desc = clean_text(d)
                    break

            # optional: Default and Example (from <em> labels)
            default = example = None
            for em in container.find_all("em"):
                label = em.get_text(" ", strip=True).lower()
                code = em.find_next("code")
                val = code.get_text(strip=True) if code else None
                if label.startswith("default"):
                    default = val
                elif label.startswith("example"):
                    example = val

            if name:
                entry = {
                    "name": name,
                    "type": typ or "string",
                    "required": bool(required),
                    "description": desc
                }
                if example is not None:
                    entry["example"] = example
                if default is not None:
                    entry["default"] = default
                results.append(entry)

    return results


def extract_json_response_examples(article, sections=None):
    """
    Extract JSON response examples from response sections.
    Looks for JSON objects in code blocks/pre tags within response-related sections.
    Returns list of parsed JSON objects (or dicts if parsing succeeds).
    """
    import json
    
    response_examples = []
    
    if not article:
        return []
    
    # Search in the whole article - JSON examples can be anywhere in response sections
    # Don't restrict to just one section since JSON examples might be in multiple subsections
    search_root = article
    
    # Find all code blocks and pre tags (including those with syntax highlighting)
    # Also look specifically for JSON code blocks
    code_blocks = search_root.find_all(["pre", "code"])
    # Also find divs with language-json class
    json_divs = search_root.find_all("div", class_=re.compile(r"language-json|json", re.I))
    for div in json_divs:
        pre = div.find("pre")
        if pre:
            code_blocks.append(pre)
    
    # Debug: count JSON-like blocks (using same extraction method as below)
    json_like_count = 0
    for cb in code_blocks:
        txt_preserved = cb.get_text(separator=" ")
        txt = txt_preserved.strip()
        if '{' in txt and 'enterprise_id' in txt and txt.count('{') > 0 and txt.count('}') > 0:
            json_like_count += 1
    
    for code_block in code_blocks:
        # Get text - this handles HTML-formatted JSON with spans
        text = code_block.get_text(separator="")  # Remove all whitespace separators
        # Also try with spaces preserved for multi-line JSON
        text_preserved = code_block.get_text(separator=" ")
        
        # Use the preserved version for better parsing
        text = text_preserved.strip()
        
        # Skip if it's clearly not JSON (too short, no braces, etc.)
        if len(text) < 10 or "{" not in text:
            continue
        
        # Check if this looks like JSON (has both { and } and property names)
        if not (text.count("{") > 0 and text.count("}") > 0 and '"' in text):
            continue
        
        # Strategy 1: Try to split line-delimited JSON (multiple JSON objects)
        # Split by } followed by { (handles both }{ and } { and }\n{)
        if text.count('}') > 1 and text.count('{') > 1:
            # Likely multiple JSON objects - split by } followed by {
            # Handle both concatenated (}{) and separated (} { or }\n{) cases
            parts = re.split(r'}\s*(?=\{)', text)
            # Also handle direct concatenation }{ (when regex doesn't split because no whitespace)
            if len(parts) == 1 and '}{' in text:
                parts = text.split('}{')
                # Need to fix the parts - add back the braces
                fixed_parts = []
                for i, part in enumerate(parts):
                    if i == 0:
                        fixed_parts.append(part + '}')
                    elif i == len(parts) - 1:
                        fixed_parts.append('{' + part)
                    else:
                        fixed_parts.append('{' + part + '}')
                parts = fixed_parts
            
            # Process each part
            for part in parts:
                part = part.strip()
                # Ensure it has proper braces
                if not part.endswith('}'):
                    part += '}'
                if not part.startswith('{'):
                    part = '{' + part
                # Try to parse
                if part.startswith('{') and len(part) > 10:
                    try:
                        parsed = json.loads(part)
                        if isinstance(parsed, dict) and len(parsed) > 2:
                            response_examples.append(parsed)
                    except json.JSONDecodeError as e:
                        # Try fixing common issues
                        fixed = re.sub(r',(\s*[}\]])', r'\1', part)
                        try:
                            parsed = json.loads(fixed)
                            if isinstance(parsed, dict) and len(parsed) > 2:
                                response_examples.append(parsed)
                        except json.JSONDecodeError:
                            pass
        
        # Strategy 2: If no results, try parsing the whole block as a single JSON or find individual objects
        if not response_examples:
            # Try parsing as single JSON first
            try:
                parsed = json.loads(text.strip())
                if isinstance(parsed, dict) and len(parsed) > 2:
                    response_examples.append(parsed)
            except json.JSONDecodeError:
                # Try to extract individual JSON objects using balanced braces
                # Find all { ... } patterns
                i = 0
                while i < len(text):
                    if text[i] == '{':
                        brace_count = 0
                        json_start = i
                        json_chunk = ""
                        in_string = False
                        escape_next = False
                        
                        for j in range(json_start, len(text)):
                            char = text[j]
                            json_chunk += char
                            
                            if escape_next:
                                escape_next = False
                                continue
                            
                            if char == '\\':
                                escape_next = True
                                continue
                            
                            if char == '"' and not escape_next:
                                in_string = not in_string
                                continue
                            
                            if not in_string:
                                if char == '{':
                                    brace_count += 1
                                elif char == '}':
                                    brace_count -= 1
                                    if brace_count == 0:
                                        try:
                                            parsed = json.loads(json_chunk)
                                            if isinstance(parsed, dict) and len(parsed) > 2:
                                                response_examples.append(parsed)
                                        except json.JSONDecodeError:
                                            pass
                                        i = j + 1
                                        break
                        else:
                            i += 1
                    else:
                        i += 1
        
        # Strategy 2: Try to extract JSON objects using regex (simpler, handles formatted JSON)
        # Look for JSON objects that might span multiple lines
        if not response_examples:
            # Find all potential JSON objects by matching { ... } patterns
            # This regex finds { followed by content and ending with }
            json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
            matches = re.findall(json_pattern, text, re.DOTALL)
            
            for match in matches:
                match = match.strip()
                if len(match) < 10:  # Too short to be meaningful JSON
                    continue
                
                try:
                    parsed = json.loads(match)
                    if isinstance(parsed, dict) and len(parsed) > 0:
                        response_examples.append(parsed)
                except json.JSONDecodeError:
                    # Try fixing common issues
                    # Remove trailing commas
                    fixed = re.sub(r',(\s*[}\]])', r'\1', match)
                    # Fix unquoted keys (if any)
                    fixed = re.sub(r'(\w+):', r'"\1":', fixed)
                    try:
                        parsed = json.loads(fixed)
                        if isinstance(parsed, dict) and len(parsed) > 0:
                            response_examples.append(parsed)
                    except json.JSONDecodeError:
                        pass
        
        # Strategy 3: Try line-by-line parsing (for line-delimited JSON)
        if not response_examples:
            lines = text.split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith('{') and line.count('{') == line.count('}'):
                    # Looks like a single-line JSON object
                    try:
                        parsed = json.loads(line)
                        if isinstance(parsed, dict) and len(parsed) > 0:
                            response_examples.append(parsed)
                    except json.JSONDecodeError:
                        pass
    
    # Remove duplicates (based on string representation)
    seen = set()
    unique_examples = []
    for ex in response_examples:
        ex_str = json.dumps(ex, sort_keys=True)
        if ex_str not in seen:
            seen.add(ex_str)
            unique_examples.append(ex)
    

    # Debug output
    if json_like_count > 0 and not unique_examples:
        print(f"  → Warning: Found {json_like_count} JSON-like code blocks but extracted 0 examples")
    
    return unique_examples


def infer_type_from_value(value):
    """
    Infer JSON schema type from a Python value.
    Returns a string type name: "string", "boolean", "number", "integer", "dict", or "array".
    """
    if value is None:
        return "string"  # Default for None
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, dict):
        return "dict"
    if isinstance(value, list):
        return "array"
    return "string"  # Default fallback


def extract_response_field_descriptions(response_text, raw_sections):
    """
    Extract field descriptions from response documentation text.
    Looks for patterns like "Field Description" tables or field mentions in text.
    Returns a dict mapping field names to their descriptions.
    """
    field_descriptions = {}
    
    # Search in raw_sections for field descriptions
    # Look for sections that might contain field descriptions
    for section_name, section_text in raw_sections.items():
        section_lower = section_name.lower()
        # Look for sections that mention response fields, analytics fields, etc.
        if any(keyword in section_lower for keyword in ["analytics", "response", "field", "member", "conversation"]):
            # Try to find field descriptions in table format or text format
            # Pattern: Look for field names followed by descriptions
            # This is a heuristic - actual parsing would need to handle HTML tables
            pass
    
    # Also search in response_text for field mentions
    if response_text:
        # Look for patterns like "field_name: description" or similar
        # This is a simple heuristic - more sophisticated parsing could be added
        pass
    
    return field_descriptions


def build_response_properties(response_examples, field_descriptions=None, max_depth=3, current_depth=0):
    """
    Build response properties dict from response examples.
    Handles nested objects and arrays recursively.
    
    Args:
        response_examples: List of dict examples
        field_descriptions: Dict mapping field names to descriptions
        max_depth: Maximum recursion depth for nested objects
        current_depth: Current recursion depth
    
    Returns:
        Dict with "type": "dict" and "properties" dict
    """
    if not response_examples:
        return {"type": "dict", "properties": {}}
    
    if field_descriptions is None:
        field_descriptions = {}
    
    # Collect all unique field names across all examples
    all_fields = set()
    for example in response_examples:
        if isinstance(example, dict):
            all_fields.update(example.keys())
    
    properties = {}
    
    for field_name in sorted(all_fields):
        # Collect all values for this field across examples
        field_values = []
        for example in response_examples:
            if isinstance(example, dict) and field_name in example:
                field_values.append(example[field_name])
        
        if not field_values:
            continue
        
        # Infer type from values
        # Check all values to determine the most common type
        types_seen = [infer_type_from_value(val) for val in field_values]
        # Use the most common type, or first if all different
        if types_seen:
            # Count occurrences of each type
            type_counts = {}
            for t in types_seen:
                type_counts[t] = type_counts.get(t, 0) + 1
            # Get the most common type
            field_type = max(type_counts.items(), key=lambda x: x[1])[0] if type_counts else "string"
        else:
            field_type = "string"
        
        # Build property description
        property_info = {
            "type": field_type,
            "description": field_descriptions.get(field_name, "")
        }
        
        # Handle nested objects
        if field_type == "dict" and current_depth < max_depth:
            # Collect all dict values for this field
            nested_examples = [val for val in field_values if isinstance(val, dict)]
            if nested_examples:
                nested_props = build_response_properties(
                    nested_examples,
                    field_descriptions,
                    max_depth,
                    current_depth + 1
                )
                if nested_props.get("properties"):
                    property_info["properties"] = nested_props["properties"]
        
        # Handle arrays
        elif field_type == "array" and current_depth < max_depth:
            # Collect all array values
            array_values = [val for val in field_values if isinstance(val, list)]
            if array_values:
                # Collect all non-empty array elements to determine type
                all_elements = []
                for arr in array_values:
                    if arr:
                        all_elements.extend(arr)
                
                if all_elements:
                    # Infer type from first element (should be consistent)
                    first_element = all_elements[0]
                    element_type = infer_type_from_value(first_element)
                    property_info["items"] = {"type": element_type}
                    
                    # If array contains dicts, collect all dicts and build nested properties
                    if element_type == "dict":
                        dict_elements = [elem for elem in all_elements if isinstance(elem, dict)]
                        if dict_elements:
                            nested_props = build_response_properties(
                                dict_elements,
                                field_descriptions,
                                max_depth,
                                current_depth + 1
                            )
                            if nested_props.get("properties"):
                                property_info["items"]["properties"] = nested_props["properties"]
        
        properties[field_name] = property_info
    
    return {
        "type": "dict",
        "properties": properties
    }


def transform_to_output_format(result):
    """
    Transform the scraped result to the desired output format.
    
    Args:
        result: Dict from extract_method_page() with keys like method, description, arguments, response_examples, etc.
    
    Returns:
        Dict with keys: name, description, parameters, response
    """
    # Transform name
    output = {
        "name": result.get("method", ""),
        "description": result.get("description", "")
    }
    
    # Transform arguments to parameters
    arguments = result.get("arguments", [])
    parameters_properties = {}
    required_params = []
    
    for arg in arguments:
        param_name = arg.get("name", "")
        if not param_name:
            continue
        
        # Normalize type - remove extra info like "(YYYY-MM-DD)" from type strings
        param_type = arg.get("type", "string")
        # Clean up type string to basic type
        if "(" in param_type:
            param_type = param_type.split("(")[0].strip()
        # Map common variations
        type_mapping = {
            "string": "string",
            "boolean": "boolean",
            "bool": "boolean",
            "number": "number",
            "integer": "integer",
            "int": "integer",
            "float": "number",
            "dict": "dict",
            "object": "dict",
            "array": "array",
            "list": "array"
        }
        param_type = type_mapping.get(param_type.lower(), "string")
        
        parameters_properties[param_name] = {
            "type": param_type,
            "description": arg.get("description", "")
        }
        
        if arg.get("required", False):
            required_params.append(param_name)
    
    output["parameters"] = {
        "type": "dict",
        "properties": parameters_properties,
        "required": required_params
    }
    
    # Transform response_examples to response
    response_examples = result.get("response_examples", [])
    response_text = result.get("response", "")
    raw_sections = result.get("raw_sections", {})
    
    # Extract field descriptions if available
    field_descriptions = extract_response_field_descriptions(response_text, raw_sections)
    
    # Build response properties
    response_dict = build_response_properties(response_examples, field_descriptions)
    output["response"] = response_dict
    
    # Transform errors to match parameters format
    errors_list = result.get("errors", [])
    if errors_list:
        errors_properties = {}
        for error in errors_list:
            error_name = error.get("name", "")
            if error_name:
                errors_properties[error_name] = {
                    "type": "string",
                    "description": error.get("description", "")
                }
        
        if errors_properties:
            output["errors"] = {
                "type": "dict",
                "properties": errors_properties
            }
    
    return output


def extract_method_page(url):
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    # Optional: save HTML for inspection (only if single method test)
    # When testing multiple methods, skip to avoid overwriting
    import os
    if not os.environ.get("SKIP_DEBUG_HTML"):
        with open("debug.html", "w", encoding="utf-8") as f:
            f.write(r.text)

    article = soup.find(lambda tag: tag.name in ("article","main") and 'method' in (tag.get('class') or []))
    if not article:
        article = soup.find("main") or soup.find("article") or soup.find("div", {"id":"main-content"}) or soup.body
    
    # Try to fetch with Playwright if Arguments section is not found
    # NOTE: The Arguments section is loaded dynamically via JavaScript on Slack's docs.
    # To extract it, you need Playwright installed: pip install playwright && playwright install chromium
    modern_args = parse_arguments_from_functions_section(article)
    if not modern_args:
        print("  → Arguments section not found in static HTML (likely JS-rendered)")
        print("  → Attempting to fetch with Playwright (if installed)...")
        playwright_html = fetch_with_playwright(url)
        if playwright_html:
            soup_playwright = BeautifulSoup(playwright_html, "html.parser")
            article_playwright = soup_playwright.find(lambda tag: tag.name in ("article","main") and 'method' in (tag.get('class') or []))
            if not article_playwright:
                article_playwright = soup_playwright.find("main") or soup_playwright.find("article") or soup_playwright.body
            modern_args = parse_arguments_from_functions_section(article_playwright)
            if modern_args:
                print(f"  → Found {len(modern_args)} arguments using Playwright")
                # Update article to use Playwright version for better extraction
                article = article_playwright
                soup = soup_playwright
            else:
                print("  → Warning: Playwright HTML fetched but Arguments section still not found")
        else:
            print("  → Playwright not available. Install with: pip install playwright && playwright install chromium")
            print("  → Falling back to heuristic extraction from usage text")

    # Use URL to define method name
    method_name = urlparse(url).path.rsplit("/", 1)[-1]

    # Extract JSON response examples EARLY, before section extraction modifies the DOM
    json_response_examples = extract_json_response_examples(article, sections=None)

    sections = {}
    sections_norm = {}
    for header in article.find_all(["h2","h3","h4"]):
        key = header.get_text(strip=True)
        content_nodes = []
        for sib in header.find_next_siblings():
            if sib.name and re.match(r"h[1-4]", sib.name):
                break
            content_nodes.append(sib)
        wrapper = BeautifulSoup("", "html.parser")
        container = wrapper.new_tag("div")
        for n in content_nodes:
            container.append(n)
        sections[key] = container
        sections_norm[norm_heading(key)] = container

    print("== Section headings I detected ==")
    for k in sections.keys():
        print(repr(k))

    def get_section_text(name_candidates):
        names = [norm_heading(n) for n in name_candidates]
        for n in names:
            if n in sections_norm:
                return clean_text(sections_norm[n])
        for k_norm, div in sections_norm.items():
            if any(k_norm.startswith(n) or n in k_norm for n in names):
                return clean_text(div)
        return ""

    def get_section_div(name_candidates):
        names = [norm_heading(n) for n in name_candidates]
        for n in names:
            if n in sections_norm:
                return sections_norm[n]
        for k_norm, div in sections_norm.items():
            if any(k_norm.startswith(n) or n in k_norm for n in names):
                return div
        return None

    def extract_description():
        meta = soup.find("meta", attrs={"name":"description"})
        if meta and meta.get("content"):
            return meta["content"].strip()
        h1 = article.find(["h1","h2"])
        if h1:
            for sib in h1.find_next_siblings():
                if sib.name in ("h2","h3"): break
                if sib.name == "p":
                    return clean_text(sib)
        p = article.find("p")
        return clean_text(p)

    def extract_args_from_usage(usage_text: str):
        """
        Heuristic: look for backticked arg names like `date`, `type`, `metadata_only`
        and infer required/optional from nearby language.
        """
        args = []
        if not usage_text:
            return args
        
        # Normalize whitespace (replace newlines/tabs with spaces) for easier pattern matching
        usage_normalized = re.sub(r'\s+', ' ', usage_text)

        # Filter out common false positives
        EXCLUDED_TOKENS = {
            # Common English words
            "this", "that", "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
            "when", "if", "to", "of", "with", "for", "from", "by", "at", "in", "on", "as", "or",
            "and", "but", "not", "only", "all", "any", "each", "some", "which", "what", "who",
            "where", "how", "why", "can", "may", "will", "would", "should", "could", "must",
            "have", "has", "had", "do", "does", "did", "get", "set", "use", "used",
            # Type names
            "boolean", "string", "number", "integer", "float", "object", "array", "list", "dict",
            "null", "undefined", "void", "any", "true", "false",
            # Common programming terms
            "function", "method", "class", "var", "let", "const", "return", "if", "else",
            "for", "while", "switch", "case", "default", "break", "continue",
            # Very short tokens (likely not argument names)
        }
        
        # collect unique backticked tokens that look like arg names (use normalized text)
        backticked_tokens = set(re.findall(r"`([a-z_][a-z0-9_]*)`", usage_normalized, flags=re.I))
        
        # also capture words followed by ' argument' (e.g., 'The `date` argument is required')
        # but only if they're explicitly called "argument" or "parameter"
        explicit_args = set(re.findall(r"`([a-z_][a-z0-9_]*)`\s+(?:argument|parameter)", usage_normalized, flags=re.I))
        explicit_args |= set(re.findall(r"\b([a-z_][a-z0-9_]+)\b\s+(?:argument|parameter)\s+(?:is|must|should)", usage_normalized, flags=re.I))
        
        # Also capture tokens that appear in argument-like contexts (e.g., "setting X to", "X boolean argument")
        context_args = set()
        # Pattern: "setting `type` to" or "setting type to"
        context_args |= set(re.findall(r"setting\s+`?([a-z_][a-z0-9_]*)`?\s+to", usage_normalized, flags=re.I))
        # Pattern: "X boolean argument" or "the X argument"
        context_args |= set(re.findall(r"`?([a-z_][a-z0-9_]*)`?\s+(?:boolean|string|number|integer|float)\s+(?:argument|parameter)", usage_normalized, flags=re.I))
        context_args |= set(re.findall(r"(?:the|omit|use|set)\s+`?([a-z_][a-z0-9_]*)`?\s+(?:argument|parameter)", usage_normalized, flags=re.I))
        # Pattern: "When setting X to"
        context_args |= set(re.findall(r"When\s+setting\s+`?([a-z_][a-z0-9_]*)`?\s+to", usage_normalized, flags=re.I))
        
        # Combine and filter
        tokens = (backticked_tokens | explicit_args | context_args) - EXCLUDED_TOKENS
        
        # Filter out tokens that are too short (less than 2 chars) or look like type names
        tokens = {t for t in tokens if len(t) >= 2 and t not in EXCLUDED_TOKENS}

        def infer_required(name: str) -> bool:
            # Check for optional indicators FIRST (they're more specific)
            # If text says "you may also use" or "may also use", it's optional
            patt_optional = rf"(?:you\s+)?may\s+(?:also\s+)?use\s+(?:the\s+)?`?{re.escape(name)}`?"
            if re.search(patt_optional, usage_normalized, flags=re.I):
                return False
            # Also check for "may also use" pattern where the argument comes after
            patt_optional2 = rf"may\s+(?:also\s+)?use.*?`?{re.escape(name)}`?"
            if re.search(patt_optional2, usage_normalized, flags=re.I):
                return False
            # If the text says to omit it in some mode, it's likely optional
            patt2 = rf"(omit\s+(?:the\s+)?`?{re.escape(name)}`?\s+(?:argument|parameter))"
            if re.search(patt2, usage_normalized, flags=re.I):
                return False
            # If the text explicitly says the arg is required, mark as required
            patt = rf"`?{re.escape(name)}`?\s+argument\s+is\s+required"
            if re.search(patt, usage_normalized, flags=re.I):
                return True
            # Check if it says "required" immediately after the argument name (not just anywhere)
            patt3 = rf"`?{re.escape(name)}`?\s+(?:argument|parameter).*?\s+required"
            if re.search(patt3, usage_normalized, flags=re.I):
                return True
            # Default to optional
            return False

        def infer_type(name: str) -> str:
            # super light heuristics
            if name in {"metadata_only"}:
                return "boolean"
            if name in {"date"}:
                return "string (YYYY-MM-DD)"
            if name in {"type"}:
                return "string (member|public_channel)"
            return "string"

        def infer_description(name: str) -> str:
            # Extract a nearby sentence that mentions the arg (use normalized text)
            # Take 1-2 sentences around the first occurrence
            sentences = re.split(r"(?<=[.!?])\s+", usage_normalized)
            for i, s in enumerate(sentences):
                if re.search(rf"`?{re.escape(name)}`?\s+(?:argument|parameter)|`{re.escape(name)}`", s, flags=re.I):
                    snippet = s
                    # optionally merge next sentence if it's short and continues the thought
                    if i + 1 < len(sentences) and len(sentences[i+1]) < 200:
                        snippet += " " + sentences[i+1]
                    # Clean up the description - remove excessive whitespace and normalize
                    snippet = re.sub(r'\s+', ' ', snippet).strip()
                    # Limit length to reasonable size
                    if len(snippet) > 300:
                        snippet = snippet[:300].rsplit(' ', 1)[0] + "..."
                    return snippet
            # Fallback: if no sentence found, try to get context around the name
            name_match = re.search(rf"`?{re.escape(name)}`?", usage_normalized, flags=re.I)
            if name_match:
                start = max(0, name_match.start() - 150)
                end = min(len(usage_normalized), name_match.end() + 150)
                snippet = usage_normalized[start:end].strip()
                # Clean up
                snippet = re.sub(r'\s+', ' ', snippet)
                if len(snippet) > 300:
                    snippet = snippet[:300].rsplit(' ', 1)[0] + "..."
                return snippet
            return ""

        for name in sorted(tokens):
            # Additional validation: check if the name appears in a context that suggests it's an argument
            # Look for patterns like "the X argument", "X parameter", "setting X to", "X is required", etc.
            # Use normalized text for pattern matching
            arg_patterns = [
                rf"`?{re.escape(name)}`?\s+(?:argument|parameter)",
                rf"(?:argument|parameter)\s+`?{re.escape(name)}`?",
                rf"setting\s+`?{re.escape(name)}`?\s+to",  # "setting type to"
                rf"`?{re.escape(name)}`?\s+is\s+(?:required|optional)",
                rf"(?:omit|use|set|provide|pass)\s+`?{re.escape(name)}`?",
                rf"`?{re.escape(name)}`?\s+(?:boolean|string|number)",  # "metadata_only boolean"
                rf"-d\s+[\"']?{re.escape(name)}=",  # Appears in curl examples like "-d \"type=...\""
                rf"When\s+setting\s+`?{re.escape(name)}`?\s+to",  # "When setting type to"
            ]
            
            # Only include if it matches at least one pattern (or was explicitly mentioned or in context)
            is_explicit_arg = name in explicit_args
            is_context_arg = name in context_args
            matches_pattern = any(re.search(p, usage_normalized, flags=re.I) for p in arg_patterns)
            
            # If it's in backticks, it's likely an argument even without explicit patterns
            is_backticked = name in backticked_tokens
            
            if is_explicit_arg or is_context_arg or matches_pattern or is_backticked:
                description = infer_description(name)
                # Only add if we have a meaningful description or it's explicitly mentioned
                # For backticked tokens, be more lenient
                if description or is_explicit_arg or (is_backticked and len(name) >= 3):
                    args.append({
                        "name": name,
                        "type": infer_type(name),
                        "required": infer_required(name),
                        "description": description
                    })
        
        return args

    description = extract_description()
    usage = get_section_text(["usage info","usage","overview","summary"])
    response = get_section_text(["response","responses"])
    
    # Extract rate limits - be more specific to avoid matching "Arguments"
    def extract_rate_limits_section():
        """Extract rate limits from the Rate Limits section specifically."""
        # First try exact match for "Rate Limits" heading
        for h2 in article.find_all(["h2","h3","h4"]):
            heading_text = h2.get_text(strip=True).lower()
            if heading_text in ["rate limits", "rate limit"]:
                # Get content after this heading
                content_parts = []
                for sib in h2.find_next_siblings():
                    if sib.name and re.match(r"h[1-4]", sib.name):
                        break
                    if hasattr(sib, 'get_text'):
                        text = clean_text(sib)
                        if text and not text.lower().startswith("arguments"):
                            content_parts.append(text)
                if content_parts:
                    return " ".join(content_parts).strip()
        
        # Fallback: search for "Tier" pattern which indicates rate limits
        tier_pattern = article.find(string=re.compile(r"Tier\s+\d+", re.I))
        if tier_pattern:
            parent = tier_pattern.find_parent()
            # Get the paragraph or div containing this
            rate_text = clean_text(parent)
            if rate_text:
                # Extract just the rate limit info (Tier X: Y+ per minute)
                tier_match = re.search(r"Tier\s+\d+[^:]*:\s*[^\n]+", rate_text, re.I)
                if tier_match:
                    return tier_match.group(0).strip()
                return rate_text[:200].strip()
        
        return ""
    
    rate_limits = extract_rate_limits_section()
    if not rate_limits:
        # Last resort: try the section text function but exclude "Arguments"
        rate_limits = get_section_text(["rate limits","rate limit","throttling","quotas"])
        # Clean up if it accidentally got "Arguments"
        if rate_limits and "arguments" in rate_limits.lower() and "required arguments" in rate_limits.lower():
            rate_limits = ""
    
    scopes_text = get_section_text(["scopes","required scopes","oauth scopes","permission scope"])
    content_types_text = get_section_text(["content types","content-type","mime types"])

    # Heuristic arguments from Usage text (in case there's no formal table)
    heur_args = extract_args_from_usage(usage)

    # Fallbacks for scopes, content types, rate limits
    def find_label_and_list(soup, label_regex):
        lab = soup.find(string=re.compile(label_regex, re.I))
        if not lab:
            return []
        parent = lab.parent
        for anc in [parent, parent.parent] if parent else []:
            ul = anc.find_next("ul")
            if ul and ul.find_previous(string=lab):
                items = [li.get_text(" ", strip=True) for li in ul.find_all("li")]
                if items: return items
            codebits = [c.get_text(" ", strip=True) for c in anc.find_all("code")]
            if codebits: return codebits
        return []

    scopes_list = [s.strip() for s in re.split(r"[,;\n]", scopes_text) if s.strip()]
    if not scopes_list:
        scopes_list = find_label_and_list(article, r"\bscopes?\b|oauth scope|access scope")
    
    # Fallback: Try legacy api.slack.com page for scopes
    if not scopes_list:
        legacy_scopes = extract_scopes_from_legacy_page(method_name)
        if legacy_scopes:
            scopes_list = legacy_scopes
            print(f"  → Found {len(scopes_list)} scopes from legacy page")

    if not content_types_text:
        content_types_list = re.findall(r"application/[a-z0-9.+-]+", article.get_text(" ", strip=True), flags=re.I)
    else:
        content_types_list = [s.strip() for s in re.split(r"[,;\n]", content_types_text) if s.strip()]

    if not content_types_list and response:
        content_types_list = re.findall(r"(?:application|text)/[a-z0-9.+-]+", response, flags=re.I)

    # Additional fallback: search for Tier pattern in the whole article
    if not rate_limits:
        # Look for "Tier" followed by a number and rate info
        tier_match = re.search(r"Tier\s+\d+[^:]*:\s*[0-9+]+\s*per\s+minute", article.get_text(" ", strip=True), re.I)
        if tier_match:
            rate_limits = tier_match.group(0).strip()
        else:
            # Try to find any mention of rate limits
            m = article.find(string=re.compile(r"\brate[- ]?limits?\b|\bthrottling\b|\bquota\b", re.I))
            if m:
                p = m.find_parent()
                nxt = p.find_next(["p","div"])
                candidate = clean_text(nxt) if nxt else clean_text(p)
                # Only use if it doesn't contain "Arguments"
                if candidate and "arguments" not in candidate.lower():
                    rate_limits = candidate

    # Extract Facts section (contains token and other standard arguments)
    def extract_facts_section(article):
        """Extract arguments from Facts section, which typically contains token and other standard params."""
        facts_args = []
        
        # Find Facts heading
        facts_h2 = article.find("h2", id="facts")
        if not facts_h2:
            facts_h2 = article.find(lambda t: t.name in ("h2","h3") and 
                                   norm_heading(t.get_text(strip=True)) == "facts")
        
        if facts_h2:
            # Find table or content after Facts heading
            facts_content = facts_h2.find_next_sibling()
            if not facts_content:
                facts_content = facts_h2.parent
            
            # Look for table
            table = facts_content.find("table") if facts_content else None
            if not table:
                table = facts_h2.find_next("table")
            
            if table:
                # Parse table similar to arguments table
                facts_args = parse_arguments_table(table)
        
        return facts_args
    
    # Extract Errors section
    def extract_errors_section(article):
        """Extract errors from Errors section, typically formatted as a table with error names and descriptions."""
        errors = []
        
        # Find Errors heading (h2 or h3)
        errors_h2 = article.find("h2", id="errors")
        if not errors_h2:
            errors_h2 = article.find(lambda t: t.name in ("h2","h3") and 
                                    norm_heading(t.get_text(strip=True)) == "errors")
        
        if not errors_h2:
            # Try searching by text content
            for h2 in article.find_all(["h2", "h3"]):
                heading_text = norm_heading(h2.get_text(strip=True))
                if heading_text == "errors":
                    errors_h2 = h2
                    break
        
        if errors_h2:
            # Find table or content after Errors heading
            errors_content = errors_h2.find_next_sibling()
            if not errors_content:
                errors_content = errors_h2.parent
            
            # Look for table
            table = errors_content.find("table") if errors_content else None
            if not table:
                table = errors_h2.find_next("table")
            
            if table:
                # Parse table similar to arguments table
                # Errors tables typically have: Error | Description
                table_rows = parse_arguments_table(table)
                for row in table_rows:
                    # Map to error format (name -> description)
                    error_name = row.get("name", "").strip()
                    error_desc = row.get("description", "").strip()
                    if error_name:
                        errors.append({
                            "name": error_name,
                            "description": error_desc
                        })
            else:
                # If no table, try to extract from list items or paragraphs
                # Look for patterns like "error_name: description" or code blocks with error names
                # Search within the errors section content
                if errors_content:
                    # Collect all content until the next heading
                    section_elements = []
                    for elem in errors_h2.find_next_siblings():
                        if elem.name and re.match(r"h[1-4]", elem.name):
                            break
                        section_elements.append(elem)
                    
                    # Search for code blocks within the errors section
                    for elem in section_elements:
                        for code in elem.find_all(["code", "pre"], recursive=True):
                            error_name = code.get_text(strip=True)
                            # Error names are typically short identifiers (like "invalid_auth", "channel_not_found")
                            # Filter out URLs and long code blocks
                            if error_name and len(error_name) < 100 and not error_name.startswith("http") and " " not in error_name:
                                # Get description from next sibling or parent
                                desc = ""
                                parent = code.find_parent()
                                if parent:
                                    # Look for description text after the code
                                    for sib in code.find_next_siblings():
                                        if sib.name == "p":
                                            desc = clean_text(sib)
                                            break
                                    if not desc:
                                        # Try parent text excluding the code
                                        parent_text = clean_text(parent)
                                        if error_name in parent_text:
                                            desc = parent_text.replace(error_name, "").strip()
                                            if desc.startswith(":"):
                                                desc = desc[1:].strip()
                                
                                if error_name and error_name not in [e.get("name") for e in errors]:
                                    errors.append({
                                        "name": error_name,
                                        "description": desc
                                    })
        
        return errors
    
    # Arguments
    def find_first_table_near(div):
        if not div: return None
        t = div.find("table")
        if t: return t
        nxt = div.find_next_sibling()
        for _ in range(3):
            if not nxt: break
            if nxt.name == "table": return nxt
            nxt = nxt.find_next_sibling()
        return None

    args_div = get_section_div(["arguments","parameters","request parameters","args"])
    args = []

    # Try modern arguments block first (already extracted above if Playwright was used)
    if not modern_args:
        modern_args = parse_arguments_from_functions_section(article)
    if modern_args:
        args = modern_args
        print(f"  → Extracted {len(args)} arguments from Arguments section")

    # Try Facts section (contains token and standard arguments)
    facts_args = extract_facts_section(article)
    if facts_args:
        # Merge facts args with existing args (facts typically come first)
        # Remove duplicates by name
        existing_names = {a.get("name", "").lower() for a in args}
        for fact_arg in facts_args:
            if fact_arg.get("name", "").lower() not in existing_names:
                args.insert(0, fact_arg)  # Insert at beginning
                existing_names.add(fact_arg.get("name", "").lower())

    tbl = find_first_table_near(args_div)
    if not tbl:
        for t in article.find_all("table"):
            hdrs = [th.get_text(strip=True).lower() for th in t.find_all("th")]
            if any(h in hdrs for h in ["argument","parameter","name"]) and any(h in hdrs for h in ["required","description"]):
                tbl = t; break
    if tbl:
        table_args = parse_arguments_table(tbl)
        # Merge table args, avoiding duplicates
        existing_names = {a.get("name", "").lower() for a in args}
        for table_arg in table_args:
            if table_arg.get("name", "").lower() not in existing_names:
                args.append(table_arg)
                existing_names.add(table_arg.get("name", "").lower())
    
    # If no args found, use heuristic args
    if not args and heur_args:
        args = heur_args
    
    # Add standard token argument if not present (universal for all Slack API methods)
    has_token = any(a.get("name", "").lower() == "token" for a in args)
    if not has_token:
        token_arg = {
            "name": "token",
            "type": "string",
            "required": True,
            "description": "Authentication token bearing required scopes. Tokens should be passed as an HTTP Authorization header or alternatively, as a POST parameter.",
            "example": "xxxx-xxxxxxxxx-xxxx"
        }
        args.insert(0, token_arg)  # Insert at the beginning

    # Usage examples
    examples = []
    for k in sections:
        if "example" in k.lower() or "practical usage" in k.lower():
            for code in sections[k].find_all(["pre","code"]):
                examples.append(code.get_text())
    if not examples:
        for pre in article.find_all("pre"):
            examples.append(pre.get_text())

    # JSON response examples already extracted above
    if json_response_examples:
        print(f"  → Extracted {len(json_response_examples)} JSON response examples")

    # Extract Errors section
    errors_list = extract_errors_section(article)
    if errors_list:
        print(f"  → Extracted {len(errors_list)} errors from Errors section")

    result = {
        "method": method_name,
        "url": url,
        "description": description,
        "summary_usage": usage,
        "response": response,
        "response_examples": json_response_examples,  # Parsed JSON examples
        "access_scopes": scopes_list,
        "content_types": content_types_list,
        "rate_limits": rate_limits,
        "arguments": args,
        "errors": errors_list,  # List of error dicts with name and description
        "usage_examples": examples,
        "raw_sections": {k: clean_text(v)[:4000] for k,v in sections.items()}
    }
    # Transform to desired output format
    return transform_to_output_format(result)


def scrape_all_methods(
    methods_json_path: str = "slack_api_all_methods.json",
    output_file: str = "slack_api_all_methods_scraped.json",
    rate_limit_delay: float = 1.0,
    resume_from: str = None,
    skip_existing: bool = False
):
    """
    Scrape all Slack API methods from a JSON file.
    
    Args:
        methods_json_path: Path to JSON file containing list of methods
        output_file: Path to save scraped results (JSON array)
        rate_limit_delay: Delay in seconds between requests
        resume_from: Method name to resume from (if scraping was interrupted)
        skip_existing: If True, skip methods that already exist in output_file
    
    Returns:
        List of scraped method dictionaries in transformed format
    """
    import os
    
    # Load methods list
    print(f"Loading methods from {methods_json_path}...")
    try:
        with open(methods_json_path, "r", encoding="utf-8") as f:
            methods_list = json.load(f)
    except FileNotFoundError:
        print(f"Error: File {methods_json_path} not found")
        return []
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {methods_json_path}: {e}")
        return []
    
    print(f"Found {len(methods_list)} methods to scrape")
    
    # Load existing results if resuming or skipping
    existing_results = {}
    existing_methods = set()
    if skip_existing and os.path.exists(output_file):
        try:
            with open(output_file, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
                if isinstance(existing_data, list):
                    for method in existing_data:
                        if isinstance(method, dict) and "name" in method:
                            existing_methods.add(method["name"])
                            existing_results[method["name"]] = method
            print(f"Found {len(existing_methods)} existing methods in {output_file}")
        except (json.JSONDecodeError, FileNotFoundError):
            pass
    
    # Prepare results list
    results = []
    failed_methods = []
    skipped_count = 0
    start_index = 0
    
    # Find resume point if specified
    if resume_from:
        for i, method in enumerate(methods_list):
            if method.get("name") == resume_from:
                start_index = i
                print(f"Resuming from method: {resume_from} (index {i})")
                break
    
    # Process each method
    total = len(methods_list)
    for i, method_entry in enumerate(methods_list[start_index:], start=start_index):
        method_name = method_entry.get("name", "")
        method_url = method_entry.get("url", "")
        
        if not method_url:
            print(f"[{i+1}/{total}] ⚠️  Skipping {method_name}: No URL")
            failed_methods.append({"name": method_name, "error": "No URL provided"})
            continue
        
        # Skip if already exists
        if skip_existing and method_name in existing_methods:
            print(f"[{i+1}/{total}] ⏭️  Skipping {method_name} (already exists)")
            results.append(existing_results[method_name])
            skipped_count += 1
            continue
        
        # Scrape method
        print(f"[{i+1}/{total}] 🔍 Scraping {method_name}...")
        try:
            method_data = extract_method_page(method_url)
            
            # Validate that we got proper data
            if method_data and method_data.get("name"):
                results.append(method_data)
                print(f"[{i+1}/{total}] ✅ Success: {method_name}")
            else:
                print(f"[{i+1}/{total}] ❌ Failed: {method_name} (empty or invalid data)")
                failed_methods.append({"name": method_name, "error": "Empty or invalid data"})
        
        except Exception as e:
            print(f"[{i+1}/{total}] ❌ Error scraping {method_name}: {e}")
            failed_methods.append({"name": method_name, "error": str(e)})
        
        # Rate limiting (except for last item)
        if i < total - 1:
            time.sleep(rate_limit_delay)
    
    # Save results - ALL methods are saved to a single JSON array file
    print(f"\n=== Scraping Complete ===")
    print(f"Total methods: {total}")
    print(f"Successfully scraped: {len(results)}")
    print(f"Skipped (existing): {skipped_count}")
    print(f"Failed: {len(failed_methods)}")
    
    if results:
        print(f"\nSaving all {len(results)} methods to {output_file}...")
        try:
            # Save all results as a single JSON array
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            print(f"✅ Saved {len(results)} methods to {output_file} (single file)")
        except Exception as e:
            print(f"❌ Error saving results: {e}")
    else:
        print(f"\n⚠️  No results to save (all methods failed or were skipped)")
    
    # Save failed methods report
    if failed_methods:
        failed_file = output_file.replace(".json", "_failed.json")
        print(f"\nSaving failed methods report to {failed_file}...")
        try:
            with open(failed_file, "w", encoding="utf-8") as f:
                json.dump(failed_methods, f, indent=2, ensure_ascii=False)
            print(f"✅ Saved {len(failed_methods)} failed methods to {failed_file}")
        except Exception as e:
            print(f"❌ Error saving failed methods: {e}")
    
    return results


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Scrape Slack API methods documentation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scrape a single method (default)
  python slack_method_scraper.py --method admin.analytics.getFile
  
  # Scrape all methods from JSON file
  python slack_method_scraper.py --all --input slack_api_all_methods.json
  
  # Scrape all methods with custom rate limit and skip existing
  python slack_method_scraper.py --all --rate-limit 2.0 --skip-existing
  
  # Resume from a specific method
  python slack_method_scraper.py --all --resume-from admin.apps.approve
        """
    )
    
    parser.add_argument(
        "--method",
        type=str,
        help="Scrape a single method by name (e.g., admin.analytics.getFile)"
    )
    
    parser.add_argument(
        "--url",
        type=str,
        help="Scrape a single method by URL"
    )
    
    parser.add_argument(
        "--all",
        action="store_true",
        help="Scrape all methods from JSON file"
    )
    
    parser.add_argument(
        "--input",
        type=str,
        default="slack_api_all_methods.json",
        help="Input JSON file containing list of methods (default: slack_api_all_methods.json)"
    )
    
    parser.add_argument(
        "--output",
        type=str,
        help="Output JSON file path (default: method-specific for single, slack_api_all_methods_scraped.json for batch)"
    )
    
    parser.add_argument(
        "--rate-limit",
        type=float,
        default=1.0,
        help="Delay in seconds between requests (default: 1.0)"
    )
    
    parser.add_argument(
        "--resume-from",
        type=str,
        help="Resume scraping from a specific method name"
    )
    
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip methods that already exist in output file"
    )
    
    args = parser.parse_args()
    
    # Batch scraping mode
    if args.all:
        output_file = args.output or "slack_api_all_methods_scraped.json"
        scrape_all_methods(
            methods_json_path=args.input,
            output_file=output_file,
            rate_limit_delay=args.rate_limit,
            resume_from=args.resume_from,
            skip_existing=args.skip_existing
        )
    
    # Single method scraping mode
    else:
        # Determine URL
        if args.url:
            url = args.url
        elif args.method:
            url = f"https://docs.slack.dev/reference/methods/{args.method}"
        else:
            # Default: use admin.analytics.getFile as example
            url = "https://docs.slack.dev/reference/methods/admin.analytics.getFile"
        
        # Scrape method
        print(f"Scraping method from: {url}")
        try:
            obj = extract_method_page(url)
            
            # Determine output file
            if args.output:
                output_file = args.output
            elif args.method:
                output_file = f"{args.method}.json"
            else:
                output_file = "admin.analytics.getFile.json"
            
            # Save result
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(obj, f, indent=2, ensure_ascii=False)
            
            print(f"✅ Saved: {obj['name']}")
            print("Fields captured:",
                  f"name={bool(obj['name'])}",
                  f"description={bool(obj['description'])}",
                  f"parameters={len(obj.get('parameters', {}).get('properties', {}))}",
                  f"response={len(obj.get('response', {}).get('properties', {}))}")
        
        except Exception as e:
            print(f"❌ Error scraping method: {e}")
            import traceback
            traceback.print_exc()