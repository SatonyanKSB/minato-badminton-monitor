import os
import urllib.request
import json


def main():

    print("========================================")
    print("Discord接続テスト開始")
    print("========================================")

    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")

    # URLそのものは絶対に表示しない
    if webhook_url:
        print("DISCORD_WEBHOOK_URL: 読み込み成功")
        print(f"URLの長さ: {len(webhook_url)}文字")
        print(f"URLの先頭: {webhook_url[:20]}...")
    else:
        print("DISCORD_WEBHOOK_URL: 読み込み失敗")
        print("GitHub ActionsからSecretを取得できていません。")
        return

    # Discordへテストメッセージを送信
    message = {
        "content": (
            "🏸 **港区バドミントン監視システム**\n"
            "Discord通知テストです。\n"
            "このメッセージが届けばDiscord連携成功です。"
        )
    }

    data = json.dumps(message).encode("utf-8")

    request = urllib.request.Request(
        webhook_url,
        data=data,
        headers={
            "Content-Type": "application/json"
        },
        method="POST"
    )

    try:

        with urllib.request.urlopen(
            request,
            timeout=20
        ) as response:

            print("")
            print("Discordへの送信結果:")
            print(f"HTTPステータス: {response.status}")

            if response.status in (200, 204):
                print("========================================")
                print("Discord通知成功")
                print("========================================")
            else:
                print("Discordから予期しないステータスが返りました。")

    except Exception as e:

        print("")
        print("========================================")
        print("Discord通知に失敗しました")
        print("========================================")
        print(f"エラー種類: {type(e).__name__}")
        print(f"エラー内容: {e}")


if __name__ == "__main__":
    main()
