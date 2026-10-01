import os
import json
import re
import urllib.request
from datetime import datetime
from playwright.sync_api import sync_playwright


# =========================================================
# 設定
# =========================================================

URL = "https://web101.rsv.ws-scs.jp/web/index.jsp"

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

STATE_FILE = "state.json"

DISTRICTS = [
    ("麻布地区", "1000_0"),
    ("赤坂地区", "2000_0"),
    ("芝地区", "5000_0"),
    ("高輪地区", "3000_0"),
    ("芝浦港南地区", "4000_0"),
]

PURPOSE_VALUE = "2010_2010040"


# =========================================================
# Discord通知
# =========================================================

def send_discord_notification(new_slots):
    """
    新しく見つかった空き枠をDiscordへ通知する
    """

    if not DISCORD_WEBHOOK_URL:
        print("DISCORD_WEBHOOK_URL が設定されていません。")
        return

    if not new_slots:
        print("新しい空き枠がないため、Discord通知はしません。")
        return

    message_lines = [
        "🏸 **港区バドミントン空き情報**",
        "",
        f"17:00以降開始の新しい空き枠が {len(new_slots)} 件あります。",
        "",
    ]

    for slot in new_slots:
        message_lines.append(
            f"📅 {slot['date']}"
        )
        message_lines.append(
            f"📍 {slot['district']}"
        )
        message_lines.append(
            f"🏢 {slot['facility']}"
        )
        message_lines.append(
            f"🏸 {slot['room']}"
        )
        message_lines.append(
            f"⏰ {slot['start']}〜{slot['end']}"
        )
        message_lines.append("")

    message = "\n".join(message_lines)

    payload = json.dumps({
        "content": message
    }).encode("utf-8")

    request = urllib.request.Request(
        DISCORD_WEBHOOK_URL,
        data=payload,
        headers={
            "Content-Type": "application/json"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            print(
                f"Discord通知成功: HTTP {response.status}"
            )

    except Exception as e:
        print(
            f"Discord通知に失敗しました: {e}"
        )


# =========================================================
# 状態保存
# =========================================================

def load_previous_state():
    """
    前回確認した空き枠一覧を読み込む
    """

    if not os.path.exists(STATE_FILE):
        print("state.json がありません。初回実行です。")
        return set()

    try:
        with open(
            STATE_FILE,
            "r",
            encoding="utf-8"
        ) as f:
            data = json.load(f)

        return set(data)

    except Exception as e:
        print(
            f"state.json の読み込みに失敗しました: {e}"
        )
        return set()


def save_current_state(current_keys):
    """
    今回確認した空き枠一覧を保存する
    """

    with open(
        STATE_FILE,
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            sorted(current_keys),
            f,
            ensure_ascii=False,
            indent=2
        )


# =========================================================
# 空き枠キー
# =========================================================

def make_slot_key(slot):
    """
    空き枠を一意に識別するための文字列を作る
    """

    return "|".join([
        slot["district"],
        slot["date"],
        slot["facility"],
        slot["room"],
        slot["start"],
        slot["end"],
    ])


# =========================================================
# 日付抽出
# =========================================================

def extract_dates(text):
    """
    ページ内テキストから日付を抽出する
    """

    patterns = [
        r"(\d{1,2}月\d{1,2}日(?:\([月火水木金土日]\))?(?:\d{4}年)?)",
        r"(\d{4}年\d{1,2}月\d{1,2}日)",
    ]

    dates = []

    for pattern in patterns:
        matches = re.findall(pattern, text)

        for match in matches:
            if match not in dates:
                dates.append(match)

    return dates


# =========================================================
# 時刻抽出
# =========================================================

def extract_times(text):
    """
    ページ内テキストから時間帯を抽出する
    """

    pattern = r"(\d{1,2}:\d{2})\s*[〜～-]\s*(\d{1,2}:\d{2})"

    return re.findall(pattern, text)


# =========================================================
# 17:00以降開始か判定
# =========================================================

def is_evening_slot(start_time):
    """
    開始時刻が17:00以降ならTrue
    """

    hour, minute = map(
        int,
        start_time.split(":")
    )

    total_minutes = hour * 60 + minute

    return total_minutes >= 17 * 60


# =========================================================
# 「さらに表示」を全部押す
# =========================================================

def get_all_results(page):
    """
    検索結果の「さらに表示」を可能な限り全部押す
    """

    print("検索結果を読み込みます。")

    previous_text = ""

    for i in range(50):

        body_text = page.locator("body").inner_text()

        print(
            f"さらに表示確認 {i + 1}回目"
        )

        # 「さらに表示」があればクリック
        buttons = page.get_by_text(
            "さらに表示",
            exact=True
        )

        count = buttons.count()

        if count == 0:
            print(
                "「さらに表示」はありません。"
            )
            break

        clicked = False

        for j in range(count):
            try:
                button = buttons.nth(j)

                if button.is_visible():
                    print(
                        "「さらに表示」をクリックします。"
                    )

                    button.click()

                    page.wait_for_timeout(1000)

                    clicked = True

                    break

            except Exception as e:
                print(
                    f"クリック失敗: {e}"
                )

        if not clicked:
            break

        new_text = page.locator(
            "body"
        ).inner_text()

        if new_text == previous_text:
            print(
                "画面内容が変わらなくなりました。"
            )
            break

        previous_text = new_text

    return page.locator("body").inner_text()


# =========================================================
# 1地区を検索
# =========================================================

def search_district(
    page,
    district_name,
    district_value
):
    """
    1つの地区を検索する
    """

    print("")
    print("=" * 60)
    print(
        f"検索開始: {district_name}"
    )
    print("=" * 60)

    page.goto(
        URL,
        wait_until="networkidle",
        timeout=60000
    )

    page.wait_for_timeout(1000)

    # -----------------------------------------------------
    # 日付
    # -----------------------------------------------------

    try:
        days = page.locator("#days")

        if days.count() > 0:
            days.evaluate(
                """
                (el) => {
                    el.value = "31";
                    el.dispatchEvent(
                        new Event("change", {bubbles: true})
                    );
                }
                """
            )

            print(
                "検索期間: 1か月"
            )

    except Exception as e:
        print(
            f"検索期間設定エラー: {e}"
        )

    # -----------------------------------------------------
    # 曜日
    # -----------------------------------------------------

    # 曜日は指定しない
    print(
        "曜日: 指定なし"
    )

    # -----------------------------------------------------
    # 時間帯
    # -----------------------------------------------------

    # 時間帯は一切選択しない
    print(
        "時間帯: 指定なし（全時間帯）"
    )

    # -----------------------------------------------------
    # 地区
    # -----------------------------------------------------

    try:
        district_select = page.locator(
            "select"
        ).filter(
            has_text=district_name
        )

        if district_select.count() > 0:
            district_select.first.select_option(
                district_value
            )

        else:
            # valueから探す
            selects = page.locator(
                "select"
            )

            found = False

            for i in range(selects.count()):

                select = selects.nth(i)

                try:
                    options = select.locator(
                        "option"
                    )

                    for j in range(options.count()):

                        option = options.nth(j)

                        value = option.get_attribute(
                            "value"
                        )

                        text = option.inner_text()

                        if value == district_value:
                            select.select_option(
                                value
                            )

                            found = True

                            print(
                                f"地区設定: {district_name}"
                            )

                            break

                    if found:
                        break

                except Exception:
                    pass

    except Exception as e:
        print(
            f"地区設定エラー: {e}"
        )

    # -----------------------------------------------------
    # 目的
    # -----------------------------------------------------

    try:
        purpose = page.locator(
            f'input[value="{PURPOSE_VALUE}"]'
        )

        if purpose.count() > 0:

            try:
                purpose.check()

            except Exception:
                purpose.evaluate(
                    """
                    (el) => {
                        el.checked = true;
                        el.dispatchEvent(
                            new Event(
                                "change",
                                {bubbles: true}
                            )
                        );
                    }
                    """
                )

            print(
                "目的: バドミントン"
            )

    except Exception as e:
        print(
            f"目的設定エラー: {e}"
        )

    # -----------------------------------------------------
    # 検索
    # -----------------------------------------------------

    search_candidates = [
        "検索",
        "この条件で検索",
        "空き状況を検索",
    ]

    clicked_search = False

    for label in search_candidates:

        try:
            button = page.get_by_text(
                label,
                exact=True
            )

            if button.count() > 0:

                for i in range(button.count()):

                    b = button.nth(i)

                    if b.is_visible():

                        print(
                            f"検索ボタン: {label}"
                        )

                        b.click()

                        clicked_search = True

                        break

                if clicked_search:
                    break

        except Exception:
            pass

    if not clicked_search:

        # submitボタンを試す
        try:
            buttons = page.locator(
                'button[type="submit"], input[type="submit"]'
            )

            if buttons.count() > 0:

                buttons.first.click()

                clicked_search = True

        except Exception as e:
            print(
                f"submitクリック失敗: {e}"
            )

    if not clicked_search:
        raise RuntimeError(
            "検索ボタンを見つけられませんでした。"
        )

    page.wait_for_timeout(2000)

    # -----------------------------------------------------
    # 日付順
    # -----------------------------------------------------

    try:
        date_order = page.get_by_text(
            "日付順",
            exact=True
        )

        if date_order.count() > 0:

            for i in range(date_order.count()):

                item = date_order.nth(i)

                if item.is_visible():

                    print(
                        "「日付順」をクリック"
                    )

                    item.click()

                    page.wait_for_timeout(1000)

                    break

    except Exception as e:
        print(
            f"日付順クリックエラー: {e}"
        )

    # -----------------------------------------------------
    # 全結果を取得
    # -----------------------------------------------------

    body_text = get_all_results(page)

    return body_text


# =========================================================
# 結果解析
# =========================================================

def parse_evening_slots(
    body_text,
    district_name
):
    """
    検索結果から17:00以降開始の枠を抽出する
    """

    slots = []

    lines = [
        line.strip()
        for line in body_text.splitlines()
        if line.strip()
    ]

    current_date = None

    for i, line in enumerate(lines):

        # -----------------------------------------------
        # 日付らしい行
        # -----------------------------------------------

        date_match = re.search(
            r"\d{1,2}月\d{1,2}日",
            line
        )

        if date_match:
            current_date = line

        # -----------------------------------------------
        # 時間帯
        # -----------------------------------------------

        time_matches = re.findall(
            r"(\d{1,2}:\d{2})\s*[〜～-]\s*(\d{1,2}:\d{2})",
            line
        )

        if not time_matches:
            continue

        for start, end in time_matches:

            if not is_evening_slot(start):
                continue

            # ------------------------------------------------
            # 周辺テキストから施設名・部屋名を推測
            # ------------------------------------------------

            context_start = max(
                0,
                i - 8
            )

            context_end = min(
                len(lines),
                i + 3
            )

            context = lines[
                context_start:context_end
            ]

            facility = "施設名不明"
            room = "部屋名不明"

            # 「体育館」「競技場」などを施設名候補にする
            for text in context:

                if any(
                    word in text
                    for word in [
                        "体育館",
                        "スポーツセンター",
                        "運動場",
                        "学校",
                        "区民センター",
                        "プラザ",
                    ]
                ):
                    facility = text
                    break

            # 部屋名候補
            for text in context:

                if any(
                    word in text
                    for word in [
                        "全面",
                        "半面",
                        "A面",
                        "B面",
                        "コート",
                        "競技場",
                    ]
                ):
                    room = text
                    break

            slot = {
                "district": district_name,
                "date": current_date or "日付不明",
                "facility": facility,
                "room": room,
                "start": start,
                "end": end,
            }

            slots.append(slot)

    return slots


# =========================================================
# テスト用Discord通知
# =========================================================

def discord_test():
    """
    Discord通知だけをテストする
    """

    test_slot = {
        "district": "テスト地区",
        "date": "10月1日(木曜)2026年",
        "facility": "テスト体育館",
        "room": "テストコート",
        "start": "18:00",
        "end": "20:00",
    }

    print("")
    print("=" * 60)
    print("Discord通知テスト")
    print("=" * 60)

    send_discord_notification(
        [test_slot]
    )

    print(
        "Discord通知テストを実行しました。"
    )


# =========================================================
# メイン処理
# =========================================================

def main():

    # =====================================================
    # ★★★★★
    # ★ Discord通知テスト中
    # ★
    # ★ Discordにテスト通知が届くことを確認したら、
    # ★ このブロックを削除してください。
    # ★★★★★
    # =====================================================

    discord_test()

    return

    # =====================================================
    # ↓↓↓ 本番処理 ↓↓↓
    # =====================================================

    previous_keys = load_previous_state()

    all_slots = []

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page(
            viewport={
                "width": 1440,
                "height": 1000,
            }
        )

        try:

            for district_name, district_value in DISTRICTS:

                try:

                    body_text = search_district(
                        page,
                        district_name,
                        district_value
                    )

                    # ------------------------------------------------
                    # 結果保存
                    # ------------------------------------------------

                    filename = (
                        f"result_"
                        f"{district_name.replace('地区', '')}.txt"
                    )

                    with open(
                        filename,
                        "w",
                        encoding="utf-8"
                    ) as f:
                        f.write(body_text)

                    # ------------------------------------------------
                    # 17:00以降を抽出
                    # ------------------------------------------------

                    slots = parse_evening_slots(
                        body_text,
                        district_name
                    )

                    print(
                        f"{district_name}: "
                        f"{len(slots)}件の17:00以降開始枠"
                    )

                    all_slots.extend(
                        slots
                    )

                except Exception as e:

                    print(
                        f"{district_name} の検索でエラー: {e}"
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

        finally:

            browser.close()

    # =====================================================
    # 重複除去
    # =====================================================

    unique_slots = {}

    for slot in all_slots:

        key = make_slot_key(slot)

        unique_slots[key] = slot

    all_slots = list(
        unique_slots.values()
    )

    # =====================================================
    # evening-results.txt
    # =====================================================

    with open(
        "evening-results.txt",
        "w",
        encoding="utf-8"
    ) as f:

        if not all_slots:

            f.write(
                "17:00以降開始の空き枠はありませんでした。\n"
            )

        else:

            for slot in all_slots:

                f.write(
                    f"{slot['district']} | "
                    f"{slot['date']} | "
                    f"{slot['facility']} | "
                    f"{slot['room']} | "
                    f"{slot['start']}〜{slot['end']}\n"
                )

    # =====================================================
    # 今回のキー
    # =====================================================

    current_keys = {
        make_slot_key(slot)
        for slot in all_slots
    }

    # =====================================================
    # 初回かどうか
    # =====================================================

    first_run = not os.path.exists(
        STATE_FILE
    )

    # =====================================================
    # 新しく出現した枠
    # =====================================================

    new_keys = (
        current_keys - previous_keys
    )

    new_slots = [
        slot
        for slot in all_slots
        if make_slot_key(slot) in new_keys
    ]

    # =====================================================
    # new-slots.txt
    # =====================================================

    with open(
        "new-slots.txt",
        "w",
        encoding="utf-8"
    ) as f:

        if first_run:

            f.write(
                "初回実行のため、通知対象はありません。\n"
            )

        elif not new_slots:

            f.write(
                "新しく出現した空き枠はありませんでした。\n"
            )

        else:

            for slot in new_slots:

                f.write(
                    f"{slot['district']} | "
                    f"{slot['date']} | "
                    f"{slot['facility']} | "
                    f"{slot['room']} | "
                    f"{slot['start']}〜{slot['end']}\n"
                )

    # =====================================================
    # Discord通知
    # =====================================================

    if first_run:

        print(
            "初回実行なのでDiscord通知はしません。"
        )

    elif new_slots:

        print(
            f"{len(new_slots)}件の新規空き枠をDiscord通知します。"
        )

        send_discord_notification(
            new_slots
        )

    else:

        print(
            "新しい空き枠がないためDiscord通知はしません。"
        )

    # =====================================================
    # state.json更新
    # =====================================================

    save_current_state(
        current_keys
    )

    # =====================================================
    # 結果表示
    # =====================================================

    print("")
    print("=" * 60)
    print("監視終了")
    print("=" * 60)

    print(
        f"17:00以降開始の枠: {len(all_slots)}件"
    )

    print(
        f"新しく出現した枠: {len(new_slots)}件"
    )


# =========================================================
# 実行
# =========================================================

if __name__ == "__main__":
    main()
