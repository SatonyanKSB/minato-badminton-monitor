import os
import json
import re
import urllib.request
import urllib.error
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


# =========================================================
# Discord通知
# =========================================================

def send_discord_notification(new_slots):

    if not DISCORD_WEBHOOK_URL:
        print("DISCORD_WEBHOOK_URL が設定されていません。")
        return

    if not new_slots:
        print("新しい空き枠がないためDiscord通知はしません。")
        return

    lines = [
        "🏸 **港区バドミントン空き情報**",
        "",
        f"17:00以降開始の新しい空き枠が {len(new_slots)} 件あります。",
        "",
    ]

    for slot in new_slots:

        lines.append(f"📅 {slot['date']}")
        lines.append(f"📍 {slot['district']}")
        lines.append(f"🏢 {slot['facility']}")
        lines.append(f"🏸 {slot['room']}")
        lines.append(f"⏰ {slot['start']}〜{slot['end']}")
        lines.append("")

    message = "\n".join(lines)

    payload = json.dumps({
        "content": message
    }).encode("utf-8")

    request = urllib.request.Request(
        DISCORD_WEBHOOK_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "Minato-Badminton-Monitor"
        },
        method="POST"
    )

    try:

        with urllib.request.urlopen(
            request,
            timeout=20
        ) as response:

            print(
                f"Discord通知成功: HTTP {response.status}"
            )

    except urllib.error.HTTPError as e:

        print(
            f"Discord通知失敗: HTTP {e.code}"
        )

        try:

            body = e.read().decode(
                "utf-8",
                errors="replace"
            )

            print(
                f"Discordエラー内容: {body}"
            )

        except Exception:
            pass

    except Exception as e:

        print(
            f"Discord通知に失敗しました: {e}"
        )


# =========================================================
# state.json
# =========================================================

def load_previous_state():

    if not os.path.exists(STATE_FILE):

        print(
            "state.json がありません。初回実行です。"
        )

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

    return "|".join([
        slot["district"],
        slot["date"],
        slot["facility"],
        slot["room"],
        slot["start"],
        slot["end"],
    ])


# =========================================================
# 17:00以降か
# =========================================================

def is_evening_slot(start_time):

    hour, minute = map(
        int,
        start_time.split(":")
    )

    return (
        hour * 60 + minute
        >= 17 * 60
    )


# =========================================================
# バドミントンを選択
# =========================================================

