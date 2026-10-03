import os
import json
import re
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from playwright.sync_api import sync_playwright


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


# =========================================================
# state.json
# =========================================================

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
        json.dump(
            sorted(state),
            f,
            ensure_ascii=False,
            indent=2
        )


# =========================================================
# 時刻判定
# =========================================================

def extract_start_time(time_text):
    """
    例：
    17:00～19:00
    18:00～21:00
    から開始時刻を取得
    """

    m = re.search(
        r"(\d{1,2}):(\d{2})\s*[～~\-−]\s*(\d{1,2}):(\d{2})",
        time_text
    )

    if not m:
        return None

    return int(m.group(1)), int(m.group(2))


def is_after_17(time_text):
    result = extract_start_time(time_text)

    if not result:
        return False

    hour, minute = result

    return (hour, minute) >= (17, 0)


# =========================================================
# ntfy通知
# =========================================================

def send_ntfy(message):

    topic = os.environ.get("NTFY_TOPIC")

    if not topic:
        print("NTFY_TOPICが設定されていないため通知できません。")
        return False

    url = f"https://ntfy.sh/{topic}"

    payload = message.encode("utf-8")

    request = Request(
        url,
        data=payload,
        headers={
            "Content-Type": "text/plain; charset=utf-8",
            "Title": "港区バドミントン空き枠",
            "Priority": "high",
            "Tags": "badminton",
            "User-Agent": "Minato-Badminton-Monitor",
        },
        method="POST",
    )

    try:

        with urlopen(request, timeout=20) as response:

            print(
                f"ntfy送信成功: HTTP {response.status}"
            )

            return 200 <= response.status < 300

    except HTTPError as e:

        print(
            f"ntfy送信エラー: HTTP {e.code}"
        )

        try:
            body = e.read().decode(
                "utf-8",
                errors="replace"
            )

            print(
                f"ntfyのエラー本文: {body}"
            )

        except Exception as body_error:

            print(
                f"ntfyエラー本文取得失敗: {body_error}"
            )

        return False

    except Exception as e:

        print(
            f"ntfy送信エラー: {e}"
        )

        return False


# =========================================================
# 地区選択
# =========================================================

def select_district(page, district):

    print(f"地区選択を開始: {district}")

    # 実際のサイトで表示される可能性がある表記
    candidates = [
        district,
        district.replace("（すべて）", ""),
        district.replace("(すべて)", ""),
    ]

    selects = page.locator("select")

    print(
        f"select要素数: {selects.count()}"
    )

    # -----------------------------------------------------
    # まず完全一致
    # -----------------------------------------------------

    for i in range(selects.count()):

        select = selects.nth(i)

        try:

            options = select.locator("option")

            for j in range(options.count()):

                option = options.nth(j)

                try:

                    text = option.inner_text().strip()

                    if text in candidates:

                        value = option.get_attribute("value")

                        if value:

                            select.select_option(
                                value=value
                            )

                        else:

                            select.select_option(
                                label=text
                            )

                        print(
                            f"地区選択成功: {text}"
                        )

                        return True

                except Exception:
                    pass

        except Exception:
            pass

    # -----------------------------------------------------
    # 部分一致
    # -----------------------------------------------------

    base_name = (
        district
        .replace("（すべて）", "")
        .replace("(すべて)", "")
        .strip()
    )

    for i in range(selects.count()):

        select = selects.nth(i)

        try:

            options = select.locator("option")

            for j in range(options.count()):

                option = options.nth(j)

                try:

                    text = option.inner_text().strip()

                    if base_name and base_name in text:

                        value = option.get_attribute("value")

                        if value:

                            select.select_option(
                                value=value
                            )

                        else:

                            select.select_option(
                                label=text
                            )

                        print(
                            f"地区選択成功（部分一致）: {text}"
                        )

                        return True

                except Exception:
                    pass

        except Exception:
            pass

    # -----------------------------------------------------
    # デバッグ
    # -----------------------------------------------------

    print(
        f"地区選択に失敗しました: {district}"
    )

    print("現在ページに存在するselectの選択肢:")

    for i in range(selects.count()):

        try:

            print(
                f"--- select {i} ---"
            )

            options = selects.nth(i).locator("option")

            for j in range(options.count()):

                try:

                    print(
                        " ",
                        options.nth(j).inner_text().strip()
                    )

                except Exception:
                    pass

        except Exception:
            pass

    return False


