"""
browser/browser_agent.py
Phase 3 — Browser automation via Playwright.
Lazy-imports Playwright so the rest of NEXUS runs even if it isn't installed yet.
Maintains a single browser session that the agent can drive across calls.
"""
import logging

logger = logging.getLogger("nexus.browser")


class BrowserAgent:
    """
    Wraps a persistent Playwright Chromium session.
    Call start() before use, close() when done. All methods return strings.
    """

    def __init__(self, headless: bool = False, timeout_ms: int = 30000):
        self.headless   = headless
        self.timeout_ms = timeout_ms
        self._pw        = None
        self._browser   = None
        self._page      = None
        self._started   = False

    def _ensure_started(self) -> str | None:
        if self._started:
            return None
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return ("Playwright not installed. Run:\n"
                    "  pip install playwright\n"
                    "  python -m playwright install chromium\n"
                    "  python -m playwright install-deps chromium   # Linux only")
        try:
            self._pw      = sync_playwright().start()
            self._browser = self._pw.chromium.launch(headless=self.headless)
            self._page    = self._browser.new_page()
            self._page.set_default_timeout(self.timeout_ms)
            self._started = True
            return None
        except Exception as e:
            return (f"Could not launch browser: {e}\n"
                    "On Linux you may need: python -m playwright install-deps chromium")

    def navigate(self, url: str) -> str:
        err = self._ensure_started()
        if err:
            return err
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        try:
            self._page.goto(url, wait_until="domcontentloaded")
            return f"Navigated to {url} — title: '{self._page.title()}'"
        except Exception as e:
            return f"Navigation failed: {e}"

    def get_text(self, max_chars: int = 3000) -> str:
        if not self._started:
            return "No page open. Navigate first."
        try:
            from bs4 import BeautifulSoup
            html = self._page.content()
            text = BeautifulSoup(html, "html.parser").get_text(separator=" ", strip=True)
            return text[:max_chars]
        except Exception as e:
            return f"Could not extract text: {e}"

    def click(self, selector: str) -> str:
        if not self._started:
            return "No page open."
        try:
            self._page.click(selector)
            return f"Clicked '{selector}'"
        except Exception as e:
            return f"Click failed on '{selector}': {e}"

    def fill(self, selector: str, value: str) -> str:
        if not self._started:
            return "No page open."
        try:
            self._page.fill(selector, value)
            return f"Filled '{selector}'"
        except Exception as e:
            return f"Fill failed: {e}"

    def screenshot(self, path: str = "/tmp/nexus_browser.png") -> str:
        if not self._started:
            return "No page open."
        try:
            self._page.screenshot(path=path, full_page=True)
            return f"Browser screenshot saved to {path}"
        except Exception as e:
            return f"Screenshot failed: {e}"

    def search(self, query: str) -> str:
        """Run a DuckDuckGo search (no API key needed) and return result text."""
        err = self._ensure_started()
        if err:
            return err
        q = query.replace(" ", "+")
        nav = self.navigate(f"https://duckduckgo.com/html/?q={q}")
        if "failed" in nav.lower():
            return nav
        return self.get_text(max_chars=2000)

    def current_url(self) -> str:
        if not self._started:
            return "No page open."
        return self._page.url

    def close(self) -> str:
        if self._browser:
            try:
                self._browser.close()
            except Exception:
                pass
        if self._pw:
            try:
                self._pw.stop()
            except Exception:
                pass
        self._started = False
        return "Browser closed"
