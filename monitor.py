from playwright.sync_api import sync_playwright

URL = "https://web101.rsv.ws-scs.jp/web/index.jsp"

# 港区の5地区
DISTRICTS = [
    ("麻布地区", "1000_0"),
    ("赤坂地区", "2000_0"),
    ("芝地区", "5000_0"),
    ("高輪地区", "3000_0"),
    ("芝浦港南地区", "4000_0"),
]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 900})

    all_results = []

    for district_name, district_value in DISTRICTS:

        print("")
        print("========================================")
        print("検索開始:", district_name)
        print("========================================")

        # 毎回検索画面から開始
        page.goto(URL, wait_until="networkidle", timeout=60000)

        # ----------------------------------------
        # 検索条件
        # ----------------------------------------

        # 1か月
        page.locator("#days").evaluate(
            """
            (el) => {
                el.value = "31";
                el.dispatchEvent(
                    new Event("change", {bubbles: true})
                );
            }
            """
        )

        # 地区
        page.locator("#bname").evaluate(
            """
            (el, value) => {
                el.value = value;
                el.dispatchEvent(
                    new Event("change", {bubbles: true})
                );
            }
            """,
            district_value
        )

        page.wait_for_timeout(500)

        # バドミントン
        page.locator("#purpose").evaluate(
            """
            (el) => {
                el.value = "2010_2010040";
                el.dispatchEvent(
                    new Event("change", {bubbles: true})
                );
            }
            """
        )

        page.wait_for_timeout(500)

        print("期間：1か月")
        print("地区:", district_name)
        print("目的：バドミントン")
        print("時間帯：指定なし")

        # ----------------------------------------
        # 検索
        # ----------------------------------------

        page.locator("#btn-go").click()

        page.wait_for_timeout(5000)

        try:
            page.wait_for_load_state(
                "networkidle",
                timeout=30000
            )
        except:
            pass

        # ----------------------------------------
        # 日付順
        # ----------------------------------------

        try:
            page.get_by_text(
                "日付順",
                exact=True
            ).click()

            page.wait_for_timeout(3000)

            try:
                page.wait_for_load_state(
                    "networkidle",
                    timeout=30000
                )
            except:
                pass

        except Exception as e:
            print("日付順への切り替えに失敗:", e)

        # ----------------------------------------
        # 結果取得
        # ----------------------------------------

        text = page.locator("body").inner_text()

        all_results.append(
            "\n"
            + "========================================\n"
            + district_name
            + "\n"
            + "========================================\n"
            + text
        )

        print("")
        print("===== ", district_name, "の検索結果 =====")
        print(text[:10000])

        # ----------------------------------------
        # 地区ごとのスクリーンショット
        # ----------------------------------------

        safe_name = district_name.replace("地区", "")

        page.screenshot(
            path=f"result_{safe_name}.png",
            full_page=True
        )

        # 次の地区へ行く前に少し待つ
        page.wait_for_timeout(1000)

    # ==================================================
    # 5地区分の結果をまとめて保存
    # ==================================================

    combined_text = "\n".join(all_results)

    with open(
        "all-district-results.txt",
        "w",
        encoding="utf-8"
    ) as f:
        f.write(combined_text)

    print("")
    print("========================================")
    print("5地区の検索がすべて完了しました")
    print("========================================")

    browser.close()