# =========================================================
# バドミントン選択
# =========================================================

def select_badminton(page):

    print("バドミントン選択を開始")

    selects = page.locator("select")

    for i in range(selects.count()):

        select = selects.nth(i)

        try:

            options = select.locator("option")

            for j in range(options.count()):

                option = options.nth(j)

                try:

                    text = option.inner_text().strip()

                    if text == "バドミントン":

                        value = option.get_attribute(
                            "value"
                        )

                        if value:

                            select.select_option(
                                value=value
                            )

                        else:

                            select.select_option(
                                label="バドミントン"
                            )

                        print(
                            "バドミントン選択成功"
                        )

                        return True

                except Exception:
                    pass

        except Exception:
            pass

    print(
        "バドミントンの選択肢が見つかりませんでした"
    )

    return False


# =========================================================
# 1か月
# =========================================================

def select_one_month(page):

    try:

        locator = page.get_by_text(
            "1か月",
            exact=True
        )

        if locator.count() > 0:

            locator.first.click()

            print(
                "期間: 1か月"
            )

            return True

    except Exception as e:

        print(
            f"1か月選択エラー: {e}"
        )

    print(
        "1か月ボタンが見つかりません"
    )

    return False


# =========================================================
# 検索ボタン
# =========================================================

def click_search(page):

    # まず「検索」という文字を持つボタンを探す
    candidates = [
        page.get_by_text(
            "検索",
            exact=True
        ),
        page.locator(
            "input[type='submit']"
        ),
        page.locator(
            "input[type='button']"
        ),
        page.locator(
            "button"
        ),
    ]

    for locator in candidates:

        try:

            count = locator.count()

            for i in range(count):

                item = locator.nth(i)

                try:

                    if not item.is_visible():
                        continue

                    text = (
                        item.inner_text().strip()
                        if item.evaluate(
                            "(el) => el.tagName"
                        ) != "INPUT"
                        else (
                            item.get_attribute("value")
                            or ""
                        )
                    )

                    if (
                        "検索" in text
                        or locator == candidates[0]
                    ):

                        item.click()

                        print(
                            "検索ボタンをクリックしました"
                        )

                        return True

                except Exception:
                    pass

        except Exception:
            pass

    print(
        "検索ボタンが見つかりません"
    )

    return False


# =========================================================
# 日付順
# =========================================================

def click_date_order(page):

    try:

        locator = page.get_by_text(
            "日付順",
            exact=True
        )

        if locator.count() > 0:

            locator.first.click()

            page.wait_for_timeout(1000)

            print(
                "日付順をクリックしました"
            )

            return True

    except Exception as e:

        print(
            f"日付順クリックエラー: {e}"
        )

    return False


# =========================================================
# さらに表示
# =========================================================

def click_more(page):

    total_clicks = 0

    while True:

        clicked = False

        for text in [
            "さらに表示",
            "さらに表示する",
        ]:

            try:

                locator = page.get_by_text(
                    text,
                    exact=True
                )

                for i in range(locator.count()):

                    item = locator.nth(i)

                    try:

                        if item.is_visible():

                            item.click()

                            total_clicks += 1

                            clicked = True

                            page.wait_for_timeout(
                                1000
                            )

                            break

                    except Exception:
                        pass

                if clicked:
                    break

            except Exception:
                pass

        if not clicked:
            break

    print(
        f"「さらに表示」クリック回数: {total_clicks}"
    )


# =========================================================
# 結果解析
# =========================================================

