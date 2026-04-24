import boto3

KEY = "YOUR_KEY_HERE"  # ← ここをsk-ant-...に書き換えて実行

assert KEY.startswith("sk-ant-"), "キーを入力してください"

boto3.client("lambda", region_name="ap-northeast-1").update_function_configuration(
    FunctionName="p003-processor",
    Environment={"Variables": {
        "S3_BUCKET": "p003-news-946554699567",
        "TABLE_NAME": "p003-topics",
        "REGION": "ap-northeast-1",
        "SITE_URL": "https://flotopic.com",
        "ANTHROPIC_API_KEY": KEY,
    }},
)
print("設定完了")
