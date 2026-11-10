"""URL import: reading schema.org, and refusing private addresses (SSRF).
No network: the page download is replaced by a fixed page."""

import pytest

from assistant.services import recipe_import
from assistant.services.recipe_import import fetch_page, fetch_recipe, public_address

PAGE = """<html><head>
<script type="application/ld+json">{"@type": "WebSite", "name": "Not a recipe"}</script>
<script type="application/ld+json">
{"@graph": [{"@type": ["Recipe", "Thing"],
  "name": "Gratin &amp; courgettes",
  "recipeYield": "4 personnes",
  "recipeIngredient": ["1 kg de courgettes", "20 cl de crème", "sel"],
  "recipeInstructions": [
    {"@type": "HowToSection", "itemListElement": [
      {"@type": "HowToStep", "text": "Couper les <b>courgettes</b>."}]},
    {"@type": "HowToStep", "text": "Cuire 30 min."}]}]}
</script></head></html>"""


def test_reads_schema_org_recipe(monkeypatch):
    monkeypatch.setattr(recipe_import, "fetch_page", lambda url: PAGE)
    recipe = fetch_recipe("https://example.com/gratin")
    assert recipe["title"] == "Gratin & courgettes"
    assert recipe["servings"] == 4
    assert recipe["ingredients"] == [
        {"name": "courgettes", "quantity": 1000, "unit": "g"},  # as written: matched later
        {"name": "crème", "quantity": 200, "unit": "ml"},
        {"name": "sel", "quantity": None, "unit": None},
    ]
    assert recipe["instructions"] == "1. Couper les courgettes.\n2. Cuire 30 min."


def test_page_without_recipe(monkeypatch):
    monkeypatch.setattr(recipe_import, "fetch_page", lambda url: "<html>no recipe</html>")
    with pytest.raises(ValueError, match="No structured recipe"):
        fetch_recipe("https://example.com/")


@pytest.mark.parametrize("address", [
    "127.0.0.1", "10.0.0.5", "192.168.1.1", "169.254.169.254",  # cloud metadata
    "100.100.100.100",  # Tailscale
    "::1", "fd7a:115c:a1e0::1",  # IPv6 loopback, Tailscale IPv6
])
def test_private_addresses_are_refused(address):
    with pytest.raises(ValueError, match="not a public"):
        public_address(address)


def test_only_http_and_standard_ports():
    for url in ["file:///etc/passwd", "ftp://example.com/", "javascript:alert(1)",
                "http://example.com:8765/", "http:///nohost"]:
        with pytest.raises(ValueError):
            fetch_page(url)


def test_redirect_to_a_private_address_is_refused(monkeypatch):
    """A public page may redirect to http://127.0.0.1: every hop is checked."""
    class Redirect:
        status = 302
        def getheader(self, name, default=None):
            return "http://127.0.0.1:80/admin"

    class FakeConnection:
        def __init__(self, *args): pass
        def request(self, *args, **kwargs): pass
        def getresponse(self): return Redirect()
        def close(self): pass

    monkeypatch.setattr(recipe_import, "public_address",
                        lambda host: "93.184.215.14" if host == "example.com"
                        else (_ for _ in ()).throw(ValueError("not a public website")))
    monkeypatch.setattr(recipe_import, "connection", lambda *args: FakeConnection())
    with pytest.raises(ValueError, match="not a public"):
        fetch_page("http://example.com/recipe")
