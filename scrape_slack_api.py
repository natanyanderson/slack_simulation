#!/usr/bin/env python3
"""
Example script to scrape Slack API Methods documentation.

Usage:
    python scrape_slack_api.py                    # List all methods
    python scrape_slack_api.py --details          # Include detailed info
    python scrape_slack_api.py --method chat.postMessage  # Scrape specific method
"""

import argparse
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from slack_io.scrapers import SlackAPIMethodsScraper


def main():
    parser = argparse.ArgumentParser(description='Scrape Slack API methods documentation')
    parser.add_argument(
        '--details',
        action='store_true',
        help='Include detailed information for each method (slower)'
    )
    parser.add_argument(
        '--method',
        type=str,
        help='Scrape specific method (e.g., chat.postMessage)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='slack_api_methods.json',
        help='Output JSON file path (default: slack_api_methods.json)'
    )
    parser.add_argument(
        '--by-category',
        action='store_true',
        help='Organize output by category'
    )
    parser.add_argument(
        '--rate-limit',
        type=float,
        default=1.0,
        help='Delay between requests in seconds (default: 1.0)'
    )

    args = parser.parse_args()

    scraper = SlackAPIMethodsScraper(rate_limit_delay=args.rate_limit)

    if args.method:
        # Scrape specific method
        print(f"Scraping details for {args.method}...")
        details = scraper.scrape_method_details(args.method)

        if details:
            print(f"\n=== {details['name']} ===")
            print(f"URL: {details['url']}")
            print(f"Description: {details['description']}")

            if details.get('parameters'):
                print("\nParameters:")
                for param in details['parameters']:
                    required = " (required)" if param.get('required') else ""
                    print(f"  - {param['name']}{required}: {param['description']}")

            if details.get('example_request'):
                print(f"\nExample Request:\n{details['example_request'][:200]}...")

            # Save to file
            scraper.save_to_json([details], args.output)
        else:
            print(f"Failed to scrape {args.method}")
            return 1

    else:
        # Scrape all methods
        methods = scraper.scrape_all_methods(include_details=args.details)

        if not methods:
            print("No methods found")
            return 1

        # Print summary
        print(f"\n=== Summary ===")
        print(f"Total methods: {len(methods)}")

        by_category = scraper.get_methods_by_category(methods)
        print(f"Categories: {len(by_category)}")

        print("\nMethods by category:")
        for category, cat_methods in sorted(by_category.items()):
            print(f"  {category}: {len(cat_methods)} methods")

        # Sample methods
        print("\nSample methods:")
        for method in methods[:10]:
            print(f"  - {method['name']}")
        if len(methods) > 10:
            print(f"  ... and {len(methods) - 10} more")

        # Save to file
        if args.by_category:
            scraper.save_by_category(methods, args.output)
        else:
            scraper.save_to_json(methods, args.output)

    return 0


if __name__ == '__main__':
    sys.exit(main())
