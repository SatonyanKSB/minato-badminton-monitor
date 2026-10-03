import os
import json
import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


# ============================================================
# 設定
# ============================================================

URL = "https://web101.rsv.ws-scs.jp/web/index.jsp"

DISTRICTS = [
    "麻布地区（すべて）",
    "赤坂地区（すべて）",
    "芝地区（すべて）",
    "高輪地区（すべて）",
    "芝浦港南地区（すべて）",
]

ACTIVITY = "バドミントン"

# 開始時刻が17:00以降の枠だけ通知
NOTIFY_START_HOUR = 17

# 状態保存
STATE_FILE = Path("state.json")

# 結果ファイル
EVENING_FILE = Path("evening-results.txt")
NEW_SLOTS_FILE = Path("new-slots.txt")

# ntfy
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "").strip()


# ============================================================
# 状態管理
# ============================================================

def load_state():
    if not STATE_FILE.exists():
        return set()

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            return set(data)

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


# ============================================================
# 文字列処理
# ============================================================

def normalize_text(text):
    return (
        text
        .replace("\u3000", " ")
        .replace("\xa0", " ")
        .strip()
    )


# ============================================================
# 時刻処理
# ============================================================

TIME_PATTERN = re.compile(
    r"(?P<start>\d{1,2})時(?P<start_min>\d{2})分"
    r"\s*[～〜~\-－]"
    r"\s*"
    r"(?P<end>\d{1,2})時(?P<end_min>\d{2})分"
)


def extract_time(text):
    if not text:
        return None

    match = TIME_PATTERN.search(text)

    if not match:
        return None

    return (
        int(match.group("start")),
        int(match.group("start_min")),
        int(match.group("end")),
        int(match.group("end_min")),
    )


def is_after_17(start_hour, start_min):
    return (
        start_hour > NOTIFY_START_HOUR
        or (
            start_hour == NOTIFY_START_HOUR
            and start_min >= 0
        )
    )


# ============================================================
# ntfy通知
# ============================================================

def send_ntfy(message):

    if not NTFY_TOPIC:
        print("NTFY_TOPICが設定されていません。")
        return False

    try:
        import urllib.request
        import urllib.error

        url = f"https://ntfy.sh/{NTFY_TOPIC}"

        # HTTPヘッダーには日本語・絵文字を入れない
        # 本文はUTF-8で送信する
        request = urllib.request.Request(
            url,
            data=message.encode("utf-8"),
            method="POST",
            headers={
                "Title": "Minato Badminton",
                "Priority": "high",
                "Tags": "badminton",
                "Content-Type": "text/plain; charset=utf-8",
            },
        )

        with urllib.request.urlopen(
            request,
            timeout=20
        ) as response:

            status = response.status

        print(
            f"ntfy送信成功: HTTP {status}"
        )

        return 200 <= status < 300

    except urllib.error.HTTPError as e:

        print(
            f"ntfy送信エラー: HTTP {e.code}"
        )

        try:
            print(
                e.read().decode(
                    "utf-8",
                    errors="ignore"
                )
            )
        except Exception:
            pass

        return False

    except Exception as e:

        print(
            f"ntfy送信エラー: {e}"
        )

        return False


# ============================================================
# 地区選択
# ============================================================

def select_district(page, district):

    print(
        f"地区選択を開始: {district}"
    )

    selects = page.locator("select")

    count = selects.count()

    print(
        f"select要素数: {count}"
    )

    target = (
        district
        .replace("（すべて）", "")
        .replace("(すべて)", "")
        .strip()
    )

    for i in range(count):

        select = selects.nth(i)

        try:

            options = select.locator("option")

            for j in range(options.count()):

                option = options.nth(j)

                try:

                    text = normalize_text(
                        option.inner_text()
                    )

                    value = option.get_attribute(
                        "value"
                    )

                    if not text:
                        continue

                    if text == district:

                        select.select_option(
                            value=value
                        )

                        print(
                            f"地区選択成功（完全一致）: {text}"
                        )

                        return True

                    normalized = (
                        text
                        .replace("（すべて）", "")
                        .replace("(すべて)", "")
                        .strip()
                    )

                    if normalized == target:

                        select.select_option(
                            value=value
                        )

                        print(
                            f"地区選択成功（部分一致）: {text}"
                        )

                        return True

                except Exception:
                    continue

        except Exception:
            continue

    print(
        f"地区選択に失敗しました: {district}"
    )

    return False


