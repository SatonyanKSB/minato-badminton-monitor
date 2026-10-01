import os
import urllib.request
import urllib.error
import json


def main():

    print("========================================")
    print("Discord接続テスト")
    print("========================================")

    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")

    if not webhook_url:
        print("DISCORD_WEBHOOK_URL: 読み込み失敗")
        return

    print("DISCORD_WEBHOOK_URL: 読み込み成功")
    print(f"URLの長さ: {len(webhook_url)}文字")

    message = {
        "content": "🏸 港区バドミントン監視システム Discord接続テストです。"
    }

    data = json.dumps(message).encode("utf-8")

    request = urllib.request.Request(
        webhook_url,
        data=data,
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

            print("")
            print("送信成功")
            print(f"HTTPステータス: {response.status}")

            body = response.read().decode(
                "utf-8",
                errors="replace"
            )

            print(f"レスポンス: {body}")

    except urllib.error.HTTPError as e:

        print("")
        print("========================================")
        print("Discordからエラーが返りました")
        print("========================================")

        print(f"HTTPステータス: {e.code}")

        error_body = e.read().decode(
            "utf-8",
            errors="replace"
        )

        print(f"Discordのエラー本文: {error_body}")

    except Exception as e:

        print("")
        print("========================================")
        print("通信エラー")
        print("========================================")

        print(f"エラー種類: {type(e).__name__}")
        print(f"エラー内容: {e}")


if __name__ == "__main__":
    main()
