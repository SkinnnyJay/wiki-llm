"""Shared HTTP defaults for outbound requests.

Keep the User-Agent here so integrations and ``url_safety`` identify the same
llm-wiki release. Prefer module-specific timeouts when an API needs one.
"""

from lib.version import __version__

USER_AGENT = f"llm-wiki/{__version__} (+https://github.com/SkinnnyJay/wiki-llm)"
DEFAULT_TIMEOUT_S = 60
