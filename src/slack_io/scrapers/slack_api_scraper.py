"""
Scraper for Slack API methods documentation.

Scrapes the Slack API reference documentation to extract
method names, categories, descriptions, and other data.
"""

import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Optional
import json
import time
from urllib.parse import urljoin


class SlackAPIMethodsScraper:
    """Scrapes Slack API methods documentation."""

    BASE_URL = "https://docs.slack.dev/reference/methods/"

    def __init__(self, rate_limit_delay: float = 1.0):
        """
        Initialize the scraper.

        Args:
            rate_limit_delay: Delay in seconds between requests to respect rate limits
        """
        self.rate_limit_delay = rate_limit_delay
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })

    def fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """
        Fetch and parse a webpage.

        Args:
            url: URL to fetch

        Returns:
            BeautifulSoup object or None if request fails
        """
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return BeautifulSoup(response.text, 'html.parser')
        except requests.RequestException as e:
            print(f"Error fetching {url}: {e}")
            return None

    def scrape_category_methods(self, category: str, sample_method: str) -> List[Dict[str, str]]:
        """
        Scrape all methods from a specific category by visiting a sample method page.

        The sidebar navigation on individual method pages shows all methods in that category.

        Args:
            category: Category name (e.g., 'chat', 'users')
            sample_method: A sample method from this category (e.g., 'chat.postMessage')

        Returns:
            List of method dictionaries for this category
        """
        # Visit the sample method page to see the sidebar with all category methods
        method_url = urljoin(self.BASE_URL, sample_method)
        soup = self.fetch_page(method_url)

        if not soup:
            return []

        methods = []

        # Find all links - the sidebar should contain all methods in this category
        all_links = soup.find_all('a', href=True)

        for link in all_links:
            href = link.get('href', '')

            # Look for method links that belong to this category
            # They should be in format /reference/methods/{category}.{method}
            if '/reference/methods/' in href:
                method_name = href.split('/reference/methods/')[-1].rstrip('/')

                # Check if this method belongs to our category
                if method_name.startswith(f'{category}.'):
                    full_url = urljoin(self.BASE_URL, method_name)
                    methods.append({
                        'name': method_name,
                        'category': category,
                        'url': full_url,
                        'description': link.get_text(strip=True)
                    })

        # Remove duplicates
        seen = set()
        unique_methods = []
        for method in methods:
            if method['name'] not in seen:
                seen.add(method['name'])
                unique_methods.append(method)

        return unique_methods

    def scrape_methods_list(self) -> List[Dict[str, str]]:
        """
        Scrape the main methods page to get list of all API methods.

        Returns:
            List of dictionaries containing method information
        """
        soup = self.fetch_page(self.BASE_URL)
        if not soup:
            return []

        methods = []

        # Find all links on the page
        method_links = soup.find_all('a', href=True)

        for link in method_links:
            href = link.get('href', '')

            # Normalize href - remove leading slash if present
            normalized_href = href.lstrip('/')

            # Filter for method links in multiple possible formats
            # Format 1: /reference/methods/method.name
            # Format 2: reference/methods/method.name
            # Format 3: Relative like chat.postMessage
            is_method_link = False
            method_name = None

            if '/reference/methods/' in href and href != '/reference/methods/':
                # Absolute path format
                method_name = href.split('/reference/methods/')[-1].rstrip('/')
                is_method_link = '.' in method_name  # Must have a dot (category.method)
            elif normalized_href.startswith('reference/methods/'):
                # Relative path format
                method_name = normalized_href.split('reference/methods/')[-1].rstrip('/')
                is_method_link = '.' in method_name

            if is_method_link and method_name:
                # Extract category (first part before dot)
                parts = method_name.split('.')
                category = parts[0] if parts else 'unknown'

                # Build full URL
                if href.startswith('http'):
                    full_url = href
                else:
                    full_url = urljoin(self.BASE_URL, method_name)

                methods.append({
                    'name': method_name,
                    'category': category,
                    'url': full_url,
                    'description': link.get_text(strip=True)
                })

        # Remove duplicates
        seen = set()
        unique_methods = []
        for method in methods:
            if method['name'] not in seen:
                seen.add(method['name'])
                unique_methods.append(method)

        return unique_methods

    def scrape_method_details(self, method_name: str) -> Optional[Dict]:
        """
        Scrape detailed information about a specific method.

        Args:
            method_name: Name of the method (e.g., 'chat.postMessage')

        Returns:
            Dictionary containing method details or None if not found
        """
        url = urljoin(self.BASE_URL, method_name)
        soup = self.fetch_page(url)

        if not soup:
            return None

        details = {
            'name': method_name,
            'url': url,
            'description': '',
            'parameters': [],
            'example_request': '',
            'example_response': ''
        }

        # Extract description
        desc_elem = soup.find('meta', {'name': 'description'})
        if desc_elem:
            details['description'] = desc_elem.get('content', '')

        # Try to extract main content description
        main_desc = soup.find('h1')
        if main_desc:
            next_p = main_desc.find_next('p')
            if next_p:
                details['description'] = next_p.get_text(strip=True)

        # Extract parameters (varies based on page structure)
        param_section = soup.find('h2', string=lambda x: x and 'Arguments' in x or 'Parameters' in x)
        if param_section:
            param_list = param_section.find_next('table')
            if param_list:
                for row in param_list.find_all('tr')[1:]:  # Skip header
                    cols = row.find_all('td')
                    if len(cols) >= 2:
                        details['parameters'].append({
                            'name': cols[0].get_text(strip=True),
                            'description': cols[1].get_text(strip=True) if len(cols) > 1 else '',
                            'required': 'required' in row.get_text().lower()
                        })

        # Extract code examples
        code_blocks = soup.find_all('code')
        if code_blocks:
            details['example_request'] = code_blocks[0].get_text(strip=True) if len(code_blocks) > 0 else ''
            details['example_response'] = code_blocks[1].get_text(strip=True) if len(code_blocks) > 1 else ''

        return details

    def scrape_all_methods(self, include_details: bool = False, deep_scrape: bool = True) -> List[Dict]:
        """
        Scrape all Slack API methods.

        Args:
            include_details: If True, fetch detailed information for each method
            deep_scrape: If True, scrape each category page for all methods

        Returns:
            List of method dictionaries
        """
        print("Scraping Slack API methods list...")
        initial_methods = self.scrape_methods_list()
        print(f"Found {len(initial_methods)} methods from main page")

        if deep_scrape:
            # Create a mapping of category to sample method
            category_samples = {m['category']: m['name'] for m in initial_methods}
            print(f"Found {len(category_samples)} categories, scraping each...")

            all_methods = []
            for i, (category, sample_method) in enumerate(sorted(category_samples.items())):
                print(f"[{i+1}/{len(category_samples)}] Scraping {category} category using {sample_method}...")
                category_methods = self.scrape_category_methods(category, sample_method)
                print(f"  Found {len(category_methods)} methods in {category}")
                all_methods.extend(category_methods)
                time.sleep(self.rate_limit_delay)

            # Remove duplicates across all methods
            seen = set()
            unique_methods = []
            for method in all_methods:
                if method['name'] not in seen:
                    seen.add(method['name'])
                    unique_methods.append(method)

            methods = unique_methods
            print(f"Total unique methods found: {len(methods)}")
        else:
            methods = initial_methods

        if include_details:
            print("Fetching detailed information for each method...")
            for i, method in enumerate(methods):
                print(f"[{i+1}/{len(methods)}] Fetching details for {method['name']}...")
                details = self.scrape_method_details(method['name'])
                if details:
                    method.update(details)

                # Rate limiting
                time.sleep(self.rate_limit_delay)

        return methods

    def get_methods_by_category(self, methods: List[Dict]) -> Dict[str, List[Dict]]:
        """
        Organize methods by category.

        Args:
            methods: List of method dictionaries

        Returns:
            Dictionary mapping category names to lists of methods
        """
        by_category = {}
        for method in methods:
            category = method.get('category', 'unknown')
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(method)

        return by_category

    def save_to_json(self, methods: List[Dict], filepath: str):
        """
        Save scraped methods to JSON file.

        Args:
            methods: List of method dictionaries
            filepath: Path to save JSON file
        """
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(methods, f, indent=2, ensure_ascii=False)
        print(f"Saved {len(methods)} methods to {filepath}")

    def save_by_category(self, methods: List[Dict], filepath: str):
        """
        Save methods organized by category to JSON file.

        Args:
            methods: List of method dictionaries
            filepath: Path to save JSON file
        """
        by_category = self.get_methods_by_category(methods)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(by_category, f, indent=2, ensure_ascii=False)
        print(f"Saved {len(by_category)} categories to {filepath}")