# ============================================================
# バドミントン選択
# ============================================================

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

                    text = normalize_text(
                        option.inner_text()
                    )

                    if ACTIVITY in text:

                        value = option.get_attribute(
                            "value"
                        )

                        if value is not None:

                            select.select_option(
                                value=value
                            )

                        else:

                            select.select_option(
                                label=text
                            )

                        print(
                            "バドミントン選択成功"
                        )

                        return True

                except Exception:
                    continue

        except Exception:
            continue

    try:

        element = page.get_by_text(
            ACTIVITY,
            exact=True
        )

        if element.count() > 0:

            element.first.click()

            print(
                "バドミントン選択成功（クリック方式）"
            )

            return True

    except Exception:
        pass

    print(
        "バドミントン選択に失敗しました"
    )

    return False


# ============================================================
# 1か月
# ============================================================

def select_one_month(page):

    candidates = [
        page.get_by_text(
            "1か月",
            exact=True
        ),
        page.get_by_role(
            "button",
            name="1か月"
        ),
        page.locator(
            "input[value='1か月']"
        ),
        page.locator(
            "button"
        ).filter(
            has_text="1か月"
        ),
    ]

    for locator in candidates:

        try:

            if locator.count() > 0:

                locator.first.click()

                time.sleep(0.5)

                print(
                    "期間: 1か月"
                )

                return True

        except Exception:
            continue

    print(
        "「1か月」選択を確認できませんでした"
    )

    return False


# ============================================================
# 検索
# ============================================================

def click_search(page):

    candidates = [
        page.get_by_text(
            "検索",
            exact=True
        ),
        page.get_by_role(
            "button",
            name="検索"
        ),
        page.locator(
            "input[type='submit'][value='検索']"
        ),
        page.locator(
            "input[value='検索']"
        ),
        page.locator(
            "button"
        ).filter(
            has_text="検索"
        ),
    ]

    for locator in candidates:

        try:

            if locator.count() > 0:

                locator.first.click()

                print(
                    "検索ボタンをクリックしました"
                )

                try:

                    page.wait_for_load_state(
                        "networkidle",
                        timeout=15000
                    )

                except Exception:
                    pass

                return True

        except Exception:
            continue

    print(
        "検索ボタンをクリックできませんでした"
    )

    return False


# ============================================================
# 日付順
# ============================================================

def click_date_order(page):

    candidates = [
        page.get_by_text(
            "日付順",
            exact=True
        ),
        page.get_by_role(
            "tab",
            name="日付順"
        ),
        page.locator(
            "a"
        ).filter(
            has_text="日付順"
        ),
        page.locator(
            "button"
        ).filter(
            has_text="日付順"
        ),
    ]

    for locator in candidates:

        try:

            if locator.count() > 0:

                locator.first.click()

                time.sleep(1)

                try:

                    page.wait_for_load_state(
                        "networkidle",
                        timeout=10000
                    )

                except Exception:
                    pass

                print(
                    "日付順をクリックしました"
                )

                return True

        except Exception:
            continue

    print(
        "日付順ボタンをクリックできませんでした"
    )

    return False


# ============================================================
# さらに表示
# ============================================================

def click_more(page):

    count_clicked = 0

    for _ in range(50):

        clicked = False

        candidates = [
            page.get_by_text(
                "さらに表示",
                exact=True
            ),
            page.get_by_role(
                "button",
                name="さらに表示"
            ),
            page.locator(
                "button"
            ).filter(
                has_text="さらに表示"
            ),
            page.locator(
                "a"
            ).filter(
                has_text="さらに表示"
            ),
        ]

        for locator in candidates:

            try:

                count = locator.count()

                if count == 0:
                    continue

                for i in range(count):

                    item = locator.nth(i)

                    try:

                        if not item.is_visible():
                            continue

                    except Exception:
                        pass

                    try:

                        item.scroll_into_view_if_needed()

                        item.click()

                        time.sleep(0.8)

                        count_clicked += 1

                        clicked = True

                        break

                    except Exception:
                        continue

                if clicked:
                    break

            except Exception:
                continue

        if not clicked:
            break

    print(
        f"「さらに表示」クリック回数: {count_clicked}"
    )

    return count_clicked


