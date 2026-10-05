import io
import json
import os
import re
import sys
import hashlib
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from PIL import Image, ImageOps, ImageDraw

API = "https://discord.com/api/v10"
OUT = Path(__file__).resolve().parents[1] / "site"
COUNT = 8
ATLAS_COLS = 4
ATLAS_ROWS = 2
CELL = 256
ATLAS_BANKS = 24
TIMEZONE = os.environ.get("DISPLAY_TIMEZONE", "America/New_York")
MAX_MESSAGE_CHARS = int(os.environ.get("MAX_MESSAGE_CHARS", "600"))

TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
CHANNEL_ID = os.environ.get("DISCORD_CHANNEL_ID", "").strip()


def die(message: str):
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def discord_get(path: str):
    r = requests.get(
        API + path,
        headers={"Authorization": f"Bot {TOKEN}", "User-Agent": "MySpaceTop8VRChat/2.0"},
        timeout=30,
    )
    if r.status_code == 401:
        die("Discord rejected the bot token. Replace the DISCORD_BOT_TOKEN GitHub secret.")
    if r.status_code == 403:
        die("Discord denied access. Give the bot View Channels and Read Message History in the comments channel.")
    if r.status_code == 404:
        die("Discord could not find the channel. Re-check DISCORD_CHANNEL_ID and confirm the bot is in that server.")
    r.raise_for_status()
    return r.json()


def get_display_name(message):
    member = message.get("member") or {}
    author = message.get("author") or {}
    return member.get("nick") or author.get("global_name") or author.get("username") or "Unknown User"


def profile_photo_url(message, guild_id: str):
    member = message.get("member") or {}
    author = message.get("author") or {}
    user_id = str(author.get("id", "0"))

    # Server-specific Discord profile photo, when one is set.
    member_photo = member.get("avatar")
    if member_photo and guild_id:
        ext = "gif" if str(member_photo).startswith("a_") else "png"
        return f"https://cdn.discordapp.com/guilds/{guild_id}/users/{user_id}/avatars/{member_photo}.{ext}?size=256"

    # Normal Discord profile photo.
    user_photo = author.get("avatar")
    if user_photo:
        ext = "gif" if str(user_photo).startswith("a_") else "png"
        return f"https://cdn.discordapp.com/avatars/{user_id}/{user_photo}.{ext}?size=256"

    # Discord default profile photo.
    try:
        discriminator = str(author.get("discriminator") or "0")
        if discriminator != "0":
            index = int(discriminator) % 5
        else:
            index = (int(user_id) >> 22) % 6
    except Exception:
        index = 0
    return f"https://cdn.discordapp.com/embed/avatars/{index}.png"


def download_profile_photo(url: str) -> Image.Image:
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        img = Image.open(io.BytesIO(r.content)).convert("RGB")
        return ImageOps.fit(img, (CELL, CELL), method=Image.Resampling.LANCZOS)
    except Exception as exc:
        print(f"WARN: profile photo failed ({exc}); using placeholder")
        img = Image.new("RGB", (CELL, CELL), (205, 215, 230))
        d = ImageDraw.Draw(img)
        d.ellipse((52, 28, 204, 180), fill=(120, 140, 170))
        d.rounded_rectangle((35, 148, 221, 258), radius=55, fill=(120, 140, 170))
        return img


def clean_message(message):
    text = (message.get("content") or "").replace("\r\n", "\n").replace("\r", "\n").strip()

    # Make Discord user mentions readable in plain Unity text.
    for user in message.get("mentions") or []:
        uid = str(user.get("id") or "")
        name = user.get("global_name") or user.get("username") or "user"
        if uid:
            text = text.replace(f"<@{uid}>", f"@{name}")
            text = text.replace(f"<@!{uid}>", f"@{name}")

    # Custom Discord emoji cannot render in TMP without extra assets, so show :name:.
    text = re.sub(r"<a?:([A-Za-z0-9_]+):\d+>", r":\1:", text)

    if len(text) > MAX_MESSAGE_CHARS:
        text = text[: MAX_MESSAGE_CHARS - 1] + "…"
    return text


def format_time(iso_time: str):
    try:
        dt = datetime.fromisoformat(iso_time.replace("Z", "+00:00"))
        dt = dt.astimezone(ZoneInfo(TIMEZONE))
        hour = dt.strftime("%I").lstrip("0") or "12"
        return f"{dt.strftime('%b')} {dt.day}, {dt.year} {hour}:{dt.strftime('%M %p')}"
    except Exception:
        return iso_time


def make_revision(comments, photo_urls):
    payload = json.dumps(
        {"comments": comments, "photos": photo_urls},
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def main():
    if not TOKEN:
        die("DISCORD_BOT_TOKEN is missing.")
    if not CHANNEL_ID:
        die("DISCORD_CHANNEL_ID is missing.")

    OUT.mkdir(parents=True, exist_ok=True)

    channel = discord_get(f"/channels/{CHANNEL_ID}")
    guild_id = str(channel.get("guild_id") or "")

    raw = discord_get(f"/channels/{CHANNEL_ID}/messages?limit=50")
    chosen = []
    for msg in raw:
        author = msg.get("author") or {}
        if author.get("bot"):
            continue
        content = clean_message(msg)
        if not content:
            continue
        chosen.append((msg, content))
        if len(chosen) >= COUNT:
            break

    comments = []
    photos = []
    photo_urls = []

    for msg, content in chosen:
        comments.append({
            "name": get_display_name(msg),
            "time": format_time(msg.get("timestamp", "")),
            "message": content,
        })
        purl = profile_photo_url(msg, guild_id)
        photo_urls.append(purl)
        photos.append(download_profile_photo(purl))

    while len(photos) < COUNT:
        photos.append(Image.new("RGB", (CELL, CELL), (235, 240, 248)))

    revision = make_revision(comments, photo_urls)

    # Rotate through 24 fixed file names. Unity knows all 24 URLs in advance,
    # which avoids dynamic VRCUrl creation and greatly reduces CDN-cache problems.
    bank = int(datetime.now().timestamp() // 300) % ATLAS_BANKS

    atlas = Image.new("RGB", (CELL * ATLAS_COLS, CELL * ATLAS_ROWS), (235, 240, 248))
    for i, photo in enumerate(photos[:COUNT]):
        x = (i % ATLAS_COLS) * CELL
        y = (i // ATLAS_COLS) * CELL
        atlas.paste(photo, (x, y))

    atlas_path = OUT / f"profile-photos-{bank}.jpg"
    atlas.save(atlas_path, "JPEG", quality=88, optimize=True, progressive=True)

    feed = {
        "revision": revision,
        "atlasBank": bank,
        "count": len(comments),
        "comments": comments,
    }
    (OUT / "comments.json").write_text(
        json.dumps(feed, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    # All 24 files exist from the first deployment, so every serialized Unity URL is valid.
    for b in range(ATLAS_BANKS):
        p = OUT / f"profile-photos-{b}.jpg"
        if not p.exists():
            atlas.save(p, "JPEG", quality=88, optimize=True, progressive=True)

    print(f"Published {len(comments)} comments, revision {revision}, profile-photo bank {bank}.")


if __name__ == "__main__":
    main()
