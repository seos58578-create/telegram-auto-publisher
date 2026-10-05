import os
import json
import time
import html
import requests
import feedparser

from bs4 import BeautifulSoup


BOT_TOKEN = os.environ["BOT_TOKEN"]
CHANNEL_ID = os.environ["CHANNEL_ID"]

SOURCES_FILE = "sources.json"
DATA_FILE = "data.json"


def load_sources():
    with open(SOURCES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def load_data():
    if not os.path.exists(DATA_FILE):
        return {"published": []}

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def clean_text(text):
    if not text:
        return ""

    soup = BeautifulSoup(text, "html.parser")
    return soup.get_text(" ", strip=True)


def get_image(entry):
    if hasattr(entry, "media_content"):
        for item in entry.media_content:
            url = item.get("url")
            if url:
                return url

    if hasattr(entry, "media_thumbnail"):
        for item in entry.media_thumbnail:
            url = item.get("url")
            if url:
                return url

    if hasattr(entry, "enclosures"):
        for item in entry.enclosures:
            url = item.get("href")
            if url:
                return url

    description = entry.get("description", "")

    soup = BeautifulSoup(
        description,
        "html.parser"
    )

    image = soup.find("img")

    if image:
        return image.get("src")

    return None


def send_message(text):
    url = (
        f"https://api.telegram.org/"
        f"bot{BOT_TOKEN}/sendMessage"
    )

    response = requests.post(
        url,
        data={
            "chat_id": CHANNEL_ID,
            "text": text,
            "parse_mode": "HTML"
        },
        timeout=30
    )

    return response.json()


def send_photo(photo, caption):
    url = (
        f"https://api.telegram.org/"
        f"bot{BOT_TOKEN}/sendPhoto"
    )

    response = requests.post(
        url,
        data={
            "chat_id": CHANNEL_ID,
            "photo": photo,
            "caption": caption,
            "parse_mode": "HTML"
        },
        timeout=30
    )

    return response.json()


def build_message(
    title,
    summary,
    source,
    article_url
):
    title = html.escape(title)

    summary = clean_text(summary)

    if len(summary) > 600:
        summary = summary[:600] + "..."

    summary = html.escape(summary)
    source = html.escape(source)

    article_url = html.escape(
        article_url,
        quote=True
    )

    return (
        f"<b>📰 {title}</b>\n\n"
        f"{summary}\n\n"
        f"📌 来源：{source}\n\n"
        f'<a href="{article_url}">'
        f"🔗 阅读原文"
        f"</a>\n\n"
        f"#资讯"
    )


def process_source(source, data):
    name = source["name"]
    rss_url = source["rss"]

    print(f"正在检查：{name}")

    feed = feedparser.parse(rss_url)

    if not feed.entries:
        print(f"{name} 没有发现文章")
        return False

    changed = False

    for entry in reversed(feed.entries[:10]):

        title = entry.get(
            "title",
            ""
        ).strip()

        article_url = entry.get(
            "link",
            ""
        ).strip()

        if not title or not article_url:
            continue

        if article_url in data["published"]:
            continue

        summary = entry.get(
            "summary",
            entry.get(
                "description",
                ""
            )
        )

        image = get_image(entry)

        message = build_message(
            title,
            summary,
            name,
            article_url
        )

        print(f"发现新文章：{title}")

        if image:
            result = send_photo(
                image,
                message
            )
        else:
            result = send_message(
                message
            )

        if result.get("ok"):
            print(f"发布成功：{title}")

            data["published"].append(
                article_url
            )
    changed = True

            time.sleep(2)

        else:
            print(
                "Telegram 发布失败：",
                result
            )

    return changed


def main():
    data = load_data()
    sources = load_sources()

    changed = False

    for source in sources:

        try:
            result = process_source(
                source,
                data
            )

            if result:
                changed = True

        except Exception as error:
            print(
                f"处理 {source['name']} 出错："
                f"{error}"
            )

    data["published"] = (
        data["published"][-1000:]
    )

    if changed:
        save_data(data)
        print("去重数据已经保存")

    print("本次任务完成")


if name == "__main__":
    main()
