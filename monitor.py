from playwright.sync_api import sync_playwright
from pathlib import Path
import re
import json
import os
import urllib.request


URL = "https://web101.rsv.ws-scs.jp/web/index.jsp"

DISTRICTS = {
    "麻布地区": "1000_0",
    "赤坂地区": "2000_0",
    "芝地区": "5000_0",
    "高輪地区": "3000_0",
    "芝浦港南地区": "4000_0",
}

PURPOSE = "2010_2010040"

STATE_FILE = Path("state.json")

DISCORD_WEBHOOK_URL = os.environ.get(
    "DISCORD_WEBHOOK_URL"
)


# ------------------------------------------------------------
# ページを開いて検索条件を設定
# ------------------------------------------------------------

def search_district(page, district_name, district_value):

    print(f"\n===== {district_name} =====")

    page.goto(
        URL,
        wait_until="domcontentloaded"
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

    # 利用目的：バドミントン
    page.locator("#purpose").evaluate(
        """(el, value) => {
            el.value = value;
            el.dispatchEvent(
                new Event('change', {bubbles: true})
            );
        }""",
        PURPOSE
    )

    page.wait_for_timeout(500)

    # 時間帯は選択しない
    # → 全時間帯を検索

    page.locator("#btn-go").click()

    page.wait_for_timeout(2000)

    print("検索結果へ移動しました")

    return page


# ------------------------------------------------------------
# 検索結果をすべて表示
# ------------------------------------------------------------

def get_all_results(page, district_name):

    print(
        f"{district_name}: "
        f"検索結果を取得中"
    )

    # 「日付順」をクリック
    try:

        date_order = page.get_by_text(
            "日付順",
            exact=True
        )

        if date_order.count() > 0:

            date_order.first.click()

            page.wait_for_timeout(1200)

            print(
                "日付順へ切り替えました"
            )

    except Exception as e:

        print(
            f"日付順切替エラー: {e}"
        )

    # 「さらに表示」を可能な限り押す
    for i in range(50):

        try:

            more = page.get_by_text(
                "さらに表示",
                exact=True
            )

            if more.count() == 0:
                break

            if not more.first.is_visible():
                break

            before = page.locator(
                "body"
            ).inner_text()

            more.first.click()

            page.wait_for_timeout(1200)

            after = page.locator(
                "body"
            ).inner_text()

            if before == after:
                break

            print(
                f"さらに表示: {i + 1}回目"
            )

        except Exception:

            break

    text = page.locator(
        "body"
    ).inner_text()

    return text


# ------------------------------------------------------------
# 日付を抽出
# ------------------------------------------------------------

def extract_dates(text):

    pattern = (
        r"(\d{1,2}月\d{1,2}日"
        r"\([^)]*\)"
        r"\d{4}年)"
    )

    return re.findall(
        pattern,
        text
    )


# ------------------------------------------------------------
# 時刻を抽出
# ------------------------------------------------------------

def extract_times(text):

    pattern = (
        r"(\d{1,2})時(\d{2})分"
        r"～"
        r"(\d{1,2})時(\d{2})分"
    )

    results = []

    for match in re.finditer(
        pattern,
        text
    ):

        start_h = int(
            match.group(1)
        )

        start_m = int(
            match.group(2)
        )

        end_h = int(
            match.group(3)
        )

        end_m = int(
            match.group(4)
        )

        results.append({

            "start": (
                f"{start_h:02d}:"
                f"{start_m:02d}"
            ),

            "end": (
                f"{end_h:02d}:"
                f"{end_m:02d}"
            ),

            "start_minutes": (
                start_h * 60
                + start_m
            ),

            "end_minutes": (
                end_h * 60
                + end_m
            ),

            "position": match.start(),

            "text": match.group(0),
        })

    return results


# ------------------------------------------------------------
# 施設名・部屋名を推定
# ------------------------------------------------------------

def extract_facility_context(
    text,
    position
):

    before = text[
        max(0, position - 500):
        position
    ]

    lines = [

        line.strip()

        for line in before.splitlines()

        if line.strip()
    ]

    ignore_words = [

        "日付順",
        "施設ごと",
        "さらに表示",
        "予約",
        "空き",
        "検索結果",
        "バドミントン",
    ]

    cleaned = []

    for line in lines:

        if line in ignore_words:
            continue

        if any(
            word in line
            for word in ignore_words
        ):
            continue

        if re.search(
            r"\d{1,2}時\d{2}分",
            line
        ):
            continue

        cleaned.append(line)

    candidates = cleaned[-3:]

    if len(candidates) == 0:

        return (
            "施設名不明",
            "部屋名不明"
        )

    if len(candidates) == 1:

        return (
            candidates[-1],
            "部屋名不明"
        )

    facility = candidates[-2]

    room = candidates[-1]

    return (
        facility,
        room
    )


# ------------------------------------------------------------
# 17:00以降開始の空き枠を抽出
# ------------------------------------------------------------

def extract_evening_slots(
    text,
    district_name
):

    slots = []

    dates = extract_dates(text)

    times = extract_times(text)

    if not dates or not times:
        return slots

    for time_info in times:

        # 17:00開始以上だけ対象
        if time_info[
            "start_minutes"
        ] < 17 * 60:

            continue

        # 時刻の直前にある日付を探す
        preceding_dates = []

        for date in dates:

            date_position = text.find(
                date
            )

            if date_position <= time_info[
                "position"
            ]:

                preceding_dates.append(
                    (
                        date_position,
                        date
                    )
                )

        if preceding_dates:

            _, date = preceding_dates[-1]

        else:

            date = "日付不明"

        facility, room = (
            extract_facility_context(
                text,
                time_info["position"]
            )
        )

        slot = {

            "district":
                district_name,

            "date":
                date,

            "facility":
                facility,

            "room":
                room,

            "start":
                time_info["start"],

            "end":
                time_info["end"],
        }

        slots.append(slot)

    return slots


# ------------------------------------------------------------
# 空き枠を一意に識別
# ------------------------------------------------------------

def make_slot_key(slot):

    return "|".join([

        slot["district"],

        slot["date"],

        slot["facility"],

        slot["room"],

        slot["start"],

        slot["end"],
    ])


# ------------------------------------------------------------
# 前回状態を読み込む
# ------------------------------------------------------------

def load_previous_state():

    if not STATE_FILE.exists():

        return set()

    try:

        data = json.loads(
            STATE_FILE.read_text(
                encoding="utf-8"
            )
        )

        if isinstance(data, list):

            return set(data)

    except Exception as e:

        print(
            f"state.json読み込みエラー: {e}"
        )

    return set()


# ------------------------------------------------------------
# 現在の状態を保存
# ------------------------------------------------------------

def save_current_state(slots):

    keys = sorted(
        set(
            make_slot_key(slot)
            for slot in slots
        )
    )

    STATE_FILE.write_text(

        json.dumps(
            keys,
            ensure_ascii=False,
            indent=2
        ),

        encoding="utf-8"
    )


# ------------------------------------------------------------
# Discord通知
# ------------------------------------------------------------

def send_discord_notification(
    new_slots
):

    if not new_slots:

        print(
            "新規空き枠なし。"
            "Discord通知は行いません。"
        )

        return

    if not DISCORD_WEBHOOK_URL:

        print(
            "DISCORD_WEBHOOK_URLが"
            "設定されていません。"
        )

        return

    lines = []

    lines.append(
        "🏸 **港区バドミントン空き情報**"
    )

    lines.append("")

    lines.append(
        f"17:00以降開始の新しい空き枠が"
        f" {len(new_slots)} 件あります。"
    )

    lines.append("")

    for slot in new_slots:

        lines.append(

            f"📅 **{slot['date']}**\n"
            f"📍 {slot['district']}\n"
            f"🏢 {slot['facility']}\n"
            f"🚪 {slot['room']}\n"
            f"🕐 {slot['start']}～{slot['end']}\n"
        )

    message = "\n".join(lines)

    payload = json.dumps({
        "content": message
    }).encode("utf-8")

    request = urllib.request.Request(

        DISCORD_WEBHOOK_URL,

        data=payload,

        headers={
            "Content-Type":
                "application/json"
        },

        method="POST"
    )

    try:

        with urllib.request.urlopen(
            request,
            timeout=20
        ) as response:

            print(
                "Discord通知成功:"
                f" HTTP {response.status}"
            )

    except Exception as e:

        print(
            f"Discord通知エラー: {e}"
        )


# ------------------------------------------------------------
# 結果ファイル
# ------------------------------------------------------------

def write_evening_results(
    slots
):

    path = Path(
        "evening-results.txt"
    )

    if not slots:

        path.write_text(

            "現在、17:00以降開始の"
            "空き枠はありません。\n",

            encoding="utf-8"
        )

        return

    lines = []

    for slot in slots:

        lines.append(

            f"{slot['district']} | "
            f"{slot['date']} | "
            f"{slot['facility']} | "
            f"{slot['room']} | "
            f"{slot['start']}～"
            f"{slot['end']}"
        )

    path.write_text(

        "\n".join(lines) + "\n",

        encoding="utf-8"
    )


# ------------------------------------------------------------
# 新規枠ファイル
# ------------------------------------------------------------

def write_new_slots(
    new_slots,
    first_run
):

    path = Path(
        "new-slots.txt"
    )

    if first_run:

        path.write_text(

            "初回実行のため、"
            "現在の空き枠を基準値として"
            "登録しました。\n"
            "今回はDiscord通知しません。\n",

            encoding="utf-8"
        )

        return

    if not new_slots:

        path.write_text(

            "新しく出現した"
            "17:00以降開始の空き枠は"
            "ありません。\n",

            encoding="utf-8"
        )

        return

    lines = [

        "===== 新しく出現した空き枠 ====="
    ]

    for slot in new_slots:

        lines.append(

            f"{slot['district']} | "
            f"{slot['date']} | "
            f"{slot['facility']} | "
            f"{slot['room']} | "
            f"{slot['start']}～"
            f"{slot['end']}"
        )

    path.write_text(

        "\n".join(lines) + "\n",

        encoding="utf-8"
    )


# ------------------------------------------------------------
# メイン処理
# ------------------------------------------------------------

def main():

    previous_keys = (
        load_previous_state()
    )

    first_run = (
        not STATE_FILE.exists()
    )

    print(
        "===================================="
    )

    print(
        "港区バドミントン空き状況モニター"
    )

    print(
        "===================================="
    )

    if first_run:

        print(
            "初回実行です。"
            "現在の空き枠を基準値として"
            "登録します。"
        )

    else:

        print(
            f"前回の空き枠数: "
            f"{len(previous_keys)}"
        )

    all_evening_slots = []

    all_results_text = []

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page(

            viewport={
                "width": 1440,
                "height": 1200
            }
        )

        for (
            district_name,
            district_value
        ) in DISTRICTS.items():

            try:

                search_district(

                    page,

                    district_name,

                    district_value
                )

                result_text = (
                    get_all_results(
                        page,
                        district_name
                    )
                )

                all_results_text.append(

                    f"\n\n"
                    f"==============================\n"
                    f"{district_name}\n"
                    f"==============================\n"
                    f"{result_text}"
                )

                try:

                    page.screenshot(

                        path=(
                            f"result_"
                            f"{district_name}.png"
                        ),

                        full_page=True
                    )

                except Exception as e:

                    print(
                        "スクリーンショット保存エラー: "
                        f"{e}"
                    )

                evening_slots = (
                    extract_evening_slots(
                        result_text,
                        district_name
                    )
                )

                print(

                    f"{district_name}: "
                    f"17:00以降開始 "
                    f"{len(evening_slots)}件"
                )

                all_evening_slots.extend(
                    evening_slots
                )

            except Exception as e:

                print(

                    f"{district_name}: "
                    f"エラー発生: {e}"
                )

                try:

                    page.screenshot(

                        path=(
                            f"error_"
                            f"{district_name}.png"
                        ),

                        full_page=True
                    )

                except Exception:
                    pass

        browser.close()

    # --------------------------------------------------------
    # 全検索結果保存
    # --------------------------------------------------------

    Path(
        "all-district-results.txt"
    ).write_text(

        "".join(all_results_text),

        encoding="utf-8"
    )

    # --------------------------------------------------------
    # 重複除去
    # --------------------------------------------------------

    unique_slots = {}

    for slot in all_evening_slots:

        key = make_slot_key(slot)

        unique_slots[key] = slot

    current_slots = list(
        unique_slots.values()
    )

    current_keys = set(
        unique_slots.keys()
    )

    # --------------------------------------------------------
    # 新規枠判定
    # --------------------------------------------------------

    new_keys = (
        current_keys
        - previous_keys
    )

    new_slots = [

        slot

        for slot in current_slots

        if make_slot_key(slot)
        in new_keys
    ]

    # 並び順
    current_slots.sort(

        key=lambda x: (

            x["date"],
            x["start"],
            x["district"],
            x["facility"],
            x["room"],
        )
    )

    new_slots.sort(

        key=lambda x: (

            x["date"],
            x["start"],
            x["district"],
            x["facility"],
            x["room"],
        )
    )

    # --------------------------------------------------------
    # 結果ファイル
    # --------------------------------------------------------

    write_evening_results(
        current_slots
    )

    write_new_slots(
        new_slots,
        first_run
    )

    # --------------------------------------------------------
    # Discord通知
    #
    # 初回は基準値登録だけ。
    # 2回目以降、新規枠があった場合のみ通知。
    # --------------------------------------------------------

    if not first_run:

        send_discord_notification(
            new_slots
        )

    else:

        print(
            "初回実行のため、"
            "Discord通知は行いません。"
        )

    # --------------------------------------------------------
    # 状態保存
    # --------------------------------------------------------

    save_current_state(
        current_slots
    )

    # --------------------------------------------------------
    # コンソール表示
    # --------------------------------------------------------

    print("")

    print(
        "===================================="
    )

    print("処理結果")

    print(
        "===================================="
    )

    print(

        f"現在の17:00以降開始枠: "
        f"{len(current_slots)}件"
    )

    print(

        f"新しく出現した枠: "
        f"{len(new_slots)}件"
    )

    if new_slots:

        print("")

        print(
            "===== 新規空き枠 ====="
        )

        for slot in new_slots:

            print(

                f"{slot['district']} | "
                f"{slot['date']} | "
                f"{slot['facility']} | "
                f"{slot['room']} | "
                f"{slot['start']}～"
                f"{slot['end']}"
            )

    print("")

    print(
        "state.jsonを更新しました。"
    )

    print(
        "===================================="
    )


if __name__ == "__main__":

    main()
