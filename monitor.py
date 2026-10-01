from playwright.sync_api import sync_playwright
from pathlib import Path
import re


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
    """「さらに表示」がなくなるまで検索結果を取得する"""

    print(f"\n===== {district_name} =====")

    # 日付順に切り替える
    try:
        page.get_by_text("日付順", exact=True).click()
        page.wait_for_timeout(1500)
        print("日付順に切り替えました")
    except Exception as e:
        print(f"日付順への切り替えに失敗: {e}")

    previous_text = ""
    click_count = 0

    # 「さらに表示」を最大50回まで押す
    for i in range(50):

        body_text = page.locator("body").inner_text()

        if body_text == previous_text:
            print("画面内容に変化がないため終了します")
            break

        previous_text = body_text

        more = page.get_by_text("さらに表示", exact=True)

        try:
            count = more.count()
        except Exception:
            count = 0

        if count == 0:
            print("「さらに表示」はありません")
            break

        clicked = False

        for j in range(count):
            try:
                item = more.nth(j)

                if item.is_visible():
                    print(
                        f"「さらに表示」をクリック "
                        f"({click_count + 1}回目)"
                    )

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

    print(
        f"「さらに表示」のクリック回数: "
        f"{click_count}"
    )

    return page.locator("body").inner_text()


def extract_evening_slots(text, district_name):
    """
    検索結果から、開始時刻が17:00以降の枠だけを抽出する。
    """

    results = []

    current_date = ""
    last_nonempty_line = ""

    lines = text.splitlines()

    for line in lines:

        line = line.strip()

        if not line:
            continue

        # 日付を取得
        date_match = re.search(
            r"(\d{1,2}月\d{1,2}日\([^)]*\)\d{4}年)",
            line
        )

        if date_match:
            current_date = date_match.group(1)

        # 時間帯を取得
        time_match = re.search(
            r"(\d{1,2})時(\d{2})分"
            r"[～~\-]"
            r"(\d{1,2})時(\d{2})分",
            line
        )

        if time_match:

            start_hour = int(time_match.group(1))
            start_minute = int(time_match.group(2))

            end_hour = int(time_match.group(3))
            end_minute = int(time_match.group(4))

            # 開始時刻を分に変換
            start_total = (
                start_hour * 60
                + start_minute
            )

            # 17:00 = 1020分
            if start_total >= 17 * 60:

                # 時間の直前に出ている
                # 「館 + 施設」の行を取得
                facility_line = last_nonempty_line

                # ヘッダー等を除外
                if facility_line in [
                    "館 施設 時間帯 予約",
                    "館\t施設\t時間帯\t予約",
                    "予約",
                ]:
                    facility_line = ""

                results.append(
                    {
                        "district": district_name,
                        "date": current_date,
                        "facility": facility_line,
                        "start": (
                            f"{start_hour:02d}:"
                            f"{start_minute:02d}"
                        ),
                        "end": (
                            f"{end_hour:02d}:"
                            f"{end_minute:02d}"
                        ),
                    }
                )

        last_nonempty_line = line

    return results


with sync_playwright() as p:

    browser = p.chromium.launch(
        headless=True
    )

    page = browser.new_page(
        viewport={
            "width": 1280,
            "height": 1600
        }
    )

    all_results = []
    evening_results = []

    for district_name, district_value in DISTRICTS:

        print(
            f"\n\n######## "
            f"{district_name} "
            f"########"
        )

        try:

            # 公式サイト
            page.goto(
                URL,
                wait_until="domcontentloaded",
                timeout=60000
            )

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

            # すべての検索結果を取得
            result_text = get_all_results(
                page,
                district_name
            )

            # 全検索結果を保存
            all_results.append(
                f"\n\n"
                f"==============================\n"
                f"{district_name}\n"
                f"==============================\n\n"
                f"{result_text}"
            )

            # 17:00以降だけ抽出
            district_evening = extract_evening_slots(
                result_text,
                district_name
            )

            evening_results.extend(
                district_evening
            )

            print(
                f"{district_name}: "
                f"17:00以降の枠 "
                f"{len(district_evening)}件"
            )

            # スクリーンショット
            screenshot_name = (
                "result_"
                + district_name.replace("地区", "")
                + ".png"
            )

            page.screenshot(
                path=screenshot_name,
                full_page=True
            )

        except Exception as e:

            print(
                f"{district_name} の処理でエラー: "
                f"{e}"
            )

            try:
                page.screenshot(
                    path=(
                        "error_"
                        + district_name
                        + ".png"
                    ),
                    full_page=True
                )
            except Exception:
                pass

    # ---------------------------------
    # 全検索結果
    # ---------------------------------

    Path(
        "all-district-results.txt"
    ).write_text(
        "".join(all_results),
        encoding="utf-8"
    )

    # ---------------------------------
    # 17:00以降の結果
    # ---------------------------------

    evening_lines = []

    evening_lines.append(
        "========================================\n"
    )

    evening_lines.append(
        "17:00以降開始の空き枠\n"
    )

    evening_lines.append(
        "========================================\n\n"
    )

    if not evening_results:

        evening_lines.append(
            "現在、17:00以降開始の空き枠は "
            "見つかりませんでした。\n"
        )

    else:

        for item in evening_results:

            evening_lines.append(
                f"地区: {item['district']}\n"
            )

            evening_lines.append(
                f"日付: {item['date']}\n"
            )

            evening_lines.append(
                f"施設: {item['facility']}\n"
            )

            evening_lines.append(
                f"時間: "
                f"{item['start']}"
                f"～"
                f"{item['end']}\n"
            )

            evening_lines.append(
                "----------------------------------------\n"
            )

    Path(
        "evening-results.txt"
    ).write_text(
        "".join(evening_lines),
        encoding="utf-8"
    )

    print("\n================================")
    print("5地区の検索が完了しました")
    print(
        "17:00以降開始の枠: "
        f"{len(evening_results)}件"
    )
    print("================================")

    browser.close()
