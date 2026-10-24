"""One-off probe #2 of the MyEQMS APIMS page (Malaysia DOE).

1. Load the page once in headless Chromium and save every response from the
   eqms.doe.gov.my host in full (unique file names; ArcGIS basemap traffic is
   only listed, not saved).
2. Download the site's own JS bundles and list every API endpoint name found.
3. Call the discovered JSON endpoints with plain urllib (no browser) to see
   whether a browser is needed at all.
"""
import itertools
import json
import os
import pathlib
import re
import urllib.request

from playwright.sync_api import sync_playwright

BASE = "https://eqms.doe.gov.my"
URL = f"{BASE}/APIMS/main"
OUT = pathlib.Path("eqms_out")
OUT.mkdir(exist_ok=True)

counter = itertools.count()
calls = []
scripts = set()


def on_response(resp):
    req = resp.request
    url = resp.url
    if url.startswith(BASE) and req.resource_type == "script":
        scripts.add(url)
    if req.resource_type not in ("xhr", "fetch"):
        return
    entry = {"n": next(counter), "method": req.method, "url": url,
             "status": resp.status,
             "content_type": resp.headers.get("content-type", "")}
    if url.startswith(BASE):
        try:
            body = resp.text()
            entry["body_len"] = len(body)
            name = re.sub(r"[^A-Za-z0-9]+", "_", url.split("//", 1)[1])[:80]
            (OUT / f"api_{entry['n']:03d}_{name}.json").write_text(body[:200_000])
        except Exception as exc:
            entry["body_error"] = str(exc)
    calls.append(entry)


def plain_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status, r.read().decode("utf-8", "replace")


def main():
    lines = ["## MyEQMS probe #2", ""]
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1400, "height": 900})
        page = ctx.new_page()
        page.on("response", on_response)
        page.goto(URL, wait_until="networkidle", timeout=90_000)
        page.wait_for_timeout(5_000)
        page.screenshot(path=str(OUT / "landing.png"), full_page=True)

        # 2. endpoints named in the site's own JS
        endpoints = set()
        for s in sorted(scripts):
            try:
                text = ctx.request.get(s).text()
            except Exception as exc:
                lines.append(f"- could not fetch {s}: {exc}")
                continue
            for m in re.findall(r"(?:publicportal\w*|api3)/[A-Za-z0-9_/\-]+", text):
                endpoints.add(m)
        (OUT / "endpoints.txt").write_text("\n".join(sorted(endpoints)))
        lines.append(f"JS bundles scanned: {len(scripts)}; endpoint strings: {len(endpoints)}")
        lines += [f"- `{e}`" for e in sorted(endpoints)]
        ctx.close()
        browser.close()

    # 1. summary of eqms calls
    lines += ["", "### eqms.doe.gov.my calls seen in browser"]
    for c in calls:
        if c["url"].startswith(BASE):
            lines.append(f"- {c['method']} {c['status']} {c['url']} ({c.get('body_len')} bytes)")
    other = sum(1 for c in calls if not c["url"].startswith(BASE))
    lines.append(f"(+ {other} third-party calls, e.g. ArcGIS basemap)")
    (OUT / "calls.json").write_text(json.dumps(calls, indent=2))

    # 3. plain HTTP (no browser)
    lines += ["", "### Plain HTTP test (no browser)"]
    tests = [
        "/api3/publicportalapims/mapcaqm",
        "/api3/publicportalapims/statelist",
        "/api3/publicportalapims/apiranking",
    ]
    for t in tests:
        try:
            status, body = plain_get(BASE + t)
            (OUT / f"plain_{t.rsplit('/', 1)[1]}.json").write_text(body[:200_000])
            lines.append(f"- {t}: HTTP {status}, {len(body)} bytes")
        except Exception as exc:
            lines.append(f"- {t}: FAILED {exc}")

    # field names of the first record of the main endpoints
    for f in sorted(OUT.glob("api_*")) + sorted(OUT.glob("plain_*")):
        try:
            data = json.loads(f.read_text())
        except Exception:
            continue
        rec = data
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, list) and v and isinstance(v[0], dict):
                    lines.append(f"- `{f.name}` key `{k}`: {len(v)} rows; fields: {list(v[0].keys())}")
        elif isinstance(data, list) and data and isinstance(data[0], dict):
            lines.append(f"- `{f.name}`: {len(data)} rows; fields: {list(data[0].keys())}")

    summary = "\n".join(lines)
    (OUT / "summary.md").write_text(summary)
    print(summary)
    gh = os.environ.get("GITHUB_STEP_SUMMARY")
    if gh:
        with open(gh, "a") as fh:
            fh.write(summary + "\n")


if __name__ == "__main__":
    main()