def select_badminton(page):

    print(
        "バドミントンの選択を開始します。"
    )

    # -----------------------------------------------------
    # 方法1：selectのoptionから「バドミントン」を探す
    # -----------------------------------------------------

    selects = page.locator("select")

    print(
        f"select要素数: {selects.count()}"
    )

    for i in range(selects.count()):

        select = selects.nth(i)

        try:

            options = select.locator("option")

            for j in range(options.count()):

                option = options.nth(j)

                text = option.inner_text().strip()
                value = option.get_attribute("value")

                if text == "バドミントン":

                    print(
                        f"バドミントンをselectから発見: "
                        f"select={i}, value={value}"
                    )

                    select.select_option(
                        value=value
                    )

                    page.wait_for_timeout(500)

                    print(
                        "バドミントン選択成功"
                    )

                    return True

        except Exception:
            pass

    # -----------------------------------------------------
    # 方法2：optionに「バドミントン」を含むものを探す
    # -----------------------------------------------------

    try:

        badminton_options = page.locator(
            "option"
        ).filter(
            has_text="バドミントン"
        )

        if badminton_options.count() > 0:

            option = badminton_options.first

            value = option.get_attribute(
                "value"
            )

            parent = option.locator(
                "xpath=.."
            )

            print(
                f"バドミントンoption発見: value={value}"
            )

            parent.select_option(
                value=value
            )

            page.wait_for_timeout(500)

            print(
                "バドミントン選択成功"
            )

            return True

    except Exception as e:

        print(
            f"option方式エラー: {e}"
        )

    # -----------------------------------------------------
    # 方法3：labelから探す
    # -----------------------------------------------------

    try:

        labels = page.locator(
            "label"
        )

        for i in range(labels.count()):

            label = labels.nth(i)

            text = label.inner_text().strip()

            if text == "バドミントン":

                print(
                    "バドミントンをlabelから発見"
                )

                label.click()

                page.wait_for_timeout(500)

                print(
                    "バドミントン選択成功"
                )

                return True

    except Exception as e:

        print(
            f"label方式エラー: {e}"
        )

    # -----------------------------------------------------
    # 方法4：inputのvalueを探す
    # -----------------------------------------------------

    try:

        inputs = page.locator(
            "input"
        )

        for i in range(inputs.count()):

            element = inputs.nth(i)

            value = element.get_attribute(
                "value"
            )

            element_id = element.get_attribute(
                "id"
            )

            name = element.get_attribute(
                "name"
            )

            if (
                value == "2010_2010040"
                or element_id == "2010_2010040"
                or name == "2010_2010040"
            ):

                print(
                    "バドミントンinputを発見"
                )

                try:
                    element.check()
                except Exception:
                    element.click()

                page.wait_for_timeout(500)

                print(
                    "バドミントン選択成功"
                )

                return True

    except Exception as e:

        print(
            f"input方式エラー: {e}"
        )

    # -----------------------------------------------------
    # 失敗
    # -----------------------------------------------------

    print("")
    print(
        "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    )
    print(
        "バドミントンを選択できませんでした。"
    )
    print(
        "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    )

    # 画面上に存在する「何をする」関連の情報をログ出力
    try:

        print("")
        print(
            "現在のselectの選択肢を確認します。"
        )

        for i in range(selects.count()):

            select = selects.nth(i)

            try:

                options = select.locator(
                    "option"
                )

                texts = []

                for j in range(
                    min(options.count(), 30)
                ):

                    texts.append(
                        options.nth(j).inner_text().strip()
                    )

                print(
                    f"select {i}: {texts}"
                )

            except Exception:
                pass

    except Exception:
        pass

    return False


# =========================================================
# 「さらに表示」を全部押す
# =========================================================

def get_all_results(page):

    print(
        "検索結果を読み込みます。"
    )

    previous_text = ""

    for i in range(50):

        print(
            f"「さらに表示」確認 {i + 1}回目"
        )

        buttons = page.get_by_text(
            "さらに表示",
            exact=True
        )

        if buttons.count() == 0:

            print(
                "「さらに表示」はありません。"
            )

            break

        clicked = False

        for j in range(buttons.count()):

            try:

                button = buttons.nth(j)

                if button.is_visible():

                    print(
                        "「さらに表示」をクリックします。"
                    )

                    button.click()

                    page.wait_for_timeout(
                        1000
                    )

                    clicked = True

                    break

            except Exception:
                pass

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

    return page.locator(
        "body"
    ).inner_text()


# =========================================================
# 1地区を検索
# =========================================================

def search_district(
    page,
    district_name,
    district_value
):

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
    # 期間：1か月
    # -----------------------------------------------------

    try:

        days = page.locator(
            "#days"
        )

        if days.count() > 0:

            days.evaluate(
                """
                (el) => {
                    el.value = "31";
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
                "検索期間: 1か月"
            )

    except Exception as e:

        print(
            f"検索期間設定エラー: {e}"
        )

    # -----------------------------------------------------
    # 時間帯
    # -----------------------------------------------------

    print(
        "時間帯: 指定なし（全時間帯）"
    )

    # -----------------------------------------------------
    # 地区
    # -----------------------------------------------------

    selects = page.locator(
        "select"
    )

    district_found = False

    for i in range(
        selects.count()
    ):

        select = selects.nth(i)

        try:

            options = select.locator(
                "option"
            )

            for j in range(
                options.count()
            ):

                option = options.nth(j)

                value = option.get_attribute(
                    "value"
                )

                text = option.inner_text().strip()

                if (
                    value == district_value
                    or district_name in text
                ):

                    select.select_option(
                        value=value
                    )

                    page.wait_for_timeout(
                        500
                    )

                    district_found = True

                    print(
                        f"地区設定: {district_name}"
                    )

                    break

            if district_found:
                break

        except Exception:
            pass

    if not district_found:

        raise RuntimeError(
            f"{district_name}を選択できませんでした。"
        )

    # -----------------------------------------------------
    # バドミントン
    # -----------------------------------------------------

    if not select_badminton(page):

        raise RuntimeError(
            "バドミントンを選択できませんでした。"
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

            buttons = page.get_by_text(
                label,
                exact=True
            )

            for i in range(
                buttons.count()
            ):

                button = buttons.nth(i)

                if button.is_visible():

                    print(
                        f"検索ボタン: {label}"
                    )

                    button.click()

                    clicked_search = True

                    break

            if clicked_search:
                break

        except Exception:
            pass

    if not clicked_search:

        try:

            buttons = page.locator(
                'button[type="submit"], input[type="submit"]'
            )

            if buttons.count() > 0:

                buttons.first.click()

                clicked_search = True

        except Exception:
            pass

    if not clicked_search:

        raise RuntimeError(
            "検索ボタンを見つけられませんでした。"
        )

    page.wait_for_timeout(
        2000
    )

    # -----------------------------------------------------
    # 日付順
    # -----------------------------------------------------

    try:

        date_order = page.get_by_text(
            "日付順",
            exact=True
        )

        for i in range(
            date_order.count()
        ):

            item = date_order.nth(i)

            if item.is_visible():

                print(
                    "「日付順」をクリック"
                )

                item.click()

                page.wait_for_timeout(
                    1000
                )

                break

    except Exception as e:

        print(
            f"日付順クリックエラー: {e}"
        )

    # -----------------------------------------------------
    # 全結果
    # -----------------------------------------------------

    return get_all_results(
        page
    )


# =========================================================
# 空き枠解析
# =========================================================

def parse_evening_slots(
    body_text,
    district_name
):

    slots = []

    lines = [
        line.strip()
        for line in body_text.splitlines()
        if line.strip()
    ]

    current_date = None

    for i, line in enumerate(lines):

        # -------------------------------------------------
        # 日付
        # -------------------------------------------------

        date_match = re.search(
            r"\d{1,2}月\d{1,2}日",
            line
        )

        if date_match:

            current_date = line

        # -------------------------------------------------
        # 時間帯
        # -------------------------------------------------

        time_matches = re.findall(
            r"(\d{1,2}:\d{2})\s*[〜～-]\s*(\d{1,2}:\d{2})",
            line
        )

        if not time_matches:
            continue

        for start, end in time_matches:

            if not is_evening_slot(
                start
            ):
                continue

            # -------------------------------------------------
            # 周辺文字
            # -------------------------------------------------

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

            # -------------------------------------------------
            # 施設名
            # -------------------------------------------------

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

            # -------------------------------------------------
            # 部屋名
            # -------------------------------------------------

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

            slots.append(
                {
                    "district": district_name,
                    "date": current_date or "日付不明",
                    "facility": facility,
                    "room": room,
                    "start": start,
                    "end": end,
                }
            )

    return slots


# =========================================================
# メイン
# =========================================================

def main():

    print("")
    print("=" * 60)
    print("港区バドミントン空き情報監視")
    print("=" * 60)

    state_exists = os.path.exists(
        STATE_FILE
    )

    previous_keys = load_previous_state()

    print(
        f"前回登録済み空き枠: {len(previous_keys)}件"
    )

    all_slots = []

   