def extract_rows(page, district):

    rows = []

    body_text = page.locator(
        "body"
    ).inner_text()

    lines = [
        x.strip()
        for x in body_text.splitlines()
        if x.strip()
    ]

    current_date = ""

    # -----------------------------------------------------
    # 日付を保持しながら結果を読む
    # -----------------------------------------------------

    for i, line in enumerate(lines):

        date_match = re.search(
            r"(\d{1,2})月(\d{1,2})日",
            line
        )

        if date_match:

            current_date = (
                f"{date_match.group(1)}月"
                f"{date_match.group(2)}日"
            )

        time_match = re.search(
            r"(\d{1,2}:\d{2})"
            r"\s*[～~\-−]"
            r"\s*(\d{1,2}:\d{2})",
            line
        )

        if not time_match:
            continue

        start = time_match.group(1)
        end = time_match.group(2)

        time_text = (
            f"{start}～{end}"
        )

        # 17:00開始未満は除外
        if not is_after_17(time_text):
            continue

        # -------------------------------------------------
        # 前後の行から施設・部屋情報を探す
        # -------------------------------------------------

        nearby = lines[
            max(0, i - 8):
            min(len(lines), i + 8)
        ]

        facility = ""
        room = ""

        for candidate in nearby:

            if candidate == line:
                continue

            if re.search(
                r"\d{1,2}月\d{1,2}日",
                candidate
            ):
                continue

            if re.search(
                r"\d{1,2}:\d{2}",
                candidate
            ):
                continue

            if candidate in [
                "空き",
                "予約",
                "○",
                "×",
                "日付順",
                "施設ごと",
            ]:
                continue

            # 長すぎるページ説明等を除外
            if len(candidate) > 100:
                continue

            if not facility:
                facility = candidate
                continue

            if not room:
                room = candidate
                break

        row = {
            "date": current_date,
            "district": district,
            "facility": facility,
            "room": room,
            "time": time_text,
        }

        rows.append(row)

    # -----------------------------------------------------
    # 重複削除
    # -----------------------------------------------------

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


# =========================================================
# 表示用
# =========================================================

def format_row(row):

    return " ".join(
        x
        for x in [
            row["date"],
            row["district"],
            row["facility"],
            row["room"],
            row["time"],
        ]
        if x
    )


# =========================================================
# メイン
# =========================================================

