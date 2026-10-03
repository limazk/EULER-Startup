from email.message import Message
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

from security import (  # noqa: E402
    MAX_BODY_BYTES,
    SlidingWindowRateLimiter,
    content_length,
    media_type,
    same_origin,
)


def headers(**values):
    msg = Message()
    for key, value in values.items():
        msg[key.replace("_", "-")] = str(value)
    return msg


class SecurityTests(unittest.TestCase):
    def test_same_origin_browser_requests(self):
        self.assertTrue(same_origin(headers(Host="example.com", Origin="https://example.com")))
        self.assertFalse(same_origin(headers(Host="example.com", Origin="https://evil.example")))
        self.assertFalse(same_origin(headers(Host="example.com", Sec_Fetch_Site="cross-site")))
        self.assertTrue(same_origin(headers(Host="example.com")))

    def test_content_type_is_normalized(self):
        self.assertEqual(media_type(headers(Content_Type="application/json; charset=utf-8")), "application/json")
        self.assertNotEqual(media_type(headers(Content_Type="text/plain")), "application/json")

    def test_body_framing_and_size(self):
        self.assertEqual(content_length(headers(Content_Length="10")), 10)
        with self.assertRaises(OverflowError):
            content_length(headers(Content_Length=str(MAX_BODY_BYTES + 1)))
        with self.assertRaises(ValueError):
            content_length(headers(Content_Length="10", Content_Encoding="gzip"))
        with self.assertRaises(ValueError):
            content_length(headers(Content_Length="10", Transfer_Encoding="chunked"))

    def test_sliding_window_limit(self):
        limiter = SlidingWindowRateLimiter(2, 60)
        self.assertEqual(limiter.check("client", now=0), (True, 0))
        self.assertEqual(limiter.check("client", now=1), (True, 0))
        allowed, retry = limiter.check("client", now=2)
        self.assertFalse(allowed)
        self.assertGreater(retry, 0)
        self.assertEqual(limiter.check("client", now=61), (True, 0))


if __name__ == "__main__":
    unittest.main()
