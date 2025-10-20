# D:\github\1968_SMART_CHAT_BACK\core\http_client.py
import requests
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from .config import DEFAULT_TIMEOUT, RETRY_TOTAL

_session = None

def get_session():
    global _session
    if _session is None:
        _session = requests.Session()
        retries = Retry(
            total=RETRY_TOTAL, backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset(['GET'])
        )
        _session.headers.update({"User-Agent": "1968-smartchat/1.0"})
        _session.mount("http://", HTTPAdapter(max_retries=retries))
        _session.mount("https://", HTTPAdapter(max_retries=retries))
    return _session

def http_get(url: str, timeout: float = DEFAULT_TIMEOUT) -> requests.Response:
    return get_session().get(url, timeout=timeout)
