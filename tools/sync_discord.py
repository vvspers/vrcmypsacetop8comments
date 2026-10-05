import io
import json
import os
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
ATLAS_BANKS = 6
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
        headers={"Authorization": f"Bot {TOKEN}", "User-Agent": "MySpaceTop8VRChat/1.0"},
        timeout=30,
    )
    if r.status_code == 401:
        die("Discord rejected the bot token. Re-check the DISCORD_BOT_TOKEN GitHub secret.")
    if r.status_code == 403:
        die("Discord denied access. Make sure the bot can View Channel and Read Message History in the comments channel.")
    if r.status_code == 404:
        die("Discord could not find the channel. Re-check DISCORD_CHANNEL_ID and make sure the bot is in that server.")
    r.raise_for_status()
    return r.json()


def get_display_name(message):
    member = message.get("member") or {}
    author = message.get("author") or {}
    return member.get("nick") or author.get("global_name") or author.get("username") or "Unknown User"


def avatar_url(message, guild_id: str):
    member = message.get("member") or {}
    author = message.get("author") or {}
    user_id = str(author.get("id", "0"))

    # Discord server-specific profile photo, if the member uses one.
    member_avatar = member.get("avatar")
    if member_avatar and guild_id:
        ext = "gif" if str(member_avatar).startswith("a_") else "png"
        return f"https://cdn.discordapp.com/guilds/{guild_id}/users/{user_id}/avatars/{member_avatar}.{ext}?size=256"

    # Normal Discord profile photo.
    user_avatar = author.get("avatar")
    if user_avatar:
        ext = "gif" if str(user_avatar).startswith("a_") else "png"
        return f"https://cdn.discordapp.com/avatars/{user_id}/{user_avatar}.{ext}?size=256"

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
        d.ellipse((52, 32, 204, 184), fill=(120, 140, 170))
        d.rounded_rectangle((35, 150, 221, 260), radius=60, fill=(120, 140, 170))
        return img


def clean_message(text: str):
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if len(text) > MAX_MESSAGE_CHARS:
        text = text[: MAX_MESSAGE_CHARS - 1] + "…"
    return text


def format_time(iso_time: str):
    try:
        dt = datetime.fromisoformat(iso_time.replace("Z", "+00:00"))
        dt = dt.astimezone(ZoneInfo(TIMEZONE))
        # Cross-platform 12-hour formatting without leading zero.
        hour = dt.strftime("%I").lstrip("0") or "12"
        return f"{dt.strftime('%b')} {dt.day}, {dt.year} {hour}:{dt.strftime('%M %p')}"
    except Exception:
        return iso_time


def make_revision(comments, photo_urls):
    payload = json.dumps({"comments": comments, "photos": photo_urls}, ensure_ascii=False, sort_keys=True).encode("utf-8")
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
        content = clean_message(msg.get("content", ""))
        if not content:
            continue
        chosen.append(msg)
        if len(chosen) >= COUNT:
            break

    comments = []
    photos = []
    photo_urls = []
    for msg in chosen:
        comments.append({
            "name": get_display_name(msg),
            "time": format_time(msg.get("timestamp", "")),
            "message": clean_message(msg.get("content", "")),
        })
        purl = avatar_url(msg, guild_id)
        photo_urls.append(purl)
        photos.append(download_profile_photo(purl))

    # Fill unused atlas cells with a plain placeholder so the atlas is always 4x2.
    while len(photos) < COUNT:
        photos.append(Image.new("RGB", (CELL, CELL), (235, 240, 248)))

    revision = make_revision(comments, photo_urls)
    # Rotate six filenames by 5-minute time slot so each scheduled run naturally
    # publishes to a different URL. This makes CDN caching harmless for profile photos.
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
    (OUT / "comments.json").write_text(json.dumps(feed, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    # Ensure every bank exists from the first deployment. Banks that have not yet been
    # used are copies of the current atlas; later workflow runs replace them naturally.
    for b in range(ATLAS_BANKS):
        p = OUT / f"profile-photos-{b}.jpg"
        if not p.exists():
            atlas.save(p, "JPEG", quality=88, optimize=True, progressive=True)

    print(f"Published {len(comments)} comments, revision {revision}, atlas bank {bank}.")


if __name__ == "__main__":
    main()
