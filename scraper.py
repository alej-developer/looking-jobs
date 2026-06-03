"""
scraper.py — Stealth Playwright scraper with Google Dorks targeting ATS portals.

Launches a headless Chromium browser with anti-detection flags, executes
a deterministic set of Google Dork queries targeting lever.co and
greenhouse.io, classifies each result with parser.classify_job(), and
persists new offers via database.insert_offer().
"""

import asyncio
import logging
import random
from urllib.parse import quote_plus

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)

from database import init_db, insert_offer
from parser import classify_job

logger = logging.getLogger(__name__)


# ─── Stealth Browser Configuration ──────────────────────────────────────────

_BROWSER_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-dev-shm-usage",
    "--no-sandbox",
    "--disable-infobars",
    "--disable-extensions",
    "--disable-gpu",
    "--lang=en-US,en",
]

_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

_DEFAULT_VIEWPORT = {"width": 1920, "height": 1080}


# ─── Google Dork Queries (Deterministic List) ────────────────────────────────
# 5 targeted dorks hitting lever.co and greenhouse.io for Python/Fullstack
# roles in Spain or Remote.

GOOGLE_DORKS: list[str] = [
    # 1. Lever — Python + Remote Spain
    'site:lever.co "python" ("remote" OR "Spain") -expired',
    # 2. Greenhouse — Fullstack + Spain
    'site:greenhouse.io "fullstack" OR "full stack" ("Spain" OR "Madrid" OR "Barcelona")',
    # 3. Lever — Fullstack + Remote Global
    'site:lever.co ("full-stack" OR "fullstack") ("remote" OR "worldwide" OR "global")',
    # 4. Greenhouse — Python Developer + Remote
    'site:greenhouse.io "python developer" ("remote" OR "Spain" OR "Europe")',
    # 5. Combined — Both portals, Python/Fullstack + Remote
    '(site:lever.co OR site:greenhouse.io) ("python" OR "fullstack") ("remote" OR "Spain")',
]


# ─── Delay helper ────────────────────────────────────────────────────────────

async def _human_delay(min_seconds: float = 2.0, max_seconds: float = 5.0) -> None:
    """Introduce a randomized delay to mimic human browsing behavior.

    Args:
        min_seconds: Minimum delay in seconds.
        max_seconds: Maximum delay in seconds.
    """
    delay = random.uniform(min_seconds, max_seconds)
    logger.debug("Human delay: %.2f seconds", delay)
    await asyncio.sleep(delay)


# ─── Result Parser ───────────────────────────────────────────────────────────

async def _extract_google_results(page: Page) -> list[dict[str, str]]:
    """Extract job listing links from a Google search results page.

    Filters results to only include lever.co and greenhouse.io URLs.

    Args:
        page: The Playwright page after navigating to Google results.

    Returns:
        A list of dicts with keys 'title', 'url', and 'snippet'.
    """
    results: list[dict[str, str]] = []

    try:
        # Wait for search results to load
        await page.wait_for_selector("div#search", timeout=10000)

        # Extract all result links
        links = await page.query_selector_all("div#search a[href]")

        for link in links:
            href = await link.get_attribute("href")
            if href is None:
                continue

            # Filter: only lever.co and greenhouse.io job pages
            if not ("lever.co" in href or "greenhouse.io" in href):
                continue

            # Skip Google redirect wrappers, ads, and non-job pages
            if any(skip in href for skip in ["/search?", "google.com", "webcache"]):
                continue

            # Extract the title text
            title_el = await link.query_selector("h3")
            title = await title_el.inner_text() if title_el else ""

            # Extract snippet if available
            snippet = ""
            parent = await link.evaluate_handle("el => el.closest('div[data-snhf]') || el.parentElement")
            if parent:
                snippet_el = await parent.query_selector("span")
                if snippet_el:
                    snippet = await snippet_el.inner_text()

            results.append({
                "title": title.strip(),
                "url": href.strip(),
                "snippet": snippet.strip(),
            })

        logger.info("Extracted %d ATS results from Google page", len(results))

    except Exception:
        logger.exception("Error extracting Google search results")

    return results


# ─── ATS Type Detector ───────────────────────────────────────────────────────

def _detect_ats_type(url: str) -> str:
    """Determine the ATS platform from the URL.

    Args:
        url: The job posting URL.

    Returns:
        ATS platform name: 'lever', 'greenhouse', or 'unknown'.
    """
    if "lever.co" in url:
        return "lever"
    if "greenhouse.io" in url:
        return "greenhouse"
    return "unknown"


# ─── Core Scraper ────────────────────────────────────────────────────────────

