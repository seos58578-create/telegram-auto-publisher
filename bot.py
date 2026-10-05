import os
import json
import hashlib
from io import BytesIO
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from PIL import Image


# =========================
# 基础配置
# =========================

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")

SOURCES_FILE = "sources.json"
PUBLISHED_FILE = "data/published.json"

TIMEOUT = 30

# 最小图片尺寸
MIN_WIDTH = 300
MIN_HEIGHT = 200

# 最大图片大小 10MB
MAX_IMAGE_SIZE = 10 * 1024 * 1024

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0 Safari/537.36"
    )
}


# =========================
# 排除关键词
# =========================

EXCLUDE_KEYWORDS = [
    # Logo
    "logo",
    "site-logo",
    "header-logo",
    "footer-logo",

    # 图标
    "icon",
    "favicon",
    "sprite",

    # 导航
    "nav",
    "navbar",
    "navigation",
    "menu",
    "header",
    "footer",

    # 轮播
    "slider",
    "swiper",
    "carousel",
    "slideshow",

    # Banner
    "banner",
    "top-banner",
    "header-banner",

    # 按钮/箭头
    "button",
    "btn",
    "arrow",
    "prev",
    "next",

    # 加载图片
    "loading",
    "loader",
    "placeholder",

    # 用户头像
    "avatar",
    "profile"
]


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

    try:

        with open(
            SOURCES_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        if not isinstance(data, list):
            raise RuntimeError(
                "sources.json 必须是 JSON 数组"
            )

        return data

    except json.JSONDecodeError as e:

        raise RuntimeError(
            f"sources.json JSON 格式错误: {e}"
        )


# =========================
# 读取去重数据
# =========================

def load_published():

    os.makedirs(
        "data",
        exist_ok=True
    )

    if not os.path.exists(
        PUBLISHED_FILE
    ):
        return set()

    try:

        with open(
            PUBLISHED_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        if isinstance(data, list):
            return set(data)

    except Exception as e:

        print(
            f"读取去重文件失败: {e}"
        )

    return set()


# =========================
# 保存去重数据
# =========================

def save_published(published):

    os.makedirs(
        "data",
        exist_ok=True
    )

    with open(
        PUBLISHED_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            sorted(list(published)),
            f,
            ensure_ascii=False,
            indent=2
        )


# =========================
# URL 唯一 ID
# =========================

def image_id(url):

    return hashlib.sha256(
        url.encode("utf-8")
    ).hexdigest()


# =========================
# 图片内容唯一 ID
# =========================

def image_content_id(data):

    return hashlib.sha256(
        data
    ).hexdigest()


# =========================
# 判断关键词
# =========================

def contains_exclude_keyword(text):

    if not text:
        return False

    text = text.lower()

    for keyword in EXCLUDE_KEYWORDS:

        if keyword in text:
            return True

    return False


# =========================
# 判断 URL 是否图片
# =========================

def is_image_url(url):

    if not url:
        return False

    url_lower = url.lower()

    path = urlparse(
        url_lower
    ).path

    extensions = (
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".gif",
        ".bmp",
        ".avif"
    )

    return path.endswith(
        extensions
    )


# =========================
# 检查图片所在 HTML 区域
# =========================

def is_in_excluded_area(img):

    parent = img
# 向上检查 5 层
    for _ in range(5):

        if not parent:
            break

        tag_name = getattr(
            parent,
            "name",
            ""
        )

        if tag_name:

            classes = parent.get(
                "class",
                []
            )

            element_id = parent.get(
                "id",
                ""
            )

            class_text = " ".join(
                classes
            )

            area_text = (
                f"{tag_name} "
                f"{class_text} "
                f"{element_id}"
            )

            if contains_exclude_keyword(
                area_text
            ):

                return True

        parent = parent.parent

    return False


# =========================
# 获取图片
# =========================

def extract_images(page_url):

    print(
        f"正在访问网站: {page_url}"
    )

    try:

        response = requests.get(
            page_url,
            headers=HEADERS,
            timeout=TIMEOUT,
            verify=False
        )

        response.raise_for_status()

    except Exception as e:

        print(
            f"网站访问失败: {e}"
        )

        return []

    print(
        f"网页状态码: {response.status_code}"
    )

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    images = []

    # =========================
    # <img>
    # =========================

    for img in soup.find_all("img"):

        # -------------------------
        # 检查 HTML 区域
        # -------------------------

        if is_in_excluded_area(img):

            print(
                "跳过导航/轮播区域图片"
            )

            continue

        candidates = []

        # -------------------------
        # 常见图片属性
        # -------------------------

        for attr in [
            "src",
            "data-src",
            "data-original",
            "data-lazy-src",
            "data-url"
        ]:

            value = img.get(attr)

            if value:

                candidates.append(
                    value
                )

        # -------------------------
        # srcset
        # -------------------------

        srcset = img.get(
            "srcset"
        )

        if srcset:

            for item in srcset.split(","):

                item = item.strip()

                if item:

                    candidates.append(
                        item.split(" ")[0]
                    )

        # -------------------------
        # 处理 URL
        # -------------------------

        for src in candidates:

            if not src:
                continue

            src = src.strip()

            full_url = urljoin(
                page_url,
                src
            )

            if not full_url.startswith(
                "http"
            ):
                continue

            # URL关键词过滤
            if contains_exclude_keyword(
                full_url
            ):

                print(
                    f"关键词过滤: {full_url}"
                )

                continue

            # 文件类型过滤
            if not is_image_url(
                full_url
            ):

                continue

            images.append(
                full_url
            )

    # =========================
    # og:image
    # =========================

    for meta in soup.find_all(
        "meta",
        property="og:image"
    ):

        content = meta.get(
            "content"
        )

        if content:

            full_url = urljoin(
                page_url,
                content
            )

            # 不采集明显的 Logo / Banner
            if contains_exclude_keyword(
                full_url
            ):
                continue

            if is_image_url(
                full_url
            ):

                images.append(
                    full_url
                )

    # =========================
    # twitter:image
    # =========================

    for meta in soup.find_all(
        "meta",
        attrs={
            "name": "twitter:image"
}
    ):

        content = meta.get(
            "content"
        )

        if content:

            full_url = urljoin(
                page_url,
                content
            )

            if contains_exclude_keyword(
                full_url
            ):
                continue

            if is_image_url(
                full_url
            ):

                images.append(
                    full_url
                )

    # =========================
    # URL 去重
    # =========================

    unique = []

    seen = set()

    for url in images:

        if url in seen:
            continue

        seen.add(url)

        unique.append(
            url
        )

    print(
        f"过滤后图片数量: {len(unique)}"
    )

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

        if not content_type.startswith(
            "image/"
        ):

            print(
                f"跳过非图片: {url}"
            )

            return None

        data = response.content

        # -------------------------
        # 图片大小限制
        # -------------------------

        if len(data) > MAX_IMAGE_SIZE:

            print(
                f"跳过过大图片: {len(data)} bytes"
            )

            return None

        # -------------------------
        # 检查实际图片尺寸
        # -------------------------

        try:

            image = Image.open(
                BytesIO(data)
            )

            width, height = image.size

            print(
                f"图片尺寸: {width}x{height}"
            )

            if (
                width < MIN_WIDTH
                or
                height < MIN_HEIGHT
            ):

                print(
                    "跳过小尺寸图片"
                )

                return None

        except Exception as e:

            print(
                f"无法读取图片尺寸: {e}"
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
# Telegram
# =========================

def send_photo(image_data):

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

    # 不再显示来源
    data = {
        "chat_id": CHANNEL_ID
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

            print(
                "Telegram 发送成功"
            )

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

    print(
        "=============================="
    )

    print(
        "Telegram 网站图片采集器"
    )

    print(
        "=============================="
    )

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

        page_url = source.get(
            "url"
        )

        max_items = int(
            source.get(
                "max_items",
                10
            )
        )

        print("")

        print(
            "------------------------------"
        )

        print(
            f"网站: {name}"
        )

        print(
            f"URL: {page_url}"
        )

        print(
            "------------------------------"
        )

        if not page_url:

            print(
                "没有配置 URL"
            )

            continue

        # =========================
        # 获取图片
        # =========================

        images = extract_images(
            page_url
        )

        total_found += len(
            images
        )

        # 最多处理 max_items 张
        images = images[:max_items]

        # =========================
        # 逐张处理
        # =========================

        for image_url in images:

            url_id = image_id(
                image_url
            )

            # -------------------------
            # URL 去重
            # -------------------------

            if url_id in published:

                print(
                    f"跳过重复图片: {image_url}"
                )

                total_duplicate += 1

                continue

            print("")

            print(
                f"准备处理图片: {image_url}"
            )

            # -------------------------
            # 下载图片
            # -------------------------

            image_data = download_image(
                image_url
            )

            if not image_data:

                total_failed += 1

                continue

            # -------------------------
            # 图片内容去重
            # -------------------------

            content_id = image_content_id(
                image_data
            )

            if content_id in published:

                print(
                    "图片内容已经发布过，跳过"
                )

                # 保存 URL，避免下次再次检查
                published.add(
                    url_id
                )

                total_duplicate += 1

                continue

            # -------------------------
            # 发送 Telegram
            # -------------------------

            success = send_photo(
                image_data
            )

            if success:

                # 保存 URL ID
                published.add(
                    url_id
                )

                # 保存图片内容 ID
                published.add(
                    content_id
                )

                total_sent += 1

            else:

                total_failed += 1

    # =========================
    # 保存去重数据
    # =========================

    save_published(
        published
    )

    print("")

    print(
        "=============================="
    )

    print(
        "本次任务完成"
    )

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

    print(
        "=============================="
    )


if __name__ == "__main__":
    main()
