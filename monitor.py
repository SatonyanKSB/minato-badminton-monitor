from playwright.sync_api import sync_playwright

URL = "https://web101.rsv.ws-scs.jp/web/index.jsp"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 900})

    print("サイトを開いています...")
    page.goto(URL, wait_until="networkidle", timeout=60000)

    # 初期画面
    page.screenshot(path="01_initial.png", full_page=True)

    lines = []

    lines.append("===== PAGE =====")
    lines.append(f"TITLE: {page.title()}")
    lines.append(f"URL: {page.url}")
    lines.append("")

    lines.append("===== SELECTS =====")

    selects = page.locator("select")
    lines.append(f"SELECT COUNT: {selects.count()}")

    for i in range(selects.count()):
        select = selects.nth(i)

        lines.append("")
        lines.append(f"--- SELECT {i} ---")
        lines.append(f"name={select.get_attribute('name')}")
        lines.append(f"id={select.get_attribute('id')}")

        options = select.locator("option")

        for j in range(options.count()):
            option = options.nth(j)

            lines.append(
                f"OPTION {j}: "
                f"value={option.get_attribute('value')} "
                f"text={option.inner_text().strip()}"
            )

    lines.append("")
    lines.append("===== BUTTONS / INPUTS =====")

    elements = page.locator("button, input")

    lines.append(f"ELEMENT COUNT: {elements.count()}")

    for i in range(elements.count()):
        el = elements.nth(i)

        try:
            text = el.inner_text().strip()
        except:
            text = ""

        lines.append(
            f"ELEMENT {i}: "
            f"tag={el.evaluate('(e) => e.tagName')} "
            f"type={el.get_attribute('type')} "
            f"name={el.get_attribute('name')} "
            f"id={el.get_attribute('id')} "
            f"value={el.get_attribute('value')} "
            f"text={text}"
        )

    # 「1か月」をクリックできるか確認
    lines.append("")
    lines.append("===== 1 MONTH TEST =====")

    one_month = page.get_by_text("1か月", exact=True)

    lines.append(f"1か月 elements: {one_month.count()}")

    if one_month.count() > 0:
        one_month.first.click()
        page.wait_for_timeout(1000)
        lines.append("1か月: CLICKED")
        page.screenshot(path="02_one_month.png", full_page=True)
    else:
        lines.append("1か月: NOT FOUND")

    # 調査結果をファイルに保存
    with open("diagnostics.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print("\n".join(lines))

    browser.close()
