import os
import json
import re
import time
from datetime import datetime
from urllib.request import Request, urlopen

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


URL = "https://web101.rsv.ws-scs.jp/web/index.jsp"

DISTRICTS = [
    "麻布地区",
    "赤坂地区",
    "芝地区",
    "高輪地区",
    "芝浦港南地区",
]

STATE_FILE = "state.json"
NEW_FILE = "new-slots.txt"
EVENING_FILE = "evening-results.txt"

# 17:00ちょうどを含め、それ以降に「開始」する枠だけ通知対象
START_HOUR = 17


def normalize_text(text):
    """全角スペース等を整理し、比較しやすくする。"""
    text = text.replace("\u3000", " ")
    text = text.replace("\xa0", " ")
    return re.sub(r"[ \t]+", " ", text).strip()


def load_state():
    if not os.path.exists(STATE_FILE):
        return set()

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return set(str(x) for x in data)
    except Exception as e:
        print(f"state.json読み込みエラー: {e}")

    return set()


def save_state(state):
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(sorted(state), f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_FILE)


def send_discord(message):
    webhook = os.environ.get("DISCORD_WEBHOOK_URL")

    if not webhook:
        print("DISCORD_WEBHOOK_URLが設定されていないためDiscord通知をスキップします。")
        return False

    payload = json.dumps({"content": message}, ensure_ascii=False).encode("utf-8")
    req = Request(
        webhook,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(req, timeout=20) as response:
            print(f"Discord送信成功: HTTP {response.status}")
            return 200 <= response.status < 300
    except Exception as e:
        print(f"Discord送信エラー: {e}")
        return False


def select_district(page, district):
    """地区のselectを見つけ、指定地区を選択する。"""
    selects = page.locator("select")
    count = selects.count()

    # まず、地区名をoptionとして持っているselectを探す
    for i in range(count):
        select = selects.nth(i)
        try:
            options = select.locator("option").all_text_contents()
            if any(district in normalize_text(x) for x in options):
                option = select.locator("option").filter(has_text=district).first
                value = option.get_attribute("value")
                if value:
                    select.select_option(value=value)
                else:
                    select.select_option(label=district)
                page.wait_for_timeout(800)
                print(f"地区設定成功: {district}")
                return
        except Exception:
            continue

    # フォールバック：labelで探す
    labels = page.locator("label")
    for i in range(labels.count()):
        try:
            txt = normalize_text(labels.nth(i).inner_text())
            if district in txt:
                for attr in ("for",):
                    target_id = labels.nth(i).get_attribute(attr)
                    if target_id:
                        page.locator(f"#{target_id}").select_option(label=district)
                        page.wait_for_timeout(800)
                        print(f"地区設定成功(label): {district}")
                        return
        except Exception:
            continue

    raise RuntimeError(f"{district} の選択肢を見つけられませんでした。")


def select_badminton(page):
    print("バドミントンの選択を開始します。")

    selects = page.locator("select")
    count = selects.count()
    print(f"select要素数: {count}")

    # 現在のサイトでは「何をする」がselect要素。
    # optionの表示文字を直接調べる。
    for i in range(count):
        select = selects.nth(i)
        try:
            options = select.locator("option").all()
            for option in options:
                text = normalize_text(option.inner_text())
                if text == "バドミントン" or "バドミントン" in text:
                    value = option.get_attribute("value")
                    print(f"バドミントンをselectから発見: select={i}, value={value}")

                    if value:
                        select.select_option(value=value)
                    else:
                        select.select_option(label=text)

                    page.wait_for_timeout(500)
                    print("バドミントン選択成功")
                    return
        except Exception:
            continue

    # 念のため従来のvalueも試す
    for selector in [
        'input[value="2010_2010040"]',
        '#2010_2010040',
        '[name="2010_2010040"]',
    ]:
        try:
            loc = page.locator(selector).first
            if loc.count() > 0:
                loc.check()
                page.wait_for_timeout(500)
                print(f"バドミントン選択成功: {selector}")
                return
        except Exception:
            pass

    # 失敗時はselectの中身をログに残す
    print("バドミントンを選択できませんでした。現在のselect内容:")
    for i in range(count):
        try:
            print(f"--- select {i} ---")
            for text in selects.nth(i).locator("option").all_text_contents():
                print(repr(normalize_text(text)))
        except Exception:
            pass

    raise RuntimeError("バドミントンの選択肢を見つけられませんでした。")


def click_search(page):
    # 「検索」という文字を持つボタン/リンクを探す
    candidates = [
        page.get_by_role("button", name="検索", exact=True),
        page.get_by_role("link", name="検索", exact=True),
        page.locator("input[type='submit'][value='検索']"),
        page.locator("button").filter(has_text="検索"),
        page.locator("a").filter(has_text="検索"),
    ]

    for loc in candidates:
        try:
            if loc.count() > 0:
                loc.first.click()
                print("検索ボタン: 検索")
                page.wait_for_load_state("domcontentloaded", timeout=15000)
                page.wait_for_timeout(1200)
                return
        except Exception:
            continue

    raise RuntimeError("検索ボタンを見つけられませんでした。")


def click_date_order(page):
    """検索結果の「日付順」をクリックする。"""
    candidates = [
        page.get_by_text("日付順", exact=True),
        page.get_by_role("link", name="日付順", exact=True),
        page.locator("a").filter(has_text="日付順"),
        page.locator("button").filter(has_text="日付順"),
    ]

    for loc in candidates:
        try:
            if loc.count() > 0:
                loc.first.click()
                page.wait_for_timeout(1000)
                print("「日付順」をクリック")
                return
        except Exception:
            continue

    print("「日付順」が見つからないため、そのまま続行します。")


def get_all_results(page):
    """「さらに表示」を最後まで押して、検索結果全体を取得する。"""
    print("検索結果を読み込みます。")

    # 最初の結果が描画されるまで少し待つ
    page.wait_for_timeout(1500)

    for n in range(1, 31):
        print(f"「さらに表示」確認 {n}回目")

        buttons = page.get_by_text("さらに表示", exact=True)
        if buttons.count() == 0:
            # DOM上の別要素も確認
            buttons = page.locator("a,button").filter(has_text="さらに表示")

        if buttons.count() == 0:
            break

        try:
            button = buttons.first
            if not button.is_visible():
                break

            before = normalize_text(page.locator("body").inner_text())
            print("「さらに表示」をクリックします。")
            button.click()
            page.wait_for_timeout(1200)

            after = normalize_text(page.locator("body").inner_text())
            if after == before:
                break
        except Exception:
            break

    return page.locator("body").inner_text()


DATE_RE = re.compile(r"^(\d{1,2})月(\d{1,2})日")


def parse_available_rows(body_text, district):
    """
    検索結果のHTML本文から、日付・館・施設・時間帯を抽出する。

    このサイトでは、実際の検索結果が
        スポーツセンター\tアリーナ半面Ａ
        09時00分～11時00分
    のように「館」と「施設」が同じ行にタブ区切りで入る。
    そのため、単純に改行だけで分割せず、タブ区切りを優先して解析する。
    """
    raw_lines = body_text.replace("\r", "\n").split("\n")
    lines = [x.replace("\u3000", " ").replace("\xa0", " ").strip() for x in raw_lines]

    results = []
    current_date = None

    date_re = re.compile(r"^(\d{1,2})月(\d{1,2})日")
    time_re = re.compile(r"^(\d{1,2})時(\d{2})分～(\d{1,2})時(\d{2})分$")

    bad = {
        "しせつよやく", "ログイン", "ホーム", "予約", "抽選",
        "利用者", "その他", "空き状況", "ヘルプ", "指定条件",
        "条件変更", "施設ごと", "日付順", "館", "施設", "時間帯",
        "すべて開く", "すべて閉じる",
    }

    for i, line in enumerate(lines):
        if not line:
            continue

        # 日付行
        m = date_re.match(line)
        if m:
            current_date = f"{m.group(1)}月{m.group(2)}日"
            continue

        if current_date is None:
            continue

        # 「館\t施設」のデータ行を探し、その直後の時間帯を対応させる。
        # 実際のinner_textではタブが残るため、ここを直接利用する。
        if "\t" not in line:
            continue

        parts = [normalize_text(x) for x in line.split("\t") if normalize_text(x)]
        if len(parts) < 2:
            continue

        # 見出し行は除外
        if parts[0] in bad or parts[1] in bad:
            continue

        # 次の意味のある行が時間帯
        time_line = None
        for j in range(i + 1, min(i + 4, len(lines))):
            candidate = normalize_text(lines[j])
            if not candidate:
                continue
            tm = time_re.match(candidate)
            if tm:
                time_line = candidate
                break
            # 時間帯以外の通常テキストが先に来たら、この行は対象外
            if candidate not in {"予約"}:
                break

        if not time_line:
            continue

        tm = time_re.match(time_line)
        if not tm:
            continue

        hall = parts[0]
        facility = parts[1]

        start_h = int(tm.group(1))
        start_m = int(tm.group(2))
        end_h = int(tm.group(3))
        end_m = int(tm.group(4))

        key = (
            f"{district}|{current_date}|{hall}|{facility}|"
            f"{start_h:02d}:{start_m:02d}-{end_h:02d}:{end_m:02d}"
        )

        results.append({
            "key": key,
            "district": district,
            "date": current_date,
            "hall": hall,
            "facility": facility,
            "start": f"{start_h:02d}:{start_m:02d}",
            "end": f"{end_h:02d}:{end_m:02d}",
            "start_minutes": start_h * 60 + start_m,
        })

    unique = {row["key"]: row for row in results}
    return list(unique.values())

def format_slot(row):
    return (
        f"{row['date']} {row['district']} "
        f"{row['hall']} / {row['facility']} "
        f"{row['start']}～{row['end']}"
    )


def main():
    print("=====================================================")
    print("港区バドミントン空き情報監視")
    print("=====================================================")

    previous_state = load_state()
    print(f"前回登録済み空き枠: {len(previous_state)}件")

    all_evening = []
    successful_districts = 0
    district_errors = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        for district in DISTRICTS:
            print("\n============================================================")
            print(f"検索開始: {district}")
            print("============================================================")
            print("検索期間: 1か月")
            print("時間帯: 指定なし（全時間帯）")

            page = browser.new_page()

            try:
                page.goto(URL, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(1000)

                # 「1か月」
                month = page.get_by_text("1か月", exact=True)
                if month.count() == 0:
                    month = page.locator("label").filter(has_text="1か月")
                if month.count() == 0:
                    raise RuntimeError("「1か月」を見つけられませんでした。")

                month.first.click()
                page.wait_for_timeout(500)

                # 時間帯は選択しない（全時間帯）
                select_district(page, district)
                select_badminton(page)
                click_search(page)
                click_date_order(page)

                body = get_all_results(page)

                # 生データ保存
                with open(
                    f"result_{district.replace('地区', '')}.txt",
                    "w",
                    encoding="utf-8",
                ) as f:
                    f.write(body)

                rows = parse_available_rows(body, district)

                # 検索結果ページ上に「合致した空き状況」があり、
                # 時間帯行もあるのに0件なら、抽出失敗と判断してstateを更新しない。
                has_available_message = "指定条件に合致した空き状況を表示しています" in body
                has_time_row = bool(
                    re.search(r"\d{1,2}時\d{2}分～\d{1,2}時\d{2}分", body)
                )

                if has_available_message and has_time_row and not rows:
                    raise RuntimeError(
                        f"{district}: 検索結果は取得できましたが、空き枠の抽出に失敗しました。"
                    )

                evening = [
                    row for row in rows
                    if row["start_minutes"] >= START_HOUR * 60
                ]

                print(f"{district}: 検索結果 {len(rows)}件")
                print(f"{district}: 17:00以降開始 {len(evening)}件")

                all_evening.extend(evening)
                successful_districts += 1

            except Exception as e:
                print(f"{district} の検索でエラー: {e}")
                district_errors.append(district)

                try:
                    page.screenshot(
                        path=f"error_{district.replace('地区', '')}.png",
                        full_page=True,
                    )
                except Exception:
                    pass

            finally:
                page.close()

        browser.close()

    # 全地区成功時のみstateを更新する
    if district_errors or successful_districts != len(DISTRICTS):
        print("\n============================================================")
        print("検索に失敗した地区があるため、state.jsonは更新しません。")
        print("============================================================")
        print("エラー地区:", ", ".join(district_errors))
        print("誤通知防止のため、今回はDiscord通知も行いません。")
        return

    # eveningをkeyで一意化
    current = {}
    for row in all_evening:
        current[row["key"]] = row

    current_state = set(current.keys())
    new_keys = current_state - previous_state
    new_rows = [current[k] for k in sorted(new_keys)]

    # 全17:00以降枠を書き出し
    with open(EVENING_FILE, "w", encoding="utf-8") as f:
        f.write("17:00以降開始の空き枠\n")
        f.write("==============================\n")
        if current:
            for key in sorted(current):
                f.write(format_slot(current[key]) + "\n")
        else:
            f.write("該当なし\n")

    # 新規枠を書き出し
    with open(NEW_FILE, "w", encoding="utf-8") as f:
        if new_rows:
            for row in new_rows:
                f.write(format_slot(row) + "\n")
        else:
            f.write("新規なし\n")

    print("\n17:00以降開始の空き枠合計:", len(current_state), "件")
    print("今回新しく出現した空き枠:", len(new_rows), "件")

    notification_ok = True

    if new_rows:
        message_lines = [
            "🏸 港区バドミントン空き情報",
            "17:00以降開始の新しい空き枠があります。",
            "",
        ]
        message_lines.extend(
            f"・{format_slot(row)}"
            for row in new_rows
        )
        message = "\n".join(message_lines)

        notification_ok = send_discord(message)

        if not notification_ok:
            print("Discord通知に失敗したため、state.jsonは更新しません。")
            print("次回実行でも同じ新規空き枠を再通知できるようにします。")
            return
    else:
        print("新規空き枠がないためDiscord通知はしません。")

    # Discord通知が成功した場合、または新規枠がない場合だけstate更新
    save_state(current_state)

    print("\n============================================================")
    print("監視終了")
    print("============================================================")


if __name__ == "__main__":
    main()
