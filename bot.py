import os
import json
import hashlib
from io import BytesIO
from urllib.parse import urljoin
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from PIL import Image


# ============================================================
# 配置
# ============================================================

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")

SOURCES_FILE = "sources.json"
PUBLISHED_FILE = "data/published.json"

REQUEST_TIMEOUT = 20

MIN_WIDTH = 300
MIN_HEIGHT = 200

MAX_IMAGE_SIZE = 10 * 1024 * 1024


# ============================================================
# 排除关键词
# ============================================================

EXCLUDE_KEYWORDS = [
    "logo",
    "icon",
    "favicon",
    "sprite",
    "nav",
    "navigation",
    "menu",
    "header",
    "footer",
    "arrow",
    "button",
    "loading",
    "avatar",
    "share",
    "search",
    "close",
    "play",
    "pause",
    "next",
    "prev",
    "left",
    "right",
]


# ============================================================
# 基础 HTTP Session
# ============================================================

session = requests.Session()

session.headers.update(
    {
        "User-Agent": (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/120.0 Safari/537.36"
        )
    }
)


# ============================================================
# 读取 sources.json
# ============================================================

def load_sources():
    if not os.path.exists(SOURCES_FILE):
        print("错误：找不到 sources.json")
        return []

    try:
        with open(
            SOURCES_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        if not isinstance(data, list):
            print("错误：sources.json 必须是数组 []")
            return []

        print(f"读取来源数量: {len(data)}")

        return data

    except json.JSONDecodeError as e:

        print("错误：sources.json JSON 格式错误")
        print(e)

        return []

    except Exception as e:

        print("读取 sources.json 失败")
        print(e)

        return []


# ============================================================
# 读取已经发布的数据
# ============================================================

def load_published():

    os.makedirs(
        "data",
        exist_ok=True
    )

    if not os.path.exists(PUBLISHED_FILE):
        return set()

    try:

        with open(
            PUBLISHED_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        if not isinstance(data, list):
            return set()

        return set(data)

    except Exception as e:

        print("读取 published.json 失败")
        print(e)

        return set()


# ============================================================
# 保存已经发布的数据
# ============================================================

def save_published(published):

    os.makedirs(
        "data",
        exist_ok=True
    )

    try:

        with open(
            PUBLISHED_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                list(published),
                f,
                ensure_ascii=False,
                indent=2
            )

    except Exception as e:

        print("保存 published.json 失败")
        print(e)


# ============================================================
# URL Hash
# ============================================================

def image_id(url):

    return hashlib.sha256(
        url.encode("utf-8")
    ).hexdigest()


# ============================================================
# 图片内容 Hash
# ============================================================

def image_content_id(data):

    return hashlib.sha256(
        data
    ).hexdigest()


# ============================================================
# 判断是否是应该排除的图片
# ============================================================
def is_excluded_url(url):

    url_lower = url.lower()

    for keyword in EXCLUDE_KEYWORDS:

        if keyword in url_lower:
            return True

    return False


# ============================================================
# 检查图片尺寸
# ============================================================

def is_valid_image(data):

    try:

        image = Image.open(
            BytesIO(data)
        )

        width, height = image.size

        print(
            f"图片尺寸: {width} x {height}"
        )

        if width < MIN_WIDTH:
            print("图片太小，跳过")
            return False

        if height < MIN_HEIGHT:
            print("图片太小，跳过")
            return False

        return True

    except Exception as e:

        print("无法读取图片")
        print(e)

        return False


# ============================================================
# 下载图片
# ============================================================

def download_image(url):

    try:

        print(
            f"下载图片: {url}"
        )

        response = session.get(
            url,
            timeout=REQUEST_TIMEOUT
        )

        response.raise_for_status()

        content_type = response.headers.get(
            "Content-Type",
            ""
        ).lower()

        if not content_type.startswith("image/"):

            print(
                f"不是图片: {content_type}"
            )

            return None

        data = response.content

        if len(data) > MAX_IMAGE_SIZE:

            print("图片超过 10MB，跳过")

            return None

        if not is_valid_image(data):

            return None

        return data

    except Exception as e:

        print(
            f"下载图片失败: {url}"
        )

        print(e)

        return None


# ============================================================
# 发送 Telegram 图片
# ============================================================

def send_photo(data):

    if not BOT_TOKEN:

        print(
            "错误：缺少 TELEGRAM_BOT_TOKEN"
        )

        return False

    if not CHANNEL_ID:

        print(
            "错误：缺少 TELEGRAM_CHANNEL_ID"
        )

        return False

    telegram_url = (
        "https://api.telegram.org/bot"
        + BOT_TOKEN
        + "/sendPhoto"
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
            telegram_url,
            data=payload,
            files=files,
            timeout=30
        )

        if response.ok:

            print(
                "Telegram 发送成功"
            )

            return True

        print(
            "Telegram 发送失败"
        )

        print(
            response.text
        )

        return False

    except Exception as e:

        print(
            "Telegram 请求失败"
        )

        print(e)

        return False


# ============================================================
# 网站图片采集
# ============================================================

def extract_website_images(page_url):

    print(
        f"正在访问网站: {page_url}"
    )

    try:

        response = session.get(
            page_url,
            timeout=REQUEST_TIMEOUT
        )

        response.raise_for_status()

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        result = []

        # ----------------------------------------------------
        # img 标签
        # ----------------------------------------------------

        for img in soup.find_all("img"):

            candidates = []

            src = img.get("src")

            if src:
                candidates.append(src)

            data_src = img.get(
                "data-src"
            )

            if data_src:
                candidates.append(data_src)

            data_original = img.get(
                "data-original"
            )

            if data_original:
                candidates.append(data_original
                )

            # srcset
            srcset = img.get("srcset")

            if srcset:

                for item in srcset.split(","):

                    item = item.strip()

                    if item:

                        candidates.append(
                            item.split()[0]
                        )

            for image_url in candidates:

                if not image_url:
                    continue

                if is_excluded_url(
                    image_url
                ):
                    continue

                image_url = urljoin(
                    page_url,
                    image_url
                )

                if image_url not in result:

                    result.append(
                        image_url
                    )

        # ----------------------------------------------------
        # og:image
        # ----------------------------------------------------

        og_image = soup.find(
            "meta",
            property="og:image"
        )

        if og_image:

            image_url = og_image.get(
                "content"
            )

            if image_url:

                image_url = urljoin(
                    page_url,
                    image_url
                )

                if not is_excluded_url(
                    image_url
                ):

                    if image_url not in result:

                        result.append(
                            image_url
                        )

        # ----------------------------------------------------
        # twitter:image
        # ----------------------------------------------------

        twitter_image = soup.find(
            "meta",
            attrs={
                "name": "twitter:image"
            }
        )

        if twitter_image:

            image_url = twitter_image.get(
                "content"
            )

            if image_url:

                image_url = urljoin(
                    page_url,
                    image_url
                )

                if not is_excluded_url(
                    image_url
                ):

                    if image_url not in result:

                        result.append(
                            image_url
                        )

        print(
            f"网站找到图片: {len(result)}"
        )

        return result

    except Exception as e:

        print(
            "网站采集失败"
        )

        print(e)

        return []


# ============================================================
# 普通 JSON 图片 API
# ============================================================

def extract_api_images(source):

    api_url = source.get(
        "url"
    )

    image_field = source.get(
        "image_field",
        "imageUrl"
    )

    method = source.get(
        "method",
        "GET"
    ).upper()

    if not api_url:

        print("API 没有配置 URL")

        return []

    print(
        f"正在请求 API: {api_url}"
    )

    try:

        if method == "POST":

            response = session.post(
                api_url,
                timeout=REQUEST_TIMEOUT
            )

        else:

            response = session.get(
                api_url,
                timeout=REQUEST_TIMEOUT
            )

        response.raise_for_status()

        data = response.json()

    except Exception as e:

        print(
            "API 请求失败"
        )

        print(e)

        return []

    result = []

    def walk(obj):

        if isinstance(
            obj,
            dict
        ):

            value = obj.get(
                image_field
            )

            if isinstance(
                value,
                str
            ):

                if value.startswith(
                    "http://"
                ) or value.startswith(
                    "https://"
                ):

                    if not is_excluded_url(
                        value
                    ):

                        result.append(value
                        )

            for value in obj.values():

                walk(value)

        elif isinstance(
            obj,
            list
        ):

            for item in obj:

                walk(item)

    walk(data)

    result = list(
        dict.fromkeys(result)
    )

    print(
        f"API 找到图片: {len(result)}"
    )

    return result


# ============================================================
# 处理图片
# ============================================================

def process_images(
    images,
    published,
    max_items
):

    total_sent = 0
    total_duplicate = 0
    total_failed = 0

    images = images[:max_items]

    for image_url in images:

        print("")
        print(
            f"准备处理: {image_url}"
        )

        # URL 去重
        url_hash = image_id(
            image_url
        )

        if url_hash in published:

            print(
                "URL 已经发布，跳过"
            )

            total_duplicate += 1

            continue

        # 下载
        image_data = download_image(
            image_url
        )

        if not image_data:

            total_failed += 1

            continue

        # 内容去重
        content_hash = image_content_id(
            image_data
        )

        if content_hash in published:

            print(
                "图片内容已经发布，跳过"
            )

            published.add(
                url_hash
            )

            total_duplicate += 1

            continue

        # Telegram
        success = send_photo(
            image_data
        )

        if success:

            published.add(
                url_hash
            )

            published.add(
                content_hash
            )

            total_sent += 1

        else:

            total_failed += 1

    return (
        total_sent,
        total_duplicate,
        total_failed
    )


# ============================================================
# 主程序
# ============================================================

def main():

    print("==============================")
    print("Telegram 图片采集器")
    print("==============================")

    # 检查 Token
    if not BOT_TOKEN:

        print(
            "错误：缺少 TELEGRAM_BOT_TOKEN"
        )

        return

    if not CHANNEL_ID:

        print(
            "错误：缺少 TELEGRAM_CHANNEL_ID"
        )

        return

    # 读取配置
    sources = load_sources()

    if not sources:

        print(
            "没有可用的数据来源"
        )

        return

    # 已发布
    published = load_published()

    total_found = 0
    total_sent = 0
    total_duplicate = 0
    total_failed = 0

    # --------------------------------------------------------
    # 遍历来源
    # --------------------------------------------------------

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
        print(
            f"来源: {name}"
        )
        print(
            f"类型: {source_type}"
        )
        print("------------------------------")

        # ----------------------------------------------------
        # 网站
        # ----------------------------------------------------

        if source_type == "website":

            page_url = source.get(
                "url"
            )

            if not page_url:

                print(
                    "网站没有配置 URL"
                )

                continue

            images = extract_website_images(
                page_url
            )

        # ----------------------------------------------------
        # 普通 API
        # ----------------------------------------------------

        elif source_type == "api":

            images = extract_api_images(
                source
            )
            # ----------------------------------------------------
        # 未知类型
        # ----------------------------------------------------

        else:

            print(
                f"未知来源类型: {source_type}"
            )

            continue

        total_found += len(
            images
        )

        sent, duplicate, failed = process_images(
            images,
            published,
            max_items
        )

        total_sent += sent
        total_duplicate += duplicate
        total_failed += failed

    # --------------------------------------------------------
    # 保存
    # --------------------------------------------------------

    save_published(
        published
    )

    # --------------------------------------------------------
    # 统计
    # --------------------------------------------------------

    print("")
    print("==============================")
    print("本次任务完成")
    print(
        f"发现图片: {total_found}"
    )
    print(
        f"成功发送: {total_sent}"
    )
    print(
        f"重复跳过: {total_duplicate}"
    )
    print(
        f"失败数量: {total_failed}"
    )
    print("==============================")


# ============================================================
# 程序入口
# ============================================================

if __name__ == "__main__":
    main()
