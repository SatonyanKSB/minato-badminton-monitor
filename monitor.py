from playwright.sync_api import sync_playwright

URL = "https://web101.rsv.ws-scs.jp/web/index.jsp"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 900})

    print("サイトを開いています...")
    page.goto(URL, wait_until="networkidle", timeout=60000)

    # 1か月
    page.locator("#days").select_option("31")

    # 芝地区（すべて）
    page.locator("#bname").select_option("5000_0")

    # バドミントン
    page.locator("#purpose").select_option("2010_2010040")

    # 時間帯は選択しない
    # → 全時間帯を検索

    print("検索条件を設定しました")
    print("地区：芝地区（すべて）")
    print("目的：バドミントン")
    print("期間：1か月")
    print("時間帯：指定なし")

    # 検索
    page.locator("#btn-go").click()

    # 検索結果の読み込みを待つ
    page.wait_for_timeout(5000)

    try:
        page.wait_for_load_state("networkidle", timeout=30000)
    except:
        pass

    print("")
    print("===== SEARCH RESULT =====")
    print("TITLE:", page.title())
    print("URL:", page.url)

    # 画面全体を保存
    page.screenshot(
        path="search-result.png",
        full_page=True
    )

    # HTMLを保存
    with open("search-result.html", "w", encoding="utf-8") as f:
        f.write(page.content())

    # 画面に表示されている文字を取得
    text = page.locator("body").inner_text()

    with open("search-result.txt", "w", encoding="utf-8") as f:
        f.write(text)

    print("")
    print("===== 画面に表示された文字 =====")
    print(text[:20000])

    print("")
    print("===== 予約という文字を含む要素 =====")

    elements = page.get_by_text("予約", exact=True)

    print("予約要素数:", elements.count())

    for i in range(elements.count()):
        el = elements.nth(i)

        try:
            print(
                i,
                "tag=", el.evaluate("(e) => e.tagName"),
                "text=", el.inner_text(),
                "href=", el.get_attribute("href"),
                "id=", el.get_attribute("id"),
                "class=", el.get_attribute("class"),
            )
        except Exception as e:
            print(i, "取得失敗:", e)

    print("")
    print("===== TEST COMPLETE =====")

    browser.close()
