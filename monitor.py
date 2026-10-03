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
# 時刻
# =========================================================

def extract_time_ranges(text):
    """
    ページ内の時刻表記をすべて取得する。

    対応例：
    17:00～19:00
    18:00 ～ 21:00
    17:00-19:00
    17:00〜19:00
    """

    pattern = (
        r"(\d{1,2}:\d{2})"
        r"\s*[～〜~\-−－]"
        r"\s*"
        r"(\d{1,2}:\d{2})"
    )

    return re.findall(pattern, text)


def is_after_17(start_time):
    m = re.match(
        r"(\d{1,2}):(\d{2})",
        start_time
    )

    if not m:
        return False

    hour = int(m.group(1))
    minute = int(m.group(2))

    return (hour, minute) >= (17, 0)


# =========================================================
# ntfy
# =========================================================

def send_ntfy(message):

    topic = os.environ.get("NTFY_TOPIC")

    if not topic:
        print("NTFY_TOPICが設定されていません。")
        return False

    url = f"https://ntfy.sh/{topic}"

    request = Request(
        url,
        data=message.encode("utf-8"),
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
                f"ntfyエラー本文: {body}"
            )

        except Exception:
            pass

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

    print(
        f"地区選択を開始: {district}"
    )

    selects = page.locator("select")

    candidates = [
        district,
        district.replace("（すべて）", ""),
        district.replace("(すべて)", ""),
    ]

    # 完全一致
    for i in range(selects.count()):

        select = selects.nth(i)

        try:

            options = select.locator("option")

            for j in range(options.count()):

                option = options.nth(j)

                try:

                    text = option.inner_text().strip()

                    if text in candidates:

                        value = option.get_attribute(
                            "value"
                        )

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

    # 部分一致
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

                    if base_name in text:

                        value = option.get_attribute(
                            "value"
                        )

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

    print(
        f"地区選択に失敗: {district}"
    )

    return False


# =========================================================
# バドミントン
# =========================================================

def select_badminton(page):

    print(
        "バドミントン選択を開始"
    )

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
        "バドミントン選択に失敗"
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

    return False


# =========================================================
# 検索
# =========================================================

def click_search(page):

    # まず「検索」という文字そのものを探す
    try:

        locator = page.get_by_text(
            "検索",
            exact=True
        )

        if locator.count() > 0:

            for i in range(locator.count()):

                item = locator.nth(i)

                try:

                    if item.is_visible():

                        item.click()

                        print(
                            "検索ボタンをクリックしました"
                        )

                        return True

                except Exception:
                    pass

    except Exception:
        pass

    # input/buttonも確認
    selectors = [
        "input[type='submit']",
        "input[type='button']",
        "button",
    ]

    for selector in selectors:

        locator = page.locator(selector)

        for i in range(locator.count()):

            item = locator.nth(i)

            try:

                if not item.is_visible():
                    continue

                text = (
                    item.get_attribute("value")
                    or item.inner_text()
                    or ""
                )

                if "検索" in text:

                    item.click()

                    print(
                        "検索ボタンをクリックしました"
                    )

                    return True

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

            page.wait_for_timeout(
                1000
            )

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

    total = 0

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

                            total += 1

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
        f"「さらに表示」クリック回数: {total}"
    )


# =========================================================
# 日付抽出
# =========================================================

def find_dates(text):

    pattern = r"(\d{1,2})月(\d{1,2})日"

    return re.findall(
        pattern,
        text
    )


# =========================================================
# 結果抽出
# =========================================================

