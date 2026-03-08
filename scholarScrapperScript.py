from scholarly import scholarly, ProxyGenerator
import requests
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

OPENALEX_API = "https://api.openalex.org/works"
# Add your email for OpenAlex "polite pool" (higher rate limits)
OPENALEX_MAILTO = "eferrante@sinc.unl.edu.ar"

profile_ids = ["ArqlkTUAAAAJ", "s3CmNoEAAAAJ", "nvVcDr4AAAAJ", "o5lqAukAAAAJ", "KqoUj1AAAAAJ","E6U3rCYAAAAJ"]


def setup_proxy():
    pg = ProxyGenerator()
    pg.FreeProxies()
    scholarly.use_proxy(pg)


def fetch_authors_from_openalex(title):
    """Query OpenAlex by title and return list of author names."""
    try:
        r = requests.get(
            OPENALEX_API,
            params={
                "search": title,
                "per_page": 1,
                "select": "title,authorships",
                "mailto": OPENALEX_MAILTO,
            },
            timeout=10,
        )
        r.raise_for_status()
        results = r.json().get("results", [])
        if not results:
            return None
        authorships = results[0].get("authorships", [])
        return ", ".join(a["author"]["display_name"] for a in authorships)
    except Exception:
        return None


def get_publications(profile_ids, progress_callback=None):
    def log(msg):
        print(msg)
        if progress_callback:
            progress_callback(msg)

    all_publications = []
    seen = set()

    # Step 1: scholarly — one fill per author profile (slow, avoid per-paper fills)
    for pid in profile_ids:
        try:
            log(f"Fetching Google Scholar profile: {pid}...")
            author = scholarly.search_author_id(pid)
            scholarly.fill(author)
            name = author.get("name", pid)
            pubs = author.get("publications", [])
            log(f"  {name}: {len(pubs)} publications found")

            for i, pub in enumerate(pubs):
                bib = pub.get("bib", {})
                title = bib.get("title", "")
                year = str(bib.get("pub_year", ""))
                key = (title.lower(), year)
                if not title or key in seen:
                    continue
                seen.add(key)

                author_pub_id = pub.get("author_pub_id", "")
                url = (
                    f"https://scholar.google.com/citations?view_op=view_citation"
                    f"&citation_for_view={author_pub_id}"
                    if author_pub_id else ""
                )
                all_publications.append({
                    "title": title,
                    "year": year,
                    "journal": bib.get("citation", ""),
                    "citations": pub.get("num_citations", 0),
                    "url": url,
                    "authors": None,  # filled in step 2
                })
        except Exception as e:
            log(f"  Error fetching profile {pid}: {e}")

    # Step 2: OpenAlex — parallel author lookup by title
    log(f"Fetching authors from OpenAlex for {len(all_publications)} papers...")
    with ThreadPoolExecutor(max_workers=8) as executor:
        future_to_idx = {
            executor.submit(fetch_authors_from_openalex, pub["title"]): i
            for i, pub in enumerate(all_publications)
        }
        for future in as_completed(future_to_idx):
            i = future_to_idx[future]
            authors = future.result()
            all_publications[i]["authors"] = authors or " "

    all_publications.sort(key=lambda x: x["year"], reverse=True)
    return all_publications


def build_html(publications):
    from itertools import groupby

    body = ""
    for year, group in groupby(publications, key=lambda x: x["year"]):
        body += f"<h3>{year}</h3>\n"
        for pub in group:
            authors = (pub.get("authors") or "").strip()
            title = pub.get("title", "")
            journal = (pub.get("journal") or "").strip()
            url = pub.get("url") or ""

            title_html = (
                f'<a href="{url}" target="_blank"><b>{title}</b></a>'
                if url else f"<b>{title}</b>"
            )
            journal_part = f" {journal}" if journal else ""
            entry = f'{authors}. &ldquo;{title_html}&rdquo;{journal_part}, ({year}).'
            body += f"<p>{entry}</p>\n"

    return f"""<html>
<head>
    <title>Combined Publications List</title>
    <style>
        body {{ font-family: Arial, sans-serif; max-width: 900px; margin: 40px auto; line-height: 1.6; }}
        h3 {{ margin-top: 2em; border-bottom: 1px solid #ccc; padding-bottom: 4px; }}
        p {{ margin: 0.5em 0; }}
        a {{ color: #1a0dab; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <h2>Combined Publications List</h2>
    {body}
</body>
</html>"""


def generate_html(publications, output_file="publications.html"):
    html = build_html(publications)
    with open(output_file, "w") as f:
        f.write(html)
    print(f"\nHTML written to {os.path.abspath(output_file)}")


if __name__ == "__main__":
    setup_proxy()
    publications = get_publications(profile_ids)
    generate_html(publications)
