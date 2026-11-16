#!/usr/bin/env python3
"""Hardened Scrapling wrapper. Usage: fetch.py URL [--mode static|stealth] [--css SEL] [--solve-cloudflare]"""
import argparse, json, sys
from scrapling.core.url_safety import ensure_safe_url, CloudflareChallengeNotSolved

def main():
    p = argparse.ArgumentParser()
    p.add_argument("url"); p.add_argument("--mode", choices=["static", "stealth"], default="static")
    p.add_argument("--css", help="CSS selector; prints text of matches"); p.add_argument("--solve-cloudflare", action="store_true")
    p.add_argument("--timeout", type=int, default=30)
    a = p.parse_args()
    try:
        ensure_safe_url(a.url)
        if a.mode == "static":
            from scrapling.fetchers import Fetcher
            r = Fetcher.get(a.url, timeout=a.timeout)
        else:
            from scrapling.fetchers import StealthyFetcher
            r = StealthyFetcher.fetch(a.url, headless=True, solve_cloudflare=a.solve_cloudflare, timeout=a.timeout * 1000)
    except (ValueError, CloudflareChallengeNotSolved) as e:
        print(json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"}, ensure_ascii=False)); sys.exit(2)
    out = {"ok": r.status < 400, "status": r.status, "url": a.url}
    out["results"] = [el.get_all_text(strip=True) for el in r.css(a.css)] if a.css else None
    if not a.css: out["text_head"] = r.get_all_text(strip=True)[:2000]
    print(json.dumps(out, ensure_ascii=False, indent=1)); sys.exit(0 if out["ok"] else 1)

if __name__ == "__main__":
    main()