def extract_rows(page, district):

    print(
        f"{district}: 検索結果の解析を開始"
    )

    body = page.locator(
        "body"
    ).inner_text()

    # -----------------------------------------------------
    # デバッグ用
    # -----------------------------------------------------

    with open(
        f"result_{district.replace('（すべて）', '').replace('(', '').replace(')', '')}.txt",
        "w",
        encoding="utf-8"
    ) as f:

        f.write(body)

    # -----------------------------------------------------
    # 時刻をすべて探す
    # -----------------------------------------------------

    pattern = (
        r"(\d{1,2}:\d{2})"
        r"\s*[～〜~\-−－]"
        r"\s*"
        r"(\d{1,2}:\d{2})"
    )

    matches = list(
        re.finditer(
            pattern,
            body
        )
    )

    print(
        f"{district}: ページ内で見つかった時間枠: "
        f"{len(matches)} 件"
    )

    rows = []

    # -----------------------------------------------------
    # 各時間枠を処理
    # -----------------------------------------------------

    for match in matches:

        start = match.group(1)
        end = match.group(2)

        # 17:00開始未満は対象外
        if not is_after_17(start):
            continue

        time_text = (
            f"{start}～{end}"
        )

        # 時刻の前後500文字を取得
        start_pos = max(
            0,
            match.start() - 500
        )

        end_pos = min(
            len(body),
            match.end() + 500
        )

        context = body[
            start_pos:end_pos
        ]

        context_lines = [
            x.strip()
            for x in context.splitlines()
            if x.strip()
        ]

        # -------------------------------------------------
        # 日付
        # -------------------------------------------------

        date_matches = list(
            re.finditer(
                r"(\d{1,2})月(\d{1,2})日",
                context
            )
        )

        date_text = ""

        if date_matches:

            dm = date_matches[-1]

            date_text = (
                f"{dm.group(1)}月"
                f"{dm.group(2)}日"
            )

        # -------------------------------------------------
        # 周辺から施設・部屋を探す
        # -------------------------------------------------

        facility = ""
        room = ""

        # 時刻を含む行を特定
        time_line_index = None

        for index, line in enumerate(
            context_lines
        ):

            if (
                start in line
                and end in line
            ):

                time_line_index = index
                break

        if time_line_index is not None:

            before = context_lines[
                max(
                    0,
                    time_line_index - 8
                ):
                time_line_index
            ]

            # 後ろから見て候補を取得
            candidates = list(
                reversed(before)
            )

            for candidate in candidates:

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

                if len(candidate) > 100:
                    continue

                if not facility:

                    facility = candidate

                elif not room:

                    room = candidate
                    break

        # -------------------------------------------------
        # 行全体からのフォールバック
        # -------------------------------------------------

        if not facility:

            for line in context_lines:

                if (
                    "体育館" in line
                    or "アリーナ" in line
                    or "競技場" in line
                    or "スポーツ" in line
                ):

                    facility = line

                    break

        # -------------------------------------------------
        # レコード
        # -------------------------------------------------

        row = {
            "date": date_text,
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

    rows = list(
        unique.values()
    )

    print(
        f"{district}: 17:00開始以降 "
        f"{len(rows)} 件を抽出"
    )

    return rows


# =========================================================
# 表示
# =========================================================

def format_row(row):

    values = [
        row["date"],
        row["district"],
        row["facility"],
        row["room"],
        row["time"],
    ]

    return " ".join(
        x for x in values
        if x
    )


# =========================================================
# メイン
# =========================================================

def main():

    previous_state = load_state()

    all_rows = []

    successful = 0

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
                    # トップページ
                    # -------------------------------------------------

                    page.goto(
                        URL,
                        wait_until="domcontentloaded",
                        timeout=60000
                    )

                    page.wait_for_timeout(
                        2000
                    )

                    # -------------------------------------------------
                    # 1か月
                    # -------------------------------------------------

                    select_one_month(page)

                    page.wait_for_timeout(
                        500
                    )

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

                    page.wait_for_timeout(
                        500
                    )

                    # -------------------------------------------------
                    # バドミントン
                    # -------------------------------------------------

                    if not select_badminton(
                        page
                    ):

                        raise RuntimeError(
                            "バドミントン選択失敗"
                        )

                    page.wait_for_timeout(
                        500
                    )

                    # -------------------------------------------------
                    # 検索
                    # -------------------------------------------------

                    if not click_search(page):

                        raise RuntimeError(
                            "検索ボタン失敗"
                        )

                    page.wait_for_timeout(
                        3000
                    )

                    # -------------------------------------------------
                    # 日付順
                    # -------------------------------------------------

                    click_date_order(page)

                    page.wait_for_timeout(
                        1000
                    )

                    # -------------------------------------------------
                    # さらに表示
                    # -------------------------------------------------

                    click_more(page)

                    page.wait_for_timeout(
                        1000
                    )

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

                    all_rows.extend(
                        rows
                    )

                    successful += 1

                except Exception as e:

                    print(
                        f"{district}の検索でエラー: {e}"
                    )

                    try:

                        page.screenshot(
                            path=(
                                f"error_"
                                f"{successful}.png"
                            ),
                            full_page=True
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
    # 全地区成功確認
    # =====================================================

    if successful != len(DISTRICTS):

        print(
            "全地区の検索が完了していないため、"
            "state.jsonは更新しません。"
        )

        return

    # =====================================================
    # 重複削除
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
    # 結果保存
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
    # 現在のstate
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
    # ntfy通知
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

    notification_ok = send_ntfy(
        message
    )

    # =====================================================
    # 通知失敗
    # =====================================================

    if not notification_ok:

        print(
            "ntfy通知に失敗したため、"
            "state.jsonは更新しません。"
        )

        print(
            "次回実行でも再通知します。"
        )

        return

    # =====================================================
    # 通知成功
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
