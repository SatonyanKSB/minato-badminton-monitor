from playwright.sync_api import sync_playwright

URL = "https://web101.rsv.ws-scs.jp/web/index.jsp"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    print("サイトを開いています...")
    page.goto(URL, wait_until="networkidle", timeout=60000)

    print("\n===== ページ情報 =====")
    print("タイトル:", page.title())
    print("URL:", page.url)

    print("\n===== セレクトボックス =====")
    selects = page.locator("select")
    print("個数:", selects.count())

    for i in range(selects.count()):
        select = selects.nth(i)
        print(f"\n--- select {i} ---")
        print("name:", select.get_attribute("name"))
        print("id:", select.get_attribute("id"))
        print("options:")
        for option in select.locator("option").all():
            print("  ", option.inner_text())

    print("\n===== ボタン・入力欄 =====")
    elements = page.locator("button, input")
    print("個数:", elements.count())

    for i in range(elements.count()):
        el = elements.nth(i)
        print(
            i,
            "tag=", el.evaluate("(e) => e.tagName"),
            "type=", el.get_attribute("type"),
            "name=", el.get_attribute("name"),
            "id=", el.get_attribute("id"),
            "value=", el.get_attribute("value"),
            "text=", el.inner_text()
        )

    page.screenshot(path="site.png", full_page=True)

    print("\n===== 調査完了 =====")

    browser.close()
