import os
import json
import re
import time
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


URL = "https://web101.rsv.ws-scs.jp/web/index.jsp"

DISTRICTS = [
    "麻布地区（すべて）",
    "赤坂地区（すべて）",
    "芝地区（すべて）",
    "高輪地区（すべて）",
    "芝浦港南地区（すべて）",
]

STATE_FILE = "state.json"
EVENING_FILE = "evening-results.txt"
NEW_FILE = "new-slots.txt"


def load_state():
    if not os.path.exists(STATE_FILE):
        return set()

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            return set(data)

        return set()
    except Exception as e:
        print(f"state.json読み込みエラー: {e}")
        return set()


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(state), f, ensure_ascii=False, indent=2)


def extract_start_time(time_text):
    """
    17:00～19:00 のような文字列から開始時刻を取得する。
    """
    m = re.search(r"(\d{1,2}):(\d{2})\s*[～~\-−]\s*(\d{1,2}):(\d{2})", time_text)

    if not m:
        return None

    return int(m.group(1)), int(m.group(2))


def is_after_17(time_text):
    result = extract_start_time(time_text)

    if not result:
        return False

    hour, minute = result
    return (hour, minute) >= (17, 0)


def send_ntfy(message):
    topic = os.environ.get("NTFY_TOPIC")

    if not topic:
        print("NTFY_TOPICが設定されていないため通知をスキップします。")
        return False

    url = f"https://ntfy.sh/{topic}"

    payload = message.encode("utf-8")

    req = Request(
        url,
        data=payload,
        headers={
            "Content-Type": "text/plain; charset=utf-8",
            "Title": "🏸 港区バドミントン空き枠",
            "Priority": "high",
            "Tags": "badminton",
            "User-Agent": "Minato-Badminton-Monitor",
        },
        method="POST",
    )

    try:
        with urlopen(req, timeout=20) as response:
            print(f"ntfy送信成功: HTTP {response.status}")
            return 200 <= response.status < 300

    except HTTPError as e:
        print(f"ntfy送信エラー: HTTP {e.code}")

        try:
            body = e.read().decode("utf-8", errors="replace")
            print(f"ntfyのエラー本文: {body}")
        except Exception as body_error:
            print(f"ntfyのエラー本文を取得できませんでした: {body_error}")

        return False

    except Exception as e:
        print(f"ntfy送信エラー: {e}")
        return False


def select_district(page, district):
    """
    地区を選択する。
    """

    selects = page.locator("select")

    for i in range(selects.count()):
        select = selects.nth(i)

        try:
            options = select.locator("option")
            option_count = options.count()

            for j in range(option_count):
                option = options.nth(j)

                try:
                    text = option.inner_text().strip()

                    if text == district:
                        value = option.get_attribute("value")

                        if value:
                            select.select_option(value=value)
                        else:
                            select.select_option(label=district)

                        print(f"地区選択: {district}")
                        return True

                except Exception:
                    pass

        except Exception:
            pass

    return False


def select_badminton(page):
    """
    「バドミントン」を選択する。
    """

    selects = page.locator("select")

    for i in range(selects.count()):
        select = selects.nth(i)

        try:
            options = select.locator("option")
            option_count = options.count()

            for j in range(option_count):
                option = options.nth(j)

                try:
                    text = option.inner_text().strip()

                    if text == "バドミントン":
                        value = option.get_attribute("value")

                        if value:
                            select.select_option(value=value)
                        else:
                            select.select_option(label="バドミントン")

                        print("活動選択: バドミントン")
                        return True

                except Exception:
                    pass

        except Exception:
            pass

    return False


def click_search(page):
    buttons = page.locator("input[type='submit'], input[type='button'], button")

    for i in range(buttons.count()):
        button = buttons.nth(i)

        try:
            text = (
                button.inner_text().strip()
                or button.get_attribute("value")
                or ""
            )

            if "検索" in text:
                button.click()
                return True

        except Exception:
            pass

    return False