# ============================================================
# 日付
# ============================================================

DATE_PATTERN = re.compile(
    r"^(\d{1,2})月(\d{1,2})日"
)


def is_date_line(text):

    return (
        DATE_PATTERN.match(text)
        is not None
    )


# ============================================================
# 結果ページのヘッダー判定
# ============================================================

def is_result_header(line):

    normalized = normalize_text(line)

    # 実際のサイトでは
    # 「館    施設    時間帯    予約」
    # がタブ区切りで1行になっている。
    if (
        "館" in normalized
        and "施設" in normalized
        and "時間帯" in normalized
        and "予約" in normalized
    ):
        return True

    return normalized in {
        "館",
        "施設",
        "時間帯",
        "予約",
    }


# ============================================================
# 検索結果解析
# ============================================================

def parse_result_lines(text):

    lines = [
        normalize_text(line)
        for line in text.splitlines()
    ]

    lines = [
        line
        for line in lines
        if line
    ]

    rows = []

    current_date = None

    seen = set()

    for i, line in enumerate(lines):

        # ----------------------------------------------------
        # 日付
        # ----------------------------------------------------

        if is_date_line(line):

            match = DATE_PATTERN.match(line)

            if match:

                month = int(match.group(1))
                day = int(match.group(2))

                current_date = (
                    f"{month}月{day}日"
                )

            continue

        # ----------------------------------------------------
        # 時間帯
        # ----------------------------------------------------

        time_info = extract_time(line)

        if time_info is None:
            continue

        if current_date is None:
            continue

        (
            start_hour,
            start_min,
            end_hour,
            end_min,
        ) = time_info

        # ----------------------------------------------------
        # 17:00開始以降のみ
        # ----------------------------------------------------

        if not is_after_17(
            start_hour,
            start_min
        ):
            continue

        # ----------------------------------------------------
        # 時間帯の直前から
        # 「館名」「施設名」を取得
        #
        # 実際のサイト：
        #
        # 館  施設  時間帯  予約
        # 港南小学校
        # 体育館全面（休日）
        # 18時00分～21時00分
        #
        # ----------------------------------------------------

        previous = []

        j = i - 1

        while (
            j >= 0
            and len(previous) < 10
        ):

            candidate = lines[j]

            # 日付を越えたら終了
            if is_date_line(candidate):
                break

            # 結果ヘッダーは完全に除外
            if is_result_header(candidate):
                j -= 1
                continue

            # その他の不要な表示
            if candidate in {
                "すべて開く",
                "すべて閉じる",
                "施設ごと",
                "日付順",
            }:
                j -= 1
                continue

            # 時刻は除外
            if extract_time(candidate):
                j -= 1
                continue

            # 数字だけの時刻軸などを除外
            if re.fullmatch(
                r"[\d\s\t]+",
                candidate
            ):
                j -= 1
                continue

            previous.append(candidate)

            j -= 1

        # ----------------------------------------------------
        # 直前の2つが
        #
        # previous[0] = 施設名
        # previous[1] = 館名
        #
        # なので逆にする。
        # ----------------------------------------------------

        facility = ""
        building = ""

        if len(previous) >= 1:
            facility = previous[0]

        if len(previous) >= 2:
            building = previous[1]

        # ----------------------------------------------------
        # ヘッダー等が混入していないか確認
        # ----------------------------------------------------

        if not facility:
            continue

        if is_result_header(facility):
            continue

        if is_result_header(building):
            continue

        # ----------------------------------------------------
        # 明らかに検索結果ではない文字を除外
        # ----------------------------------------------------

        invalid_words = {
            "指定条件に合致した空き状況を表示しています。",
            "利用する施設・日時の予約ボタンをクリックします。",
            "条件変更",
            "空き状況",
            "ホーム",
            "予約",
            "抽選",
            "利用者",
            "その他",
            "ログイン",
        }

        if facility in invalid_words:
            continue

        if building in invalid_words:
            continue

        # ----------------------------------------------------
        # 重複除外
        # ----------------------------------------------------

        key = (
            current_date,
            building,
            facility,
            start_hour,
            start_min,
            end_hour,
            end_min,
        )

        if key in seen:
            continue

        seen.add(key)

        rows.append({
            "date": current_date,
            "building": building,
            "facility": facility,
            "start_hour": start_hour,
            "start_min": start_min,
            "end_hour": end_hour,
            "end_min": end_min,
        })

    return rows


