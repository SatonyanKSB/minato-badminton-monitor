from playwright.sync_api import sync_playwright

URL = "https://web101.rsv.ws-scs.jp/web/index.jsp"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 900})

    print("サイトを開いています...")
    page.goto(URL, wait_until="networkidle", timeout=60000)

    print("サイトを開きました")

    # 1か月
    # #days は画面上では非表示のため、JavaScriptで値を変更して
    # changeイベントを発生させる
    page.locator("#days").evaluate("""
        (e) => {
            e.value = "31";
            e.dispatchEvent(new Event("change", { bubbles: true }));
        }
    """)

    page.wait_for_timeout(1000)

    # 芝地区（すべて）
    page.locator("#bname").select_option("5000_0")

    page.wait_for_timeout(1000)

    # バドミントン
    page.locator("#purpose").select_option("2010_2010040")

    page.wait_for_timeout(1000)

    print("")
    print("===== 検索条件 =====")
    print("期間：1か月")
    print("地区：芝地区（すべて）")
    print("目的：バドミントン")
    print("時間帯：指定なし")

    # 検索
    print("")
    print("検索ボタンを押します...")

    page.locator("#btn-go").click()

    # 検索結果を待つ
    page.wait_for_timeout(5000)

    try:
        page.wait_for_load_state("networkidle", timeout=30000)
    except:
        pass

    print("")
    print("===== SEARCH RESULT =====")
    print("TITLE:", page.title())
    print("URL:", page.url)

    # スクリーンショット
    page.screenshot(
        path="search-result.png",
        full_page=True
    )

    # HTML
    with open("search-result.html", "w", encoding="utf-8") as f:
        f.write(page.content())

    # 表示文字
    text = page.locator("body").inner_text()

    with open("search-result.txt", "w", encoding="utf-8") as f:
        f.write(text)

    print("")
    print("===== 画面に表示された文字 =====")
    print(text[:30000])

    print("")
    print("===== 予約 =====")

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
