from ingest.adapters.brave_search import BraveSearchAdapter
from ingest.adapters.convo import ConvoAdapter
from ingest.adapters.file import FileAdapter
from ingest.adapters.hackernews import HackerNewsAdapter
from ingest.adapters.pdf_marker import PdfMarkerAdapter
from ingest.adapters.pdf_markitdown import PdfMarkitdownAdapter
from ingest.adapters.pdf_mineru import PdfMineruAdapter
from ingest.adapters.pdf_vision import PdfVisionAdapter
from ingest.adapters.perplexity import PerplexityAdapter
from ingest.adapters.twitter import TwitterAdapter
from ingest.adapters.url import UrlAdapter
from ingest.adapters.web_firecrawl import FirecrawlAdapter
from ingest.adapters.web_playwright import PlaywrightAdapter
from ingest.adapters.youtube import YoutubeAdapter

ADAPTERS = [
    FileAdapter,
    UrlAdapter,
    HackerNewsAdapter,
    PdfVisionAdapter,
    PdfMarkerAdapter,
    PdfMarkitdownAdapter,
    PdfMineruAdapter,
    FirecrawlAdapter,
    PlaywrightAdapter,
    YoutubeAdapter,
    PerplexityAdapter,
    TwitterAdapter,
    BraveSearchAdapter,
    ConvoAdapter,
]
