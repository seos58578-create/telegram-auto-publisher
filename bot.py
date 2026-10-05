def main():

    print("==============================")
    print("Telegram 图片采集器")

    sources = load_sources()
    published = load_published()

    for source in sources:

        source_type = source.get(
            "type",
            "website"
        )

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

        for image_url in images:

            url_id = image_id(
                image_url
            )

            if url_id in published:
                print("URL 已发布，跳过")
                continue

            image_data = download_image(
                image_url
            )

            if not image_data:
                continue

            if send_photo(image_data):
                published.add(url_id)

    save_published(published)


if __name__ == "__main__":
    main()
