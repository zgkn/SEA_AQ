"""One-off probe of the MyEQMS APIMS page (Malaysia DOE).

Loads the page once in headless Chromium, records every XHR/fetch call the app
makes (URL, status, content type, body preview), saves the rendered text and
screenshots, then tries clicking anything labelled PM2.5 to see what extra
calls that triggers. Nothing is scraped at scale: one visit, a few clicks.
"""
import json
import os
import pathlib
import re

from playwright.sync_api import sync_playwright

URL = "https://eqms.doe.gov.my/APIMS/main"
OUT = pathlib.Path("eqms_out")
OUT.mkdir(exist_ok=True)

calls = []


def on_response(resp):
    req = resp.request
    if req.resource_type not in ("xhr", "fetch"):
        return
    ct = resp.headers.get("content-type", "")
    entry = {
        "n": len(calls),
        "method": req.method,
        "url": resp.url,
        "status": resp.status,
        "content_type": ct,
        "post_data": (req.post_data or "")[:500],
    }
    try:
        if "json" in ct or "text" in ct:
            body = resp.text()
            entry["body_len"] = len(body)
            (OUT / f"resp_{entry['n']:03d}.txt").write_text(body[:100_000])
            entry["preview"] = body[:300]
            entry["mentions_pm25"] = bool(re.search(r"pm\s?2\.?5", body, re.I))
    except Exception as exc:  # response may be gone after navigation
        entry["body_error"] = str(exc)
    calls.append(entry)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(
            viewport={"width": 1400, "height": 900},
            record_har_path=str(OUT / "session.har"),
        )
        page = ctx.new_page()
        page.on("response", on_response)

        page.goto(URL, wait_until="networkidle", timeout=90_000)
        page.wait_for_timeout(5_000)
        page.screenshot(path=str(OUT / "01_landing.png"), full_page=True)
        (OUT / "landing_text.txt").write_text(page.inner_text("body"))
        calls_after_landing = len(calls)

        # Try anything labelled PM2.5 (tab, button, menu item, table header).
        try:
            hits = page.get_by_text(re.compile(r"PM\s?2\.?5", re.I))
            count = hits.count()
            print(f"elements mentioning PM2.5: {count}")
            for i in range(min(count, 3)):
                try:
                    hits.nth(i).click(timeout=5_000)
                    page.wait_for_timeout(4_000)
                    page.screenshot(path=str(OUT / f"02_click_{i}.png"), full_page=True)
                    (OUT / f"click_{i}_text.txt").write_text(page.inner_text("body"))
                except Exception as exc:
                    print(f"click {i} failed: {exc}")
        except Exception as exc:
            print(f"PM2.5 search failed: {exc}")

        ctx.close()
        browser.close()

    (OUT / "calls.json").write_text(json.dumps(calls, indent=2))

    lines = [f"## MyEQMS probe", f"XHR/fetch calls: {len(calls)} "
             f"({calls_after_landing} on landing)", ""]
    for c in calls:
        flag = " **PM2.5**" if c.get("mentions_pm25") else ""
        lines.append(f"- `{c['method']} {c['status']}` {c['url']} "
                     f"[{c['content_type']}]{flag}")
    summary = "\n".join(lines)
    print(summary)
    gh = os.environ.get("GITHUB_STEP_SUMMARY")
    if gh:
        with open(gh, "a") as fh:
            fh.write(summary + "\n")


if __name__ == "__main__":
    main()
