---
name: wiki-extract-ecommerce
description: Extract product listings, pricing, and auction data from Amazon, eBay, Etsy, Shopify into raw/. Use for product research or price tracking.
disable-model-invocation: true
argument-hint: "<product URL or search query>"
---

# Wiki extract — ecommerce & auctions

Extracts structured product and pricing data from ecommerce and auction platforms into `raw/` for wiki ingestion. Use when:
- The user shares an Amazon, eBay, Etsy, or Shopify product URL.
- Researching pricing, sold comps, or market trends for a product category.
- "What does this sell for?", "find sold listings for X", "add this product to the wiki", "track prices for X".
- Auction research: lot descriptions, hammer prices, bidding history.

---

## Step 1 — Identify the platform and URL type

| URL pattern | Platform | Content type |
|-------------|----------|--------------|
| `amazon.com/dp/<ASIN>` or `/gp/product/<ASIN>` | Amazon | Product page |
| `amazon.com/s?k=<query>` | Amazon | Search results |
| `ebay.com/itm/<ID>` | eBay | Active listing |
| `ebay.com/sch/...&LH_Sold=1` | eBay | Sold listings (price history) |
| `ebay.com/b/<category>/<ID>` | eBay | Category browse |
| `etsy.com/listing/<ID>` | Etsy | Product listing |
| `etsy.com/shop/<name>` | Etsy | Shop page |
| `<store>.myshopify.com` or any Shopify store | Shopify | Storefront / product |
| `catawiki.com/l/<ID>` or `sothebys.com` etc. | Auction house | Lot description |

---

## Step 2 — Check adapter availability

```bash
llm-wiki integrations status
```

Ecommerce pages are heavily JavaScript-rendered. **Firecrawl is strongly preferred**. stdlib fallback will often return empty or stub content.

```
Adapter priority for ecommerce:
  1. Firecrawl CLI / REST  → handles JS rendering, best structured output
  2. stdlib url            → works only for Shopify JSON API and eBay sold search
  3. Direct API            → Amazon PA API (if configured), eBay Browse API
```

---

## Step 3 — Amazon

### Product page

```bash
ASIN="<B0XXXXXXXX>"
SLUG="amazon-${ASIN,,}"   # lowercase
OUT_DIR="raw/products/${SLUG}"
mkdir -p "$OUT_DIR"

# Fetch with Firecrawl (handles JS, extracts structured product data)
llm-wiki ingest firecrawl "https://www.amazon.com/dp/${ASIN}" \
  --out "${OUT_DIR}/listing.md"
```

If `AMAZON_PA_API_KEY` is configured (Amazon Product Advertising API):

```bash
python3 << 'PYEOF'
import urllib.request, urllib.parse, hmac, hashlib, datetime, json, os

# PA API v5 ItemsSearch / GetItems
# Full auth implementation: https://webservices.amazon.com/paapi5/documentation/
ASIN = os.environ.get('ASIN', '')
# ... (PA API auth is complex — use Firecrawl unless PA API is explicitly configured)
PYEOF
```

### Amazon search results (price survey)

```bash
QUERY="<search terms>"
llm-wiki ingest firecrawl \
  "https://www.amazon.com/s?k=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))" "$QUERY")" \
  --out "raw/products/amazon-search-${QUERY// /-}.md"
```

---

## Step 4 — eBay

### Active listing

```bash
ITEM_ID="<eBay item ID>"
SLUG="ebay-${ITEM_ID}"
OUT_DIR="raw/products/${SLUG}"
mkdir -p "$OUT_DIR"

llm-wiki ingest firecrawl "https://www.ebay.com/itm/${ITEM_ID}" \
  --out "${OUT_DIR}/listing.md"
```

### Sold listings (price history — most valuable for research)

Sold listings are the gold standard for actual market price. The URL filter `LH_Sold=1&LH_Complete=1` restricts results to completed, sold items.

```bash
QUERY="<search terms>"
ENCODED=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))" "$QUERY")

# eBay sold search URL
SOLD_URL="https://www.ebay.com/sch/i.html?_nkw=${ENCODED}&LH_Sold=1&LH_Complete=1&_sop=13"
# _sop=13 = sort by recently ended

llm-wiki ingest firecrawl "$SOLD_URL" \
  --out "raw/products/ebay-sold-${QUERY// /-}.md"
```

Parse sold prices from the output:

```python
# scripts/.tmp/parse_ebay_sold.py
import re, sys, pathlib

text = pathlib.Path(sys.argv[1]).read_text()
# Find price patterns: "$XX.XX" or "US $XX.XX"
prices = re.findall(r'(?:US )?\$\s*([\d,]+\.?\d*)', text)
prices = [float(p.replace(',','')) for p in prices if float(p.replace(',','')) > 0]
if prices:
    print(f"Count:   {len(prices)}")
    print(f"Min:     ${min(prices):.2f}")
    print(f"Max:     ${max(prices):.2f}")
    print(f"Median:  ${sorted(prices)[len(prices)//2]:.2f}")
    print(f"Mean:    ${sum(prices)/len(prices):.2f}")
```

---

