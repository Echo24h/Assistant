"""What a conversation costs, in dollars, to show it in the page.

Prices per million tokens (input, output), from the pricing page, for
prompts of 100K tokens or fewer. A model not listed: no price shown.
Cache: writing costs 1.25x the input price (5-minute cache), reading 0.1x.
"""

PRICES = {
    "claude-haiku-5-5": (0.10, 0.50),
}
CACHE_WRITE = 1.25
CACHE_READ = 0.10


def cost_usd(model: str, input_tokens: int, output_tokens: int,
             cache_read: int = 0, cache_write: int = 0) -> float | None:
    if model not in PRICES:
        return None
    price_in, price_out = PRICES[model]
    return (input_tokens * price_in
            + cache_write * price_in * CACHE_WRITE
            + cache_read * price_in * CACHE_READ
            + output_tokens * price_out) / 1_000_000
