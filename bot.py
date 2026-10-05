import os
import json
import hashlib
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


# =========================
# 基础配置
# =========================

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")

SOURCES_FILE = "sources.json"
PUBLISHED_FILE = "data/published.json"

TIMEOUT = 30

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0 Safari/537.36"
    )
}


# =========================
# 检查配置
# =========================

if not BOT_TOKEN:
    raise RuntimeError("缺少 TELEGRAM_BOT_TOKEN")

if not CHANNEL_ID:
    raise RuntimeError("缺少 TELEGRAM_CHANNEL_ID")


# =========================
# 读取网站配置
# =========================

def load_sources():
    with open(SOURCES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


# =========================
# 读取去重数据
# =========================

def load_published():
    os.makedirs("data", exist_ok=True)

    if not os.path.exists(PUBLISHED_FILE):
        return set()

    try:
        with open(PUBLISHED_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            return set(data)

    except Exception as e:
        print(f"读取去重文件失败: {e}")

    return set()


# =========================
# 保存去重数据
# =========================

def save_published(published):
    os.makedirs("data", exist_ok=True)

    with open(PUBLISHED_FILE, "w", encoding="utf-8") as f:
        json.dump(
            sorted(list(published)),
            f,
            ensure_ascii=False,
            indent=2
        )


# =========================
# 图片唯一 ID
# =========================

def image_id(url):
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


# =========================
# 判断是否图片
# =========================

def is_image_url(url):
    if not url:
        return False

    url_lower = url.lower()

    # 去掉查询参数
    path = urlparse(url_lower).path

    extensions = (
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".gif",
        ".bmp",
        ".avif"
    )

    return path.endswith(extensions)


# =========================
# 获取网页图片
# =========================

def extract_images(page_url):

    print(f"正在访问网站: {page_url}")

    try:
        response = requests.get(
            page_url,
            headers=HEADERS,
            timeout=TIMEOUT,
            verify=False
        )

        response.raise_for_status()

    except Exception as e:
        print(f"网站访问失败: {e}")
        return []

    print(f"网页状态码: {response.status_code}")

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    images = []

    # -------------------------
    # 1. <img src="">
    # -------------------------

    for img in soup.find_all("img"):

        candidates = []

        for attr in [
            "src",
            "data-src",
            "data-original",
            "data-lazy-src",
            "data-url"
        ]:
            value = img.get(attr)

            if value:
                candidates.append(value)

        # -------------------------
        # srcset
        # -------------------------

        srcset = img.get("srcset")

        if srcset:

            for item in srcset.split(","):

                item = item.strip()

                if item:
                    candidates.append(
                        item.split(" ")[0]
                    )

        for src in candidates:

            if not src:
                continue

            src = src.strip()

            full_url = urljoin(
                page_url,
                src
            )

            if full_url.startswith("http"):
                images.append(full_url)

    # -------------------------
    # 2. og:image
    # -------------------------

    for meta in soup.find_all(
        "meta",
        property="og:image"
    ):

        content = meta.get("content")

        if content:

            full_url = urljoin(
page_url,
                content
            )

            images.append(full_url)

    # -------------------------
    # 3. twitter:image
    # -------------------------

    for meta in soup.find_all(
        "meta",
        attrs={"name": "twitter:image"}
    ):

        content = meta.get("content")

        if content:

            full_url = urljoin(
                page_url,
                content
            )

            images.append(full_url)

    # -------------------------
    # 去重
    # -------------------------

    unique = []

    seen = set()

    for url in images:

        if url in seen:
            continue

        seen.add(url)

        unique.append(url)

    print(f"网页发现图片: {len(unique)}")

    return unique


# =========================
# 下载图片
# =========================

def download_image(url):

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=TIMEOUT,
            stream=True,
            verify=False
        )

        response.raise_for_status()

        content_type = response.headers.get(
            "Content-Type",
            ""
        ).lower()

        if not content_type.startswith("image/"):

            print(
                f"跳过非图片: {url}"
            )

            return None

        data = response.content

        # Telegram 图片建议不要太大
        if len(data) > 10 * 1024 * 1024:

            print(
                f"跳过过大图片: {len(data)} bytes"
            )

            return None

        return data

    except Exception as e:

        print(
            f"下载图片失败: {url}"
        )

        print(e)

        return None


# =========================
# 发送 Telegram 图片
# =========================

def send_photo(image_data, source_url):

    telegram_url = (
        f"https://api.telegram.org/bot"
        f"{BOT_TOKEN}/sendPhoto"
    )

    files = {
        "photo": (
            "image.jpg",
            image_data,
            "image/jpeg"
        )
    }

    data = {
        "chat_id": CHANNEL_ID,
        
    }

    try:

        response = requests.post(
            telegram_url,
            data=data,
            files=files,
            timeout=60
        )

        result = response.json()

        if result.get("ok"):

            print("Telegram 发送成功")

            return True

        print(
            "Telegram 发送失败:",
            result
        )

        return False

    except Exception as e:

        print(
            "Telegram 请求失败:",
            e
        )

        return False


# =========================
# 主程序
# =========================

def main():

    print("==============================")
    print("Telegram 网站图片采集器")
    print("==============================")

    sources = load_sources()

    published = load_published()

    total_found = 0
    total_sent = 0
    total_duplicate = 0
    total_failed = 0

    for source in sources:

        name = source.get(
            "name",
            "未知网站"
        )

        page_url = source.get("url")

        max_items = int(
            source.get(
                "max_items",
                10
            )
        )

        print("")
        print("------------------------------")
        print(f"网站: {name}")
        print(f"URL: {page_url}")
        print("------------------------------")

        if not page_url:
            print("没有配置 URL")
            continue

        images = extract_images(
            page_url
        )

        total_found += len(images)

        # 最多发送 max_items 张
        images = images[:max_items]

        for image_url in images:

            uid = image_id(image_url)

            # -------------------------
            # 去重
            # -------------------------

            if uid in published:

                print(
                    f"跳过重复图片: {image_url}"
                )

                total_duplicate += 1

                continue

            print("")
            print(
                f"准备发送图片: {image_url}"
            )
# -------------------------
            # 下载
            # -------------------------

            image_data = download_image(
                image_url
            )

            if not image_data:

                total_failed += 1

                continue

            # -------------------------
            # Telegram
            # -------------------------

            success = send_photo(
                image_data,
                page_url
            )

            if success:

                published.add(uid)

                total_sent += 1

            else:

                total_failed += 1

    # 保存去重数据
    save_published(
        published
    )

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