def main():

    previous_state = load_state()

    all_rows = []

    successful_districts = 0

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page(
            viewport={
                "width": 1440,
                "height": 1200,
            },
            locale="ja-JP",
        )

        try:

            for district in DISTRICTS:

                print("")
                print("=" * 60)
                print(
                    f"検索開始: {district}"
                )
                print("=" * 60)

                try:

                    # -------------------------------------------------
                    # ページを開く
                    # -------------------------------------------------

                    page.goto(
                        URL,
                        wait_until="domcontentloaded",
                        timeout=60000,
                    )

                    page.wait_for_timeout(2000)

                    # -------------------------------------------------
                    # 1か月
                    # -------------------------------------------------

                    select_one_month(page)

                    page.wait_for_timeout(500)

                    # -------------------------------------------------
                    # 時間帯は選択しない
                    # -------------------------------------------------

                    print(
                        "時間帯: 選択なし（全時間帯）"
                    )

                    # -------------------------------------------------
                    # 地区
                    # -------------------------------------------------

                    if not select_district(
                        page,
                        district
                    ):

                        raise RuntimeError(
                            "地区選択失敗"
                        )

                    page.wait_for_timeout(500)

                    # -------------------------------------------------
                    # バドミントン
                    # -------------------------------------------------

                    if not select_badminton(
                        page
                    ):

                        raise RuntimeError(
                            "バドミントン選択失敗"
                        )

                    page.wait_for_timeout(500)

                    # -------------------------------------------------
                    # 検索
                    # -------------------------------------------------

                    if not click_search(page):

                        raise RuntimeError(
                            "検索ボタン失敗"
                        )

                    page.wait_for_timeout(3000)

                    # -------------------------------------------------
                    # 日付順
                    # -------------------------------------------------

                    click_date_order(page)

                    page.wait_for_timeout(1000)

                    # -------------------------------------------------
                    # さらに表示
                    # -------------------------------------------------

                    click_more(page)

                    page.wait_for_timeout(1000)

                    # -------------------------------------------------
                    # 結果抽出
                    # -------------------------------------------------

                    rows = extract_rows(
                        page,
                        district
                    )

                    print(
                        f"{district}: "
                        f"17:00開始以降 "
                        f"{len(rows)} 件"
                    )

                    all_rows.extend(rows)

                    successful_districts += 1

                except Exception as e:

                    print(
                        f"{district}の検索でエラー: {e}"
                    )

                    try:

                        page.screenshot(
                            path=(
                                f"error_"
                                f"{successful_districts}.png"
                            ),
                            full_page=True,
                        )

                    except Exception:
                        pass

                    print(
                        "全地区の検索を完了できなかったため終了します。"
                    )

                    return

        finally:

            try:
                browser.close()
            except Exception:
                pass

    # =====================================================
    # 全地区検索成功確認
    # =====================================================

    if successful_districts != len(DISTRICTS):

        print(
            "全地区の検索が完了していないため、"
            "state.jsonは更新しません。"
        )

        return

    # =====================================================
    # 全体の重複削除
    # =====================================================

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

    all_rows = list(
        unique_rows.values()
    )

    # =====================================================
    # evening-results.txt
    # =====================================================

    with open(
        EVENING_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        if all_rows:

            sorted_rows = sorted(
                all_rows,
                key=lambda x: (
                    x["date"],
                    x["district"],
                    x["facility"],
                    x["room"],
                    x["time"],
                )
            )

            for row in sorted_rows:

                f.write(
                    format_row(row)
                    + "\n"
                )

        else:

            f.write(
                "17:00開始以降の空き枠はありません。\n"
            )

    # =====================================================
    # 現在の状態
    # =====================================================

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

    # =====================================================
    # 新規枠
    # =====================================================

    new_slots = sorted(
        current_state - previous_state
    )

    with open(
        NEW_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        if new_slots:

            f.write(
                f"今回新しく出現した空き枠: "
                f"{len(new_slots)} 件\n"
            )

            for slot in new_slots:

                f.write(
                    slot.replace("|", " ")
                    + "\n"
                )

        else:

            f.write(
                "新規なし\n"
            )

    print("")
    print(
        f"現在の17:00開始以降空き枠: "
        f"{len(current_state)} 件"
    )

    print(
        f"今回新しく出現した空き枠: "
        f"{len(new_slots)} 件"
    )

    # =====================================================
    # 新規なし
    # =====================================================

    if not new_slots:

        print(
            "新規空き枠がないため"
            "ntfy通知はしません。"
        )

        save_state(
            current_state
        )

        return

    # =====================================================
    # 通知本文
    # =====================================================

    message_lines = [
        "🏸 港区バドミントン空き枠",
        "",
        f"新しい空き枠が "
        f"{len(new_slots)} 件あります。",
        "",
    ]

    for slot in new_slots:

        message_lines.append(
            "・" + slot.replace("|", " ")
        )

    message = "\n".join(
        message_lines
    )

    print("")
    print(
        "===== ntfy通知内容 ====="
    )
    print(message)
    print(
        "========================"
    )

    # =====================================================
    # ntfy送信
    # =====================================================

    notification_ok = send_ntfy(
        message
    )

    # =====================================================
    # 通知失敗
    # =====================================================

    if not notification_ok:

        print("")
        print(
            "ntfy通知に失敗したため、"
            "state.jsonは更新しません。"
        )

        print(
            "次回実行でも同じ空き枠を"
            "再通知できるようにします。"
        )

        return

    # =====================================================
    # 通知成功後のみstate更新
    # =====================================================

    save_state(
        current_state
    )

    print(
        "ntfy通知成功。"
        "state.jsonを更新しました。"
    )


if __name__ == "__main__":
    main()
