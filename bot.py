import os
import json
import hashlib
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO


BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")

SOURCES_FILE = "sources.json"
PUBLISHED_FILE = "data/published.json"

MIN_WIDTH = 300
MIN_HEIGHT = 200
MAX_IMAGE_SIZE = 10 * 1024 * 1024

TIMEOUT = 20


EXCLUDE_KEYWORDS = [
    "logo",
    "icon",
    "favicon",
    "nav",
    "menu",
    "header",
    "footer",
    "arrow",
    "button",
    "loading",
    "avatar",
    "share",
    "sprite",
]


def load_sources():
    if not os.path.exists(SOURCES_FILE):
        print("找不到 sources.json")
        return []

    try:
        with open(SOURCES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            print("sources.json 必须是数组")
            return []

        return data

    except json.JSONDecodeError as e:
        print("sources.json JSON 格式错误：")
        print(e)
        return []


def load_published():
    os.makedirs("data", exist_ok=True)

    if not os.path.exists(PUBLISHED_FILE):
        return set()

    try:
        with open(PUBLISHED_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        return set(data)

    except Exception:
        return set()


def save_published(published):
    os.makedirs("data", exist_ok=True)

    with open(PUBLISHED_FILE, "w", encoding="utf-8") as f:
        json.dump(
            list(published),
            f,
            ensure_ascii=False,
            indent=2
        )


def image_id(url):
    return hashlib.sha256(
        url.encode("utf-8")
    ).hexdigest()


def image_content_id(data):
    return hashlib.sha256(data).hexdigest()


def is_valid_image(data):
    try:
        image = Image.open(BytesIO(data))

        width, height = image.size

        print(f"图片尺寸: {width} x {height}")

        if width < MIN_WIDTH:
            return False

        if height < MIN_HEIGHT:
            return False

        return True

    except Exception:
        return False


def download_image(url):
    try:
        print(f"下载图片: {url}")

        response = requests.get(
            url,
            timeout=TIMEOUT,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )

        response.raise_for_status()

        data = response.content

        if len(data) > MAX_IMAGE_SIZE:
            print("图片超过 10MB，跳过")
            return None

        content_type = response.headers.get(
            "Content-Type",
            ""
        ).lower()

        if not content_type.startswith("image/"):
            print(f"不是图片: {content_type}")
            return None

        if not is_valid_image(data):
            print("图片尺寸不符合要求")
            return None

        return data

    except Exception as e:
        print(f"下载图片失败: {url}")
        print(e)
        return None


def send_photo(data):
    if not BOT_TOKEN:
        print("缺少 TELEGRAM_BOT_TOKEN")
        return False

    if not CHANNEL_ID:
        print("缺少 TELEGRAM_CHANNEL_ID")
        return False

    url = (
        f"https://api.telegram.org/bot"
        f"{BOT_TOKEN}/sendPhoto"
    )

    try:
        files = {
            "photo": (
                "image.jpg",
                data,
                "image/jpeg"
            )
        }

        payload = {
            "chat_id": CHANNEL_ID
        }

        response = requests.post(
            url,
            data=payload,
            files=files,
            timeout=30
        )

        if response.ok:
            print("发送 Telegram 成功")
            return True

        print("Telegram 发送失败")
        print(response.text)

        return False

    except Exception as e:
        print("Telegram 请求失败")
        print(e)
        return False


def extract_website_images(page_url):
    print(f"正在访问网站: {page_url}")

    try:
        response = requests.get(
            page_url,
            timeout=TIMEOUT,
            headers={
"User-Agent": "Mozilla/5.0"
            }
        )

        response.raise_for_status()

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        result = []

        for img in soup.find_all("img"):

            src = (
                img.get("src")
                or img.get("data-src")
                or img.get("data-original")
            )

            if not src:
                continue

            src_lower = src.lower()

            if any(
                keyword in src_lower
                for keyword in EXCLUDE_KEYWORDS
            ):
                continue

            if src.startswith("//"):
                src = "https:" + src

            elif src.startswith("/"):
                from urllib.parse import urljoin
                src = urljoin(page_url, src)

            elif not src.startswith("http"):
                from urllib.parse import urljoin
                src = urljoin(page_url, src)

            if src not in result:
                result.append(src)

        return result

    except Exception as e:
        print("网站采集失败:")
        print(e)
        return []


def extract_api_images(source):
    api_url = source.get("url")
    image_field = source.get(
        "image_field",
        "imageUrl"
    )

    print(f"正在请求 API: {api_url}")

    try:
        response = requests.get(
            api_url,
            timeout=TIMEOUT,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json"
            }
        )

        response.raise_for_status()

        data = response.json()

    except Exception as e:
        print("API 请求失败:")
        print(e)
        return []

    result = []

    def walk(obj):

        if isinstance(obj, dict):

            value = obj.get(image_field)

            if isinstance(value, str):
                if value.startswith("http"):
                    result.append(value)

            for v in obj.values():
                walk(v)

        elif isinstance(obj, list):

            for item in obj:
                walk(item)

    walk(data)

    # 去重
    result = list(dict.fromkeys(result))

    print(f"API 找到图片: {len(result)}")

    return result


def main():

    print("==============================")
    print("Telegram 图片采集器")
    print("==============================")

    sources = load_sources()
    published = load_published()

    total_found = 0
    total_sent = 0
    total_duplicate = 0
    total_failed = 0

    for source in sources:

        source_type = source.get(
            "type",
            "website"
        )

        name = source.get(
            "name",
            "未知来源"
        )

        max_items = int(
            source.get(
                "max_items",
                10
            )
        )

        print("")
        print("------------------------------")
        print(f"来源: {name}")
        print(f"类型: {source_type}")
        print("------------------------------")

        if source_type == "api":

            images = extract_api_images(
                source
            )

        else:

            page_url = source.get("url")

            if not page_url:
                print("没有配置 URL")
                continue

            images = extract_website_images(
                page_url
            )

        total_found += len(images)

        images = images[:max_items]

        for image_url in images:

            url_id = image_id(
                image_url
            )

            if url_id in published:

                print("URL 已发布，跳过")

                total_duplicate += 1

                continue

            image_data = download_image(
                image_url
            )

            if not image_data:

                total_failed += 1

                continue

            content_id = image_content_id(
                image_data
            )

            if content_id in published:

                print("图片内容已发布，跳过")

                published.add(url_id)
total_duplicate += 1

                continue

            if send_photo(image_data):

                published.add(url_id)

                published.add(content_id)

                total_sent += 1

            else:

                total_failed += 1

    save_published(published)

    print("")
    print("==============================")
    print("本次任务完成")
    print(f"发现图片: {total_found}")
    print(f"成功发送: {total_sent}")
    print(f"重复跳过: {total_duplicate}")
    print(f"失败数量: {total_failed}")
    print("==============================")


if __name__ == "__main__":
    main()
