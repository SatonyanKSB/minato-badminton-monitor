from playwright.sync_api import sync_playwright

URL = "https://web101.rsv.ws-scs.jp/web/index.jsp"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 900})

    print("サイトを開いています...")
    page.goto(URL, wait_until="networkidle", timeout=60000)

    page.screenshot(path="site.png", full_page=True)

    print("")
    print("===== SELECT一覧 =====")

    selects = page.locator("select")
    count = selects.count()

    print("select総数:", count)

    for i in range(count):
        el = selects.nth(i)

        try:
            info = el.evaluate("""
                e => ({
                    id: e.id,
                    name: e.getAttribute('name'),
                    className: e.className,
                    visible: !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length),
                    disabled: e.disabled,
                    value: e.value,
                    options: Array.from(e.options).map(o => ({
                        text: o.text,
                        value: o.value
                    }))
                })
            """)

            print("")
            print("----- SELECT", i, "-----")
            print("id:", info["id"])
            print("name:", info["name"])
            print("class:", info["className"])
            print("visible:", info["visible"])
            print("disabled:", info["disabled"])
            print("value:", info["value"])

            print("options:")
            for option in info["options"][:30]:
                print(
                    "  ",
                    repr(option["text"]),
                    "=>",
                    repr(option["value"])
                )

        except Exception as e:
            print("SELECT", i, "取得失敗:", e)

    print("")
    print("===== INPUT / BUTTON一覧 =====")

    elements = page.locator("input, button")

    for i in range(elements.count()):
        el = elements.nth(i)

        try:
            info = el.evaluate("""
                e => ({
                    tag: e.tagName,
                    type: e.getAttribute('type'),
                    id: e.id,
                    name: e.getAttribute('name'),
                    value: e.getAttribute('value'),
                    text: e.innerText,
                    className: e.className,
                    visible: !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length)
                })
            """)

            print(
                i,
                info
            )

        except Exception as e:
            print(i, "取得失敗:", e)

    print("")
    print("===== TEST COMPLETE =====")

    with open("diagnostics.txt", "w", encoding="utf-8") as f:
        f.write("SELECT総数: " + str(count) + "\n\n")

        for i in range(count):
            el = selects.nth(i)

            try:
                info = el.evaluate("""
                    e => ({
                        id: e.id,
                        name: e.getAttribute('name'),
                        className: e.className,
                        visible: !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length),
                        disabled: e.disabled,
                        value: e.value,
                        options: Array.from(e.options).map(o => ({
                            text: o.text,
                            value: o.value
                        }))
                    })
                """)

                f.write("===== SELECT " + str(i) + " =====\n")
                f.write(str(info) + "\n\n")

            except Exception as e:
                f.write("SELECT " + str(i) + " ERROR: " + str(e) + "\n")

    browser.close()