def click_date_order(page):
    """
    「日付順」をクリックする。
    """
    try:
        locator = page.get_by_text("日付順", exact=True)

        if locator.count() > 0:
            locator.first.click()
            time.sleep(1)
            print("日付順をクリックしました")
            return True

    except Exception as e:
        print(f"日付順クリックエラー: {e}")

    return False


def click_more(page):
    """
    「さらに表示」があれば繰り返しクリックする。
    """

    total_clicks = 0

    while True:
        clicked = False

        candidates = [
            page.get_by_text("さらに表示", exact=True),
            page.get_by_text("さらに表示する", exact=True),
        ]

        for locator in candidates:
            try:
                count = locator.count()

                if count > 0:
                    for i in range(count):
                        try:
                            item = locator.nth(i)

                            if item.is_visible():
                                item.click()
                                total_clicks += 1
                                clicked = True
                                time.sleep(1)
                                break

                        except Exception:
                            pass

                if clicked:
                    break

            except Exception:
                pass

        if not clicked:
            break

    print(f"「さらに表示」クリック回数: {total_clicks}")


def extract_rows(page, district):
    """
    検索結果から17:00開始以降の空き枠を抽出する。
    """

    rows = []

    # ページ全体のテキストから検索
    text = page.locator("body").inner_text()

    lines = [x.strip() for x in text.splitlines() if x.strip()]

    current_date = ""
    current_facility = ""
    current_room = ""

    for i, line in enumerate(lines):

        # 日付
        date_match = re.search(r"(\d{1,2})月(\d{1,2})日", line)

        if date_match:
            current_date = f"{date_match.group(1)}月{date_match.group(2)}日"

        # 時刻
        time_match = re.search(
            r"(\d{1,2}:\d{2})\s*[～~\-−]\s*(\d{1,2}:\d{2})",
            line
        )

        if not time_match:
            continue

        start = time_match.group(1)
        end = time_match.group(2)

        if not is_after_17(line):
            continue

        # 周辺テキストから施設名等を取得
        nearby = lines[max(0, i - 5):min(len(lines), i + 6)]

        for candidate in nearby:
            if candidate == line:
                continue

            if (
                "地区" not in candidate
                and "検索" not in candidate
                and "空き" not in candidate
                and "○" not in candidate
                and "×" not in candidate
                and len(candidate) <= 80
            ):
                if not current_facility:
                    current_facility = candidate
                elif not current_room:
                    current_room = candidate

        row = {
            "date": current_date,
            "district": district,
            "facility": current_facility,
            "room": current_room,
            "time": f"{start}～{end}",
        }

        rows.append(row)

    # 重複除去
    unique = {}

    for row in rows:
        key = (
            row["date"],
            row["district"],
            row["facility"],
            row["room"],
            row["time"],
        )

        unique[key] = row

    return list(unique.values())


def format_row(row):
    parts = [
        row.get("date", ""),
        row.get("district", ""),
        row.get("facility", ""),
        row.get("room", ""),
        row.get("time", ""),
    ]

    return " ".join(x for x in parts if x)