# ============================================================
# 表示
# ============================================================

def format_row(row):

    return (
        f"{row['date']} "
        f"{row['building']} "
        f"{row['facility']} "
        f"{row['start_hour']:02d}:"
        f"{row['start_min']:02d}"
        f"～"
        f"{row['end_hour']:02d}:"
        f"{row['end_min']:02d}"
    )


# ============================================================
# 一意キー
# ============================================================

def make_key(row):

    return (
        f"{row['date']}|"
        f"{row['building']}|"
        f"{row['facility']}|"
        f"{row['start_hour']:02d}:"
        f"{row['start_min']:02d}|"
        f"{row['end_hour']:02d}:"
        f"{row['end_min']:02d}"
    )


# ============================================================
# 1地区検索
# ============================================================

def search_district(page, district):

    print()
    print("=" * 60)
    print(
        f"検索開始: {district}"
    )
    print("=" * 60)

    print("期間: 1か月")
    print(
        "時間帯: 選択なし（全時間帯）"
    )

    # --------------------------------------------------------
    # ホーム
    # --------------------------------------------------------

    page.goto(
        URL,
        wait_until="domcontentloaded",
        timeout=30000
    )

    time.sleep(1)

    # --------------------------------------------------------
    # 1か月
    # --------------------------------------------------------

    select_one_month(page)

    # --------------------------------------------------------
    # 地区
    # --------------------------------------------------------

    if not select_district(
        page,
        district
    ):

        raise RuntimeError(
            f"地区選択に失敗: {district}"
        )

    # --------------------------------------------------------
    # バドミントン
    # --------------------------------------------------------

    if not select_badminton(page):

        raise RuntimeError(
            "バドミントン選択に失敗"
        )

    # --------------------------------------------------------
    # 検索
    # --------------------------------------------------------

    if not click_search(page):

        raise RuntimeError(
            "検索ボタンをクリックできませんでした"
        )

    time.sleep(2)

    # --------------------------------------------------------
    # 日付順
    # --------------------------------------------------------

    click_date_order(page)

    time.sleep(1)

    # --------------------------------------------------------
    # さらに表示
    # --------------------------------------------------------

    click_more(page)

    time.sleep(1)

    # --------------------------------------------------------
    # ページ全文
    # --------------------------------------------------------

    body_text = page.locator(
        "body"
    ).inner_text()

    # --------------------------------------------------------
    # 生データ保存
    # --------------------------------------------------------

    safe_name = (
        district
        .replace("（すべて）", "")
        .replace("(すべて)", "")
        .replace("/", "_")
    )

    result_file = Path(
        f"result_{safe_name}.txt"
    )

    result_file.write_text(
        body_text,
        encoding="utf-8"
    )

    # --------------------------------------------------------
    # 時間枠数
    # --------------------------------------------------------

    time_ranges = TIME_PATTERN.findall(
        body_text
    )

    print(
        f"ページ内で見つかった時間枠: "
        f"{len(time_ranges)} 件"
    )

    # --------------------------------------------------------
    # 解析
    # --------------------------------------------------------

    rows = parse_result_lines(
        body_text
    )

    print(
        f"{district}: "
        f"17:00開始以降 "
        f"{len(rows)} 件"
    )

    for row in rows:

        print(
            "  "
            + format_row(row)
        )

    return rows


# ============================================================
# メイン
# ============================================================

