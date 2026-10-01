from playwright.sync_api import sync_playwright
from pathlib import Path
import time


URL = "https://web101.rsv.ws-scs.jp/web/index.jsp"

DISTRICTS = [
    ("麻布地区", "1000_0"),
    ("赤坂地区", "2000_0"),
    ("芝地区", "5000_0"),
    ("高輪地区", "3000_0"),
    ("芝浦港南地区", "4000_0"),
]

PURPOSE = "2010_2010040"  # バドミントン


def get_all_results(page, district_name):
    """検索結果を「さらに表示」がなくなるまで取得する"""

    print(f"\n===== {district_name} =====")

    # 日付順に切り替える
    try:
        page.get_by_text("日付順", exact=True).click()
        page.wait_for_timeout(1500)
        print("日付順に切り替えました")
    except Exception as e:
        print(f"日付順への切り替えに失敗: {e}")

    # 最初の表示内容
    previous_text = ""
    click_count = 0

    # 「さらに表示」を最大50回まで押す
    for i in range(50):
        body_text = page.locator("body").inner_text()

        # 同じ内容なら終了
        if body_text == previous_text:
            print("画面内容に変化がないため終了します")
            break

        previous_text = body_text

        # 「さらに表示」を探す
        more = page.get_by_text("さらに表示", exact=True)

        try:
            count = more.count()
        except Exception:
            count = 0

        if count == 0:
            print("「さらに表示」はありません")
            break

        # 表示されている「さらに表示」を探す
        clicked = False

        for j in range(count):
            try:
                item = more.nth(j)

                if item.is_visible():
                    print(f"「さらに表示」をクリック ({click_count + 1}回目)")
                    item.click()
                    page.wait_for_timeout(1200)

                    click_count += 1
                    clicked = True
                    break

            except Exception:
                continue

        if not clicked:
            print("クリックできる「さらに表示」がありません")
            break

    print(f"「さらに表示」のクリック回数: {click_count}")

    # 最終的に表示されている全文を取得
    final_text = page.locator("body").inner_text()

    return final_text


with sync_playwright() as p:

    browser = p.chromium.launch(headless=True)

    page = browser.new_page(
        viewport={"width": 1280, "height": 1600}
    )

    all_results = []

    for district_name, district_value in DISTRICTS:

        print(f"\n\n######## {district_name} ########")

        try:
            # 公式サイトを開く
            page.goto(URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1500)

            # 期間：1か月
            page.locator("#days").evaluate(
                """(el) => {
                    el.value = '31';
                    el.dispatchEvent(
                        new Event('change', {bubbles: true})
                    );
                }"""
            )

            # 地区
            page.locator("#bname").evaluate(
                """(el, value) => {
                    el.value = value;
                    el.dispatchEvent(
                        new Event('change', {bubbles: true})
                    );
                }""",
                district_value
            )

            # バドミントン
            page.locator("#purpose").evaluate(
                """(el, value) => {
                    el.value = value;
                    el.dispatchEvent(
                        new Event('change', {bubbles: true})
                    );
                }""",
                PURPOSE
            )

            # 検索
            page.locator("#btn-go").click()

            page.wait_for_timeout(2500)

            # 「さらに表示」を全部処理
            result_text = get_all_results(
                page,
                district_name
            )

            # 画面全体のスクリーンショット
            screenshot_name = (
                f"result_{district_name.replace('地区', '')}.png"
            )

            page.screenshot(
                path=screenshot_name,
                full_page=True
            )

            # 地区ごとのテキスト保存
            text_name = (
                f"result_{district_name.replace('地区', '')}.txt"
            )

            Path(text_name).write_text(
                result_text,
                encoding="utf-8"
            )

            # 全地区まとめ
            all_results.append(
                f"\n\n==============================\n"
                f"{district_name}\n"
                f"==============================\n\n"
                f"{result_text}"
            )

            print(
                f"{district_name}: "
                f"{len(result_text)}文字取得"
            )

        except Exception as e:

            print(
                f"{district_name} の処理でエラー: {e}"
            )

            # エラー時もスクリーンショットを残す
            try:
                page.screenshot(
                    path=f"error_{district_name}.png",
                    full_page=True
                )
            except Exception:
                pass

    # 全地区まとめファイル
    Path("all-district-results.txt").write_text(
        "".join(all_results),
        encoding="utf-8"
    )

    print("\n==============================")
    print("5地区の検索が完了しました")
    print("==============================")

    browser.close()
