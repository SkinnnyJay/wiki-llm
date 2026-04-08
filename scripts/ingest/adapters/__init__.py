from ingest.adapters.file import FileAdapter
from ingest.adapters.url import UrlAdapter
from ingest.adapters.hackernews import HackerNewsAdapter
from ingest.adapters.pdf_vision import PdfVisionAdapter
from ingest.adapters.pdf_marker import PdfMarkerAdapter
from ingest.adapters.pdf_markitdown import PdfMarkitdownAdapter
from ingest.adapters.pdf_mineru import PdfMineruAdapter
from ingest.adapters.web_firecrawl import FirecrawlAdapter
from ingest.adapters.youtube import YoutubeAdapter
from ingest.adapters.perplexity import PerplexityAdapter
from ingest.adapters.twitter import TwitterAdapter
from ingest.adapters.brave_search import BraveSearchAdapter

ADAPTERS = [
    FileAdapter,
    UrlAdapter,
    HackerNewsAdapter,
    PdfVisionAdapter,
    PdfMarkerAdapter,
    PdfMarkitdownAdapter,
    PdfMineruAdapter,
    FirecrawlAdapter,
    YoutubeAdapter,
    PerplexityAdapter,
    TwitterAdapter,
    BraveSearchAdapter,
]