def main():

    print()
    print("=" * 60)
    print(
        "港区バドミントン空き状況モニター【本番】"
    )
    print("=" * 60)
    print()

    previous_state = load_state()

    all_rows = []

    successful_districts = 0

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page(
            viewport={
                "width": 1280,
                "height": 1000,
            },
            locale="ja-JP",
        )

        try:

            for district in DISTRICTS:

                try:

                    rows = search_district(
                        page,
                        district
                    )

                    successful_districts += 1

                    for row in rows:

                        row["district"] = district

                        all_rows.append(row)

                except Exception as e:

                    print()
                    print(
                        f"{district}: 検索エラー"
                    )

                    print(e)

                    safe_name = (
                        district
                        .replace(
                            "（すべて）",
                            ""
                        )
                        .replace(
                            "(すべて)",
                            ""
                        )
                    )

                    try:

                        page.screenshot(
                            path=(
                                f"error_"
                                f"{safe_name}.png"
                            ),
                            full_page=True
                        )

                    except Exception:
                        pass

        finally:

            browser.close()

    # ========================================================
    # 5地区すべて成功したか
    # ========================================================

    print()
    print("=" * 60)

    print(
        f"検索成功地区: "
        f"{successful_districts}/"
        f"{len(DISTRICTS)}"
    )

    print("=" * 60)

    if successful_districts != len(
        DISTRICTS
    ):

        print(
            "5地区すべての検索に成功していないため、"
            "state.jsonを更新しません。"
        )

        NEW_SLOTS_FILE.write_text(
            "検索失敗のため状態更新なし\n",
            encoding="utf-8"
        )

        return

    # ========================================================
    # 現在の17:00開始以降空き枠
    # ========================================================

    current_state = set()

    for row in all_rows:

        current_state.add(
            make_key(row)
        )

    print()
    print(
        "現在の17:00開始以降空き枠: "
        f"{len(current_state)} 件"
    )

    # ========================================================
    # 新規枠
    # ========================================================

    new_keys = (
        current_state
        - previous_state
    )

    new_rows = [
        row
        for row in all_rows
        if make_key(row) in new_keys
    ]

    new_rows.sort(
        key=lambda r: (
            r["date"],
            r["start_hour"],
            r["start_min"],
            r["building"],
            r["facility"],
        )
    )

    print(
        "今回新しく出現した空き枠: "
        f"{len(new_rows)} 件"
    )

    # ========================================================
    # evening-results.txt
    # ========================================================

    evening_lines = []

    sorted_all_rows = sorted(
        all_rows,
        key=lambda r: (
            r["date"],
            r["start_hour"],
            r["start_min"],
            r["building"],
            r["facility"],
        )
    )

    for row in sorted_all_rows:

        evening_lines.append(
            f"{row['district']} | "
            f"{format_row(row)}"
        )

    if evening_lines:

        EVENING_FILE.write_text(
            "\n".join(evening_lines),
            encoding="utf-8"
        )

    else:

        EVENING_FILE.write_text(
            "17:00開始以降の空き枠なし\n",
            encoding="utf-8"
        )

    # ========================================================
    # new-slots.txt
    # ========================================================

    if new_rows:

        new_lines = []

        for row in new_rows:

            new_lines.append(
                f"{row['district']} | "
                f"{format_row(row)}"
            )

        NEW_SLOTS_FILE.write_text(
            "\n".join(new_lines),
            encoding="utf-8"
        )

    else:

        NEW_SLOTS_FILE.write_text(
            "今回新しく出現した空き枠はありません。\n",
            encoding="utf-8"
        )

    # ========================================================
    # 新規枠なし
    # ========================================================

    if not new_rows:

        print(
            "新規空き枠がないため"
            "ntfy通知はしません。"
        )

        save_state(
            current_state
        )

        return

    # ========================================================
    # ntfy本文
    # ========================================================

    message_lines = [
        "🏸 港区バドミントン空き枠",
        "",
        f"新しく出現した空き枠: "
        f"{len(new_rows)}件",
        "",
    ]

    for row in new_rows:

        message_lines.append(
            f"📅 {row['date']}"
        )

        message_lines.append(
            f"📍 {row['district']}"
        )

        message_lines.append(
            f"🏢 {row['building']} / "
            f"{row['facility']}"
        )

        message_lines.append(
            f"🕐 "
            f"{row['start_hour']:02d}:"
            f"{row['start_min']:02d}"
            f"～"
            f"{row['end_hour']:02d}:"
            f"{row['end_min']:02d}"
        )

        message_lines.append("")

    message = "\n".join(
        message_lines
    )

    print()
    print("=" * 60)
    print("ntfy通知")
    print("=" * 60)
    print(message)

    # ========================================================
    # ntfy送信
    # ========================================================

    success = send_ntfy(
        message
    )

    # ========================================================
    # 通知成功時のみstate更新
    # ========================================================

    if success:

        print(
            "通知成功。"
            "state.jsonを更新します。"
        )

        save_state(
            current_state
        )

    else:

        print(
            "通知失敗。"
            "state.jsonは更新しません。"
        )

        print(
            "次回実行時に再度通知します。"
        )


# ============================================================
# 実行
# ============================================================

if __name__ == "__main__":
    main()
