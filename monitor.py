from playwright.sync_api import sync_playwright

URL = "https://web101.rsv.ws-scs.jp/web/index.jsp"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 900})

    print("サイトを開いています...")
    page.goto(URL, wait_until="networkidle", timeout=60000)

    # ==================================================
    # 検索条件を設定
    # ==================================================

    # 1か月
    page.locator("#days").evaluate("""
        (el) => {
            el.value = "31";
            el.dispatchEvent(new Event("change", {bubbles: true}));
        }
    """)

    # 芝地区（すべて）
    page.locator("#bname").evaluate("""
        (el) => {
            el.value = "5000_0";
            el.dispatchEvent(new Event("change", {bubbles: true}));
        }
    """)

    # バドミントン
    page.locator("#purpose").evaluate("""
        (el) => {
            el.value = "2010_2010040";
            el.dispatchEvent(new Event("change", {bubbles: true}));
        }
    """)

    print("検索条件を設定しました")
    print("地区：芝地区（すべて）")
    print("目的：バドミントン")
    print("期間：1か月")
    print("時間帯：指定なし")

    # ==================================================
    # 検索
    # ==================================================

    print("検索を実行します...")

    page.locator("#btn-go").click()

    page.wait_for_timeout(5000)

    try:
        page.wait_for_load_state("networkidle", timeout=30000)
    except:
        pass

    print("検索結果が表示されました")

    # ==================================================
    # 日付順へ切り替える
    # ==================================================

    print("日付順へ切り替えています...")

    try:
        page.get_by_text("日付順", exact=True).click()
    except Exception as e:
        print("通常クリックに失敗しました。JavaScriptで試します...")
        print(e)

        page.evaluate("""
            () => {
                const elements = Array.from(document.querySelectorAll("*"));
                const target = elements.find(
                    el => el.textContent.trim() === "日付順"
                );

                if (target) {
                    target.click();
                }
            }
        """)

    page.wait_for_timeout(5000)

    try:
        page.wait_for_load_state("networkidle", timeout=30000)
    except:
        pass

    print("日付順への切り替えが完了しました")

    # ==================================================
    # 検索結果を保存
    # ==================================================

    print("検索結果を保存します...")

    # スクリーンショット
    page.screenshot(
        path="search-result.png",
        full_page=True
    )

    # HTML
    with open("search-result.html", "w", encoding="utf-8") as f:
        f.write(page.content())

    # 画面に表示されている文字
    text = page.locator("body").inner_text()

    with open("search-result.txt", "w", encoding="utf-8") as f:
        f.write(text)

    # ==================================================
    # ログ出力
    # ==================================================

    print("")
    print("========================================")
    print("SEARCH RESULT")
    print("========================================")

    print("TITLE:", page.title())
    print("URL:", page.url)

    print("")
    print("========================================")
    print("画面に表示された文字")
    print("========================================")

    print(text[:30000])

    # ==================================================
    # 「予約」ボタンを調査
    # ==================================================

    print("")
    print("========================================")
    print("予約という文字を含む要素")
    print("========================================")

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
    print("========================================")
    print("TEST COMPLETE")
    print("========================================")

    browser.close()