async def _execute_dork(
    context: BrowserContext,
    dork: str,
    dork_index: int,
) -> int:
    """Execute a single Google Dork query and persist discovered offers.

    Args:
        context: The Playwright browser context (with stealth settings).
        dork: The Google Dork query string.
        dork_index: 1-based index for logging purposes.

    Returns:
        Number of new offers successfully inserted.
    """
    page = await context.new_page()
    inserted_count = 0

    try:
        search_url = f"https://www.google.com/search?q={quote_plus(dork)}&num=20"
        logger.info(
            "[Dork %d/5] Executing: %s",
            dork_index,
            dork,
        )

        await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
        await _human_delay(3.0, 6.0)

        # Handle potential CAPTCHA or consent page
        consent_button = await page.query_selector('button[id="L2AGLb"]')
        if consent_button:
            await consent_button.click()
            logger.info("Google consent dialog accepted")
            await _human_delay(1.0, 2.0)

        results = await _extract_google_results(page)

        if not results:
            logger.warning("[Dork %d/5] No results found", dork_index)
            return 0

        for result in results:
            title = result["title"]
            url = result["url"]

            # Classify the job offer
            classification = classify_job(title, url)

            # Determine work modality string for the DB
            work_modality = classification.work_modality
            if classification.geo_scope != "UNKNOWN":
                work_modality = f"{classification.work_modality}_{classification.geo_scope}"

            # Detect ATS platform
            ats_type = _detect_ats_type(url)

            # Infer company name from URL or title
            company_name = _infer_company_from_url(url)

            # Detect location from classification
            location = classification.geo_match if classification.geo_match else None

            try:
                insert_offer(
                    company_name=company_name,
                    job_title=title,
                    url=url,
                    ats_type=ats_type,
                    location=location,
                    work_modality=work_modality,
                    status="PENDING",
                )
                inserted_count += 1
            except Exception:
                logger.warning("Skipping duplicate or invalid offer: %s", url)

        logger.info(
            "[Dork %d/5] Inserted %d new offers out of %d results",
            dork_index,
            inserted_count,
            len(results),
        )

    except Exception:
        logger.exception("[Dork %d/5] Failed to execute dork query", dork_index)
    finally:
        await page.close()

    return inserted_count


def _infer_company_from_url(url: str) -> str:
    """Extract a probable company name from a Lever or Greenhouse URL.

    Lever format:  https://jobs.lever.co/company-name/...
    Greenhouse:    https://boards.greenhouse.io/company-name/...

    Args:
        url: The job posting URL.

    Returns:
        Inferred company name (title-cased), or 'Unknown' if extraction fails.
    """
    try:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        path_parts = [p for p in parsed.path.split("/") if p]

        if path_parts:
            raw_name = path_parts[0]
            # Convert slug to readable name: "my-company" -> "My Company"
            return raw_name.replace("-", " ").replace("_", " ").title()
    except Exception:
        logger.debug("Could not infer company name from URL: %s", url)

    return "Unknown"


# ─── Main Entry Point ───────────────────────────────────────────────────────

async def run_scraper() -> dict[str, int]:
    """Execute all Google Dork queries and return a summary of results.

    Initializes the database, launches a stealth Playwright browser,
    iterates through all dorks, and collects results.

    Returns:
        A dict with keys: 'total_dorks', 'total_inserted', 'total_errors'.
    """
    # Ensure database schema exists
    init_db()

    total_inserted = 0
    total_errors = 0

    logger.info("=" * 60)
    logger.info("ATS SCRAPER — Starting with %d Google Dork queries", len(GOOGLE_DORKS))
    logger.info("=" * 60)

    playwright_instance: Playwright | None = None
    browser: Browser | None = None

    try:
        playwright_instance = await async_playwright().start()

        browser = await playwright_instance.chromium.launch(
            headless=True,
            args=_BROWSER_ARGS,
        )

        context = await browser.new_context(
            user_agent=_DEFAULT_USER_AGENT,
            viewport=_DEFAULT_VIEWPORT,
            locale="en-US",
            timezone_id="Europe/Madrid",
            java_script_enabled=True,
        )

        # Inject stealth scripts to remove automation indicators
        await context.add_init_script("""
            // Override navigator.webdriver to false
            Object.defineProperty(navigator, 'webdriver', {
                get: () => false,
            });

            // Override chrome.runtime to appear as a normal browser
            window.chrome = {
                runtime: {},
            };

            // Override permissions query
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) =>
                parameters.name === 'notifications'
                    ? Promise.resolve({ state: Notification.permission })
                    : originalQuery(parameters);
        """)

        logger.info("Stealth browser launched — headless Chromium with anti-detection")

        for i, dork in enumerate(GOOGLE_DORKS, start=1):
            try:
                inserted = await _execute_dork(context, dork, i)
                total_inserted += inserted
            except Exception:
                logger.exception("Critical error on dork %d", i)
                total_errors += 1

            # Delay between dorks to avoid rate-limiting
            if i < len(GOOGLE_DORKS):
                await _human_delay(5.0, 10.0)

    except Exception:
        logger.exception("Fatal error in scraper execution")
        total_errors += 1
    finally:
        if browser:
            await browser.close()
            logger.debug("Browser closed")
        if playwright_instance:
            await playwright_instance.stop()
            logger.debug("Playwright stopped")

    summary = {
        "total_dorks": len(GOOGLE_DORKS),
        "total_inserted": total_inserted,
        "total_errors": total_errors,
    }

    logger.info("=" * 60)
    logger.info("SCRAPER SUMMARY: %s", summary)
    logger.info("=" * 60)

    return summary


# ─── Script Execution ────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    asyncio.run(run_scraper())
