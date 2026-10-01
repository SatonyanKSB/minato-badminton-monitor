from playwright.sync_api import sync_playwright
from pathlib import Path
import re
import json


URL = "https://web101.rsv.ws-scs.jp/web/index.jsp"

DISTRICTS = [
    ("麻布地区", "1000_0"),
    ("赤坂地区", "2000_0"),
    ("芝地区", "5000_0"),
    ("高輪地区", "3000_0"),
    ("芝浦港南地区", "4000_0"),
]

PURPOSE = "2010_2010040"  # バドミントン

STATE_FILE = Path("state.json")


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
    検索結果から、
    開始時刻が17:00以降の枠だけを抽出する。
    """

    results = []

    current_date = ""
    last_nonempty_line = ""

    lines = text.splitlines()

    for line in lines:

        line = line.strip()

        if not line:
            continue

        # 日付
        date_match = re.search(
            r"(\d{1,2}月\d{1,2}日\([^)]*\)\d{4}年)",
            line
        )

        if date_match:
            current_date = date_match.group(1)

        # 時間帯
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

            start_total = (
                start_hour * 60
                + start_minute
            )

            # 開始時刻17:00以降
            if start_total >= 17 * 60:

                results.append(
                    {
                        "district": district_name,
                        "date": current_date,
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


def make_slot_key(slot):
    """
    空き枠を一意に識別するためのキーを作る。
    """

    return (
        f"{slot['district']}|"
        f"{slot['date']}|"
        f"{slot['start']}|"
        f"{slot['end']}"
    )


def load_previous_state():
    """前回の状態を読み込む"""

    if not STATE_FILE.exists():

        print("前回のstate.jsonはありません")

        return set()

    try:

        data = json.loads(
            STATE_FILE.read_text(
                encoding="utf-8"
            )
        )

        return set(data)

    except Exception as e:

        print(
            f"state.jsonの読み込みに失敗: {e}"
        )

        return set()


def save_current_state(slots):
    """今回の空き枠をstate.jsonに保存する"""

    keys = [
        make_slot_key(slot)
        for slot in slots
    ]

    STATE_FILE.write_text(
        json.dumps(
            keys,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )


def format_slot(slot):
    """空き枠を読みやすい文章にする"""

    return (
        f"地区：{slot['district']}\n"
        f"日付：{slot['date']}\n"
        f"時間：{slot['start']}～{slot['end']}\n"
    )


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

    current_evening_slots = []

    # --------------------------------
    # 前回の状態を読み込む
    # --------------------------------

    previous_keys = load_previous_state()

    first_run = not STATE_FILE.exists()

    print("\n==============================")
    print("前回状態")
    print(
        f"{len(previous_keys)}件"
    )
    print("==============================")

    # --------------------------------
    # 5地区を検索
    # --------------------------------

    for district_name, district_value in DISTRICTS:

        print(
            f"\n\n######## "
            f"{district_name} "
            f"########"
        )

        try:

            page.goto(
                URL,
                wait_until="domcontentloaded",
                timeout=60000
            )

            page.wait_for_timeout(1500)

            # 1か月
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

            # 全件取得
            result_text = get_all_results(
                page,
                district_name
            )

            all_results.append(
                f"\n\n"
                f"==============================\n"
                f"{district_name}\n"
                f"==============================\n\n"
                f"{result_text}"
            )

            # 17時以降抽出
            district_slots = extract_evening_slots(
                result_text,
                district_name
            )

            current_evening_slots.extend(
                district_slots
            )

            print(
                f"{district_name}: "
                f"17:00以降 "
                f"{len(district_slots)}件"
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

    # --------------------------------
    # 今回の全検索結果
    # --------------------------------

    Path(
        "all-district-results.txt"
    ).write_text(
        "".join(all_results),
        encoding="utf-8"
    )

    # --------------------------------
    # 今回の17時以降枠
    # --------------------------------

    current_keys = {
        make_slot_key(slot)
        for slot in current_evening_slots
    }

    # --------------------------------
    # 新しく出現した枠を判定
    # --------------------------------

    new_keys = current_keys - previous_keys

    # キーから実データを探す
    new_slots = []

    for slot in current_evening_slots:

        if make_slot_key(slot) in new_keys:

            new_slots.append(slot)

    # --------------------------------
    # 結果を保存
    # --------------------------------

    evening_lines = []

    evening_lines.append(
        "========================================\n"
    )

    evening_lines.append(
        "今回の17:00以降開始 空き枠\n"
    )

    evening_lines.append(
        "========================================\n\n"
    )

    if current_evening_slots:

        for slot in current_evening_slots:

            evening_lines.append(
                format_slot(slot)
            )

            evening_lines.append(
                "----------------------------------------\n"
            )

    else:

        evening_lines.append(
            "現在、17:00以降開始の空き枠はありません。\n"
        )

    Path(
        "evening-results.txt"
    ).write_text(
        "".join(evening_lines),
        encoding="utf-8"
    )

    # --------------------------------
    # 新規枠だけ保存
    # --------------------------------

    new_lines = []

    new_lines.append(
        "========================================\n"
    )

    new_lines.append(
        "新しく出現した17:00以降開始の空き枠\n"
    )

    new_lines.append(
        "========================================\n\n"
    )

    if first_run:

        new_lines.append(
            "【初回実行】\n"
        )

        new_lines.append(
            "今回は基準値として保存します。\n"
        )

        new_lines.append(
            "初回の空き枠は新規通知対象にしません。\n"
        )

    elif new_slots:

        new_lines.append(
            f"{len(new_slots)}件の新しい空き枠があります。\n\n"
        )

        for slot in new_slots:

            new_lines.append(
                format_slot(slot)
            )

            new_lines.append(
                "----------------------------------------\n"
            )

    else:

        new_lines.append(
            "新しく出現した空き枠はありません。\n"
        )

    Path(
        "new-slots.txt"
    ).write_text(
        "".join(new_lines),
        encoding="utf-8"
    )

    # --------------------------------
    # 今回の状態を保存
    # --------------------------------

    save_current_state(
        current_evening_slots
    )

    # --------------------------------
    # コンソール表示
    # --------------------------------

    print("\n================================")
    print("検索完了")
    print("================================")

    print(
        f"今回の17:00以降枠: "
        f"{len(current_evening_slots)}件"
    )

    if first_run:

        print(
            "初回実行なので、"
            "新規枠は通知対象にしません"
        )

    else:

        print(
            f"新しく出現した枠: "
            f"{len(new_slots)}件"
        )

        for slot in new_slots:

            print(
                "\n--- 新規空き ---"
            )

            print(
                format_slot(slot)
            )

    print("\nstate.jsonを更新しました")

    browser.close()
