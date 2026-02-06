"""Scrape web pages."""

import json
import os
import sys

import requests
from bs4 import BeautifulSoup

params = json.loads(os.environ.get("PARVA_PARAMS", "{}"))
url = params.get("url", "")
selector = params.get("selector")
fmt = params.get("format", "text")

if not url:
    print(json.dumps({"error": "No URL provided"}))
    sys.exit(0)

try:
    resp = requests.get(url, timeout=30, headers={
        "User-Agent": "Mozilla/5.0 (compatible; Parva/1.0)"
    })
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")

    # Remove script and style elements
    for tag in soup(["script", "style", "nav", "footer"]):
        tag.decompose()

    if selector:
        elements = soup.select(selector)
        if fmt == "html":
            result = {"html": "\n".join(str(e) for e in elements)}
        else:
            result = {"text": "\n".join(e.get_text(strip=True) for e in elements)}
    elif fmt == "links":
        links = []
        for a in soup.find_all("a", href=True):
            links.append({"text": a.get_text(strip=True), "href": a["href"]})
        result = {"links": links[:100]}
    elif fmt == "html":
        result = {"html": str(soup.body or soup)[:10000]}
    else:
        text = soup.get_text(separator="\n", strip=True)
        result = {"text": text[:10000], "title": soup.title.string if soup.title else ""}

    result["url"] = url
    result["status_code"] = resp.status_code

except Exception as e:
    result = {"error": str(e), "url": url}

print(json.dumps(result, default=str))