def main():
    previous_state = load_state()

    all_rows = []

    with sync_playwright() as p:

        browser = p.chromium.launch(headless=True)

        page = browser.new_page(
            viewport={"width": 1440, "height": 1200},
            locale="ja-JP",
        )

        try:

            for district in DISTRICTS:

                print("")
                print("=" * 60)
                print(f"検索開始: {district}")
                print("=" * 60)

                try:
                    page.goto(
                        URL,
                        wait_until="domcontentloaded",
                        timeout=60000,
                    )

                    page.wait_for_timeout(2000)

                    # 「1か月」
                    try:
                        month = page.get_by_text("1か月", exact=True)

                        if month.count() > 0:
                            month.first.click()
                            print("期間: 1か月")
                    except Exception as e:
                        print(f"1か月選択エラー: {e}")

                    page.wait_for_timeout(500)

                    # 時間帯は選択しない
                    print("時間帯: 選択なし（全時間帯）")

                    # 地区
                    if not select_district(page, district):
                        print(f"地区選択に失敗: {district}")
                        raise RuntimeError("地区選択失敗")

                    # バドミントン
                    if not select_badminton(page):
                        print("バドミントン選択に失敗")
                        raise RuntimeError("バドミントン選択失敗")

                    page.wait_for_timeout(500)

                    # 検索
                    if not click_search(page):
                        print("検索ボタンが見つかりません")
                        raise RuntimeError("検索ボタン失敗")

                    page.wait_for_timeout(3000)

                    # 日付順
                    click_date_order(page)

                    page.wait_for_timeout(1000)

                    # さらに表示
                    click_more(page)

                    page.wait_for_timeout(1000)

                    # 結果抽出
                    rows = extract_rows(page, district)

                    print(
                        f"{district}: 17:00開始以降 {len(rows)} 件"
                    )

                    all_rows.extend(rows)

                except Exception as e:
                    print(f"{district}の検索でエラー: {e}")

                    page.screenshot(
                        path=f"error_{len(all_rows)}.png",
                        full_page=True,
                    )

                    print("全地区の検索を完了できなかったため終了します。")

                    browser.close()
                    return

        finally:
            try:
                browser.close()
            except Exception:
                pass

    # 重複除去
    unique_rows = {}

    for row in all_rows:
        key = (
            row["date"],
            row["district"],
            row["facility"],
            row["room"],
            row["time"],
        )

        unique_rows[key] = row

    all_rows = list(unique_rows.values())

    # 結果保存
    with open(EVENING_FILE, "w", encoding="utf-8") as f:

        if all_rows:
            for row in sorted(
                all_rows,
                key=lambda x: (
                    x["date"],
                    x["district"],
                    x["facility"],
                    x["room"],
                    x["time"],
                ),
            ):
                f.write(format_row(row) + "\n")
        else:
            f.write("17:00開始以降の空き枠はありません。\n")

    # 現在の状態
    current_state = set()

    for row in all_rows:
        current_state.add(
            "|".join(
                [
                    row["date"],
                    row["district"],
                    row["facility"],
                    row["room"],
                    row["time"],
                ]
            )
        )

    # 新規だけ抽出
    new_slots = sorted(current_state - previous_state)

    with open(NEW_FILE, "w", encoding="utf-8") as f:

        if new_slots:
            f.write(f"今回新しく出現した空き枠: {len(new_slots)} 件\n")

            for slot in new_slots:
                f.write(slot.replace("|", " ") + "\n")
        else:
            f.write("新規なし\n")

    print("")
    print(f"現在の17:00開始以降空き枠: {len(current_state)} 件")
    print(f"今回新しく出現した空き枠: {len(new_slots)} 件")

    # 新規がなければ通知不要
    if not new_slots:
        print("新規空き枠がないためntfy通知はしません。")
        save_state(current_state)
        return

    # 通知本文
    message_lines = [
        "🏸 港区バドミントン空き枠",
        "",
        f"新しい空き枠が {len(new_slots)} 件あります。",
        "",
    ]

    for slot in new_slots:
        message_lines.append("・" + slot.replace("|", " "))

    message = "\n".join(message_lines)

    print("")
    print("===== ntfy通知内容 =====")
    print(message)
    print("========================")

    # ntfy通知
    notification_ok = send_ntfy(message)

    if not notification_ok:
        print("")
        print("ntfy通知に失敗したため、state.jsonは更新しません。")
        print("次回実行でも同じ空き枠を再通知できるようにします。")
        return

    # 通知成功後のみ状態保存
    save_state(current_state)

    print("ntfy通知成功。state.jsonを更新しました。")


if __name__ == "__main__":
    main()
