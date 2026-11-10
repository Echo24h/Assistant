"""Import a recipe from a website, WITHOUT the model (0 tokens).

Most recipe websites describe the recipe in a standard format for search
engines: schema.org "Recipe" in a <script type="application/ld+json">
block. We read that block; no HTML guessing, no AI.

This module downloads a page chosen by the user, so it must not become a
way to reach private machines (SSRF: Server-Side Request Forgery). Rules:
- http(s) only, ports 80/443 only;
- the name must resolve to PUBLIC addresses only (not 127.0.0.1, not
  192.168.x.x, not Tailscale's 100.x...), checked for every redirect;
- we connect to the address we checked, not to a second DNS answer
  (otherwise "DNS rebinding" could swap it for a private one);
- small and slow pages are cut: at most 2 MB, 10 seconds.
The model has NO tool that calls this: only a click in the Recipes tab.
"""

import html
import http.client
import ipaddress
import json
import re
import socket
import ssl
from urllib.parse import urljoin, urlsplit

from .recipes import parse_ingredient_line

MAX_BYTES = 2_000_000
TIMEOUT = 10  # seconds
MAX_REDIRECTS = 3
USER_AGENT = "Mozilla/5.0 (personal recipe import)"
LD_JSON = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL)


def fetch_recipe(url: str) -> dict:
    """{"title", "servings", "ingredients", "instructions", "source_url"}."""
    page = fetch_page(url)
    for block in LD_JSON.findall(page):
        try:
            recipe = find_recipe(json.loads(block))
        except ValueError:  # invalid JSON in the page: try the next block
            continue
        if recipe:
            return to_recipe(recipe, url)
    raise ValueError("No structured recipe on this page: copy its text into the chat.")


# --- download, safely ---

def fetch_page(url: str) -> str:
    for _ in range(MAX_REDIRECTS + 1):
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise ValueError("Only http:// or https:// addresses.")
        port = parts.port or (443 if parts.scheme == "https" else 80)
        if port not in (80, 443):
            raise ValueError("Only the standard ports (80, 443).")
        ip = public_address(parts.hostname)

        conn = connection(parts.scheme, parts.hostname, ip, port)
        try:
            path = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
            conn.request("GET", path, headers={"Host": parts.hostname,
                                               "User-Agent": USER_AGENT,
                                               "Accept": "text/html"})
            response = conn.getresponse()
            if response.status in (301, 302, 303, 307, 308):
                url = urljoin(url, response.getheader("Location", ""))
                continue  # checked again at the top of the loop
            if response.status != 200:
                raise ValueError(f"The website answered {response.status}.")
            body = response.read(MAX_BYTES + 1)
            if len(body) > MAX_BYTES:
                raise ValueError("Page too large.")
            return body.decode(response.headers.get_content_charset() or "utf-8", "replace")
        except (OSError, http.client.HTTPException) as e:
            raise ValueError(f"Cannot download the page: {e}") from e
        finally:
            conn.close()
    raise ValueError("Too many redirects.")


def public_address(hostname: str) -> str:
    """The first address of hostname; refuse if ANY of its addresses is not public."""
    try:
        infos = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror:
        raise ValueError(f"Unknown website: {hostname}") from None
    addresses = [info[4][0] for info in infos]
    for address in addresses:
        if not ipaddress.ip_address(address).is_global:
            raise ValueError("This address is not a public website.")
    return addresses[0]


def connection(scheme: str, hostname: str, ip: str, port: int):
    """An HTTP(S) connection to `ip`, while TLS still checks `hostname`'s certificate."""
    if scheme == "https":
        return PinnedHTTPS(hostname, ip, port)
    return PinnedHTTP(hostname, ip, port)


class PinnedHTTP(http.client.HTTPConnection):
    def __init__(self, hostname, ip, port):
        super().__init__(hostname, port, timeout=TIMEOUT)
        self.ip = ip

    def connect(self):
        self.sock = socket.create_connection((self.ip, self.port), self.timeout)


class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, hostname, ip, port):
        super().__init__(hostname, port, timeout=TIMEOUT, context=ssl.create_default_context())
        self.ip = ip

    def connect(self):
        sock = socket.create_connection((self.ip, self.port), self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


# --- read schema.org Recipe ---

def find_recipe(node):
    """The first object whose @type is (or contains) "Recipe", anywhere in the JSON."""
    if isinstance(node, list):
        for item in node:
            if found := find_recipe(item):
                return found
    elif isinstance(node, dict):
        kind = node.get("@type")
        if kind == "Recipe" or (isinstance(kind, list) and "Recipe" in kind):
            return node
        return find_recipe(node.get("@graph", []))
    return None


def to_recipe(data: dict, url: str) -> dict:
    lines = [clean(line) for line in data.get("recipeIngredient") or []]
    return {
        "title": clean(data.get("name") or "Recette"),
        "servings": servings_of(data.get("recipeYield")),
        "ingredients": ingredients(lines)[:100],
        "instructions": "\n".join(
            f"{n}. {step}" for n, step in enumerate(steps(data.get("recipeInstructions")), 1)),
        "source_url": url,
    }


def ingredients(lines: list[str]) -> list[dict]:
    """Each line read like a typed one; a strange line is skipped, not fatal."""
    result = []
    for line in lines:
        try:
            result.append(parse_ingredient_line(line))
        except ValueError:
            continue
    return result


def servings_of(value) -> int:
    """recipeYield can be 4, "4", "4 personnes", ["4", "4 servings"]..."""
    if isinstance(value, list):
        value = value[0] if value else None
    found = re.search(r"\d+", str(value or ""))
    number = int(found.group()) if found else 0
    return number if 0 < number <= 100 else 2


def steps(value) -> list[str]:
    """recipeInstructions: a text, a list of texts, of HowToStep, of HowToSection."""
    if isinstance(value, str):
        return [line for line in (clean(v) for v in value.split("\n")) if line]
    result = []
    for item in value or []:
        if isinstance(item, str):
            result.append(clean(item))
        elif isinstance(item, dict) and "itemListElement" in item:  # a section
            result += steps(item["itemListElement"])
        elif isinstance(item, dict):
            result.append(clean(item.get("text") or item.get("name") or ""))
    return [step for step in result if step]


def clean(text) -> str:
    """Text from the page: HTML entities decoded, tags removed, spaces tidied."""
    text = html.unescape(re.sub(r"<[^>]+>", " ", str(text)))
    text = re.sub(r"\s+([.,])", r"\1", text)  # "<b>word</b>." gave "word ."
    return re.sub(r"\s+", " ", text).strip()