## Step 5 — Etsy

```bash
LISTING_ID="<Etsy listing ID>"
SLUG="etsy-${LISTING_ID}"
OUT_DIR="raw/products/${SLUG}"
mkdir -p "$OUT_DIR"

# Single listing
llm-wiki ingest firecrawl "https://www.etsy.com/listing/${LISTING_ID}" \
  --out "${OUT_DIR}/listing.md"

# Shop page
SHOP_NAME="<shop name>"
llm-wiki ingest firecrawl "https://www.etsy.com/shop/${SHOP_NAME}" \
  --out "raw/products/etsy-shop-${SHOP_NAME,,}.md"
```

---

## Step 6 — Shopify

Shopify storefronts expose a machine-readable JSON API at `/products/<handle>.json` and `/products.json` (product catalog) — no Firecrawl needed.

```bash
STORE="<store-domain>"   # e.g. example.myshopify.com or customdomain.com
HANDLE="<product-handle>"

# Single product (no JS needed)
llm-wiki ingest url "https://${STORE}/products/${HANDLE}.json" \
  --out "raw/products/shopify-${STORE//./-}-${HANDLE}.json"

# Full product catalog (paginated, up to 250 per page)
llm-wiki ingest url "https://${STORE}/products.json?limit=250" \
  --out "raw/products/shopify-${STORE//./-}-catalog.json"
```

Parse the JSON into a readable product summary:

```python
# scripts/.tmp/parse_shopify.py
import json, sys, pathlib

data = json.loads(pathlib.Path(sys.argv[1]).read_text())
p = data.get('product', data)  # handle both single and catalog

variants = p.get('variants', [])
prices = [float(v['price']) for v in variants if v.get('price')]

print(f"# {p['title']}")
print(f"\n{p.get('body_html','').replace('<','<').replace('>','>')[:500]}")
print(f"\n**Variants:** {len(variants)}")
if prices:
    print(f"**Price range:** ${min(prices):.2f} – ${max(prices):.2f}")
```

---

## Step 7 — Auction houses

For major auction houses (Sotheby's, Christie's, Heritage Auctions, Catawiki, Invaluable):

```bash
LOT_URL="<lot page URL>"
SLUG="<auction-house>-lot-<ID>"
OUT_DIR="raw/products/auctions/${SLUG}"
mkdir -p "$OUT_DIR"

llm-wiki ingest firecrawl "$LOT_URL" --out "${OUT_DIR}/lot.md"
```

Key fields to extract and record in frontmatter:
- Lot number, estimate (low/high), hammer price, buyer's premium
- Auction date, auction house, sale name
- Condition report, provenance

---

## Step 8 — Write to raw/ with frontmatter

Output path: `raw/products/<platform>-<slug>/index.md`

```yaml
---
title: "<Product/Lot Title>"
platform: amazon | ebay | etsy | shopify | sothebys | christies | heritage | catawiki | other
source_url: https://...
source_type: ecommerce_listing | auction_lot | sold_search
asin: "<ASIN>"                      # Amazon only
ebay_item_id: "<ID>"                # eBay only
etsy_listing_id: "<ID>"             # Etsy only
condition: new | used | refurbished | lot | unknown
price_listed: <N.NN>                # current asking price
currency: USD | GBP | EUR
sold_price: <N.NN>                  # if sold listing or auction result
estimate_low: <N.NN>                # auction only
estimate_high: <N.NN>               # auction only
hammer_price: <N.NN>                # auction only
buyers_premium_pct: <N>             # auction only
auction_date: YYYY-MM-DD            # auction only
auction_house: "<name>"             # auction only
seller: "<seller name or ID>"
fetched_date: YYYY-MM-DD
---
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Amazon returns CAPTCHA or robot check | Use Firecrawl; avoid rapid repeated requests |
| eBay sold search returns current listings | Ensure `LH_Sold=1&LH_Complete=1` are both in the URL |
| Etsy listing returns "page not found" | Listing may be sold out/inactive; check if it exists in browser |
| Shopify `/products.json` returns 404 | Store may have disabled the API; use Firecrawl on the storefront |
| Firecrawl returns < 200 words | Page may be geo-blocked or require login; try stdlib as fallback |
| Auction lot shows "Sold: —" (no price) | Some houses hide hammer prices post-sale; check results archive separately |
| Price extraction misses prices | Prices may be in non-USD format; adjust regex in `parse_ebay_sold.py` |

---

## Done looks like

- **`raw/`** captures product or listing data with price/sold state when visible; bot-blocks and login walls are documented, not faked.

## Related skills

- **wiki-research-web** — for general product review articles or market analysis pages
- **wiki-extract-paywall** — if a product review site (e.g. Consumer Reports) is paywalled
- **wiki-research-news** — for news coverage of product launches or market trends
- **wiki-raw-prepare** — clean and restructure scraped product data before wiki ingestion

## Smoke check

- **CLI:** Run `llm-wiki integrations status` and any `llm-wiki` line from Step 1 of this skill (from the vault root).
- **Prompt:** Invoke this skill by name in Claude Code; complete Step 1 only and confirm expected CLI or file output.

