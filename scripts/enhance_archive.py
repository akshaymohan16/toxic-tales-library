"""Enrich generated archive pages without changing reviewed renderer inputs.

Run after build_motion.py and before hashing/deploying the site. This never
renders or changes media, evidence, release records or original episode JSON.
"""
import argparse
import html
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

CHANNEL_ID = "UCDvftxMMdtGSntm-ezcPfCg"
OLD_PROVENANCE = ("Reference imagery and explanatory animation are not footage or "
                  "raw data from this experiment. Narration is synthetic.")
START = "<!-- confirmed-social-links:start -->"
END = "<!-- confirmed-social-links:end -->"


def read(path, default=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def platform_url(url, platform):
    """Only actual provider permalink shapes become published-story buttons."""
    if not isinstance(url, str):
        return False
    try:
        parts = urlsplit(url)
        if (parts.scheme != "https" or parts.username or parts.password or
                parts.port or parts.query or parts.fragment):
            return False
        if platform == "instagram":
            return (parts.hostname in {"instagram.com", "www.instagram.com"} and
                    re.fullmatch(r"/(?:reel|p)/[A-Za-z0-9_-]+/?", parts.path) is not None)
        if platform == "youtube":
            return (parts.hostname in {"youtube.com", "www.youtube.com"} and
                    re.fullmatch(r"/shorts/[A-Za-z0-9_-]{11}/?", parts.path) is not None)
    except ValueError:
        pass
    return False


def confirmed_publications(posts, episode_id):
    """Derive display links from positive receipts, with the YouTube live gate."""
    result, seen = [], set()
    for post in posts:
        platform = post.get("platform", "instagram")
        url = post.get("public_url")
        if (post.get("episode_id") != episode_id or post.get("status") != "published"
                or post.get("provider_status") != "PUBLISHED"
                or not platform_url(url, platform)):
            continue
        if platform == "youtube":
            live = post.get("live_verification", {})
            if (post.get("youtube_channel_id") != CHANNEL_ID or
                    live.get("decision") != "pass" or live.get("url") != url or
                    live.get("channel_id") != CHANNEL_ID):
                continue
        key = platform, url.rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        result.append({"platform": platform, "status": "published",
                       "public_url": url, "post_id": post.get("post_id"),
                       "date": post.get("publication_date")})
    return result


def provenance_note(episode):
    """Use each episode's verified asset descriptions, not guessed study status."""
    note = ("The credits below identify the source and use of each visual. "
            "Reference imagery and explanatory illustrations are distinguished "
            "from experimental footage where present. Narration is synthetic.")
    videos = [asset for asset in episode.get("production", {}).get("assets", [])
              if str(asset.get("media_type", "")).startswith("video/")]
    for asset in videos:
        creator = asset.get("creator", "Credited source")
        changes = asset.get("changes", "")
        if changes:
            note += " Video source - " + str(creator) + ": " + str(changes)
    return html.escape(note)


def social_block(publications):
    if not publications:
        return ""
    links = []
    for post in publications:
        label = "Watch on YouTube" if post["platform"] == "youtube" else "View on Instagram"
        links.append('<a class="button secondary" href="' +
                     html.escape(post["public_url"], quote=True) +
                     '" target="_blank" rel="noopener noreferrer">' + label + "</a>")
    return (START + '<section class="panel"><h2>Published versions</h2>'
            '<div class="actions">' + "".join(links) + "</div></section>" + END)


def enhance_page(content, episode, publications):
    # Rebuilding starts from the exact renderer output; repeated runs are safe.
    content = re.sub(re.escape(START) + r".*?" + re.escape(END), "",
                     content, flags=re.DOTALL)
    content = content.replace(OLD_PROVENANCE, provenance_note(episode))
    block = social_block(publications)
    if block:
        if "<footer>" not in content:
            raise ValueError("Generated page has no footer insertion point")
        content = content.replace("<footer>", block + "<footer>", 1)
    return content


def run(root):
    root = Path(root)
    site = root / "site"
    papers_path = site / "papers.json"
    papers = read(papers_path)
    if not isinstance(papers, list):
        raise ValueError("Build papers.json before enhancing the archive")
    ledger = read(root / "automation/published.json", {"posts": []})
    config = read(root / "automation/config.json", {})
    changed_pages = 0
    for entry in papers:
        episode_id = entry.get("id", "")
        if not re.fullmatch(r"TT-\d{3,}", episode_id):
            raise ValueError("Unsafe episode identity in papers.json")
        episode = read(root / "episodes" / (episode_id.lower() + ".json"))
        if not isinstance(episode, dict) or episode.get("id") != episode_id:
            raise ValueError("Missing matching episode source: " + episode_id)
        publications = confirmed_publications(ledger.get("posts", []), episode_id)
        entry["confirmed_publications"] = publications
        pages = [site / "sources" / (episode_id.lower() + ".html"),
                 site / ("pilot-" + episode_id.lower() + ".html")]
        if config.get("active_pilot_id") == episode_id:
            pages.append(site / "pilot.html")
        for page in pages:
            if not page.is_file():
                continue
            original = page.read_text(encoding="utf-8")
            enhanced = enhance_page(original, episode, publications)
            if enhanced != original:
                page.write_text(enhanced, encoding="utf-8")
                changed_pages += 1
    papers_path.write_text(json.dumps(papers, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    return {"episodes": len(papers), "changed_pages": changed_pages,
            "confirmed_social_links": sum(len(p["confirmed_publications"]) for p in papers)}


if __name__ == "__main__":
    args = argparse.ArgumentParser()
    args.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    print(json.dumps(run(args.parse_args().root), indent=2))
