#!/usr/bin/env bash
# build_embedding_layer.sh — multilingual-e5-small ONNX qint8 を含む Lambda layer をビルド
#
# T2026-0502-U Phase 1 (2026-05-02 PO 指示「embedding 移行進めたい」):
#   118MB の ONNX qint8 モデル + onnxruntime + transformers tokenizer を
#   Lambda layer (250MB 制限内) にパッケージング。
#
# 出力: /tmp/embedding_layer.zip → AWS Console or aws CLI で publish-layer-version
#
# 必要環境: Mac (or Linux)・python3.12・wget。Cowork sandbox では SOCKS proxy で
# huggingface_hub の download が失敗するため Mac の Code セッションでのみ動作。
#
# 使い方:
#   bash scripts/build_embedding_layer.sh
#   aws lambda publish-layer-version --layer-name p003-embedding-e5small \
#     --description "multilingual-e5-small ONNX qint8 (T2026-0502-U)" \
#     --compatible-runtimes python3.12 --license-info "MIT" \
#     --zip-file fileb:///tmp/embedding_layer.zip --region ap-northeast-1
#
# 検証コマンド (layer publish 後):
#   aws lambda update-function-configuration --function-name p003-fetcher \
#     --layers <ARN of new layer version> --region ap-northeast-1

set -euo pipefail

WORK_DIR="${WORK_DIR:-/tmp/build_embedding_layer}"
OUTPUT_ZIP="${OUTPUT_ZIP:-/tmp/embedding_layer.zip}"
MODEL_REPO="deepfile/multilingual-e5-small-onnx-qint8"
TOKENIZER_REPO="intfloat/multilingual-e5-small"

echo "[1/5] 作業ディレクトリ準備: $WORK_DIR"
rm -rf "$WORK_DIR"
mkdir -p "$WORK_DIR/python" "$WORK_DIR/embedding/tokenizer"

echo "[2/5] Python 依存 (onnxruntime + transformers tokenizer のみ・PyTorch 不要) インストール"
pip install --target "$WORK_DIR/python" --platform manylinux2014_x86_64 \
  --python-version 3.12 --only-binary=:all: --upgrade \
  onnxruntime==1.20.1 transformers==4.46.0 tokenizers sentencepiece numpy

# 不要ファイル削除でサイズ削減
find "$WORK_DIR/python" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find "$WORK_DIR/python" -name "*.pyc" -delete 2>/dev/null || true
find "$WORK_DIR/python" -name "tests" -type d -exec rm -rf {} + 2>/dev/null || true

echo "[3/5] ONNX model + tokenizer ダウンロード"
python3 - <<'PYEOF'
import os
from huggingface_hub import snapshot_download
work_dir = os.environ.get('WORK_DIR', '/tmp/build_embedding_layer')
# qint8 ONNX モデル
mp = snapshot_download(
    repo_id='deepfile/multilingual-e5-small-onnx-qint8',
    local_dir=os.path.join(work_dir, 'embedding'),
    allow_patterns=['*.onnx'],
)
print(f'model dir: {mp}')
# tokenizer (sentencepiece.bpe.model + tokenizer.json + config)
tp = snapshot_download(
    repo_id='intfloat/multilingual-e5-small',
    local_dir=os.path.join(work_dir, 'embedding', 'tokenizer'),
    allow_patterns=['tokenizer.json', 'tokenizer_config.json', 'sentencepiece.bpe.model',
                    'special_tokens_map.json', 'config.json'],
)
print(f'tokenizer dir: {tp}')
PYEOF

# Lambda layer 構造に整える: /opt/embedding/model.onnx + /opt/embedding/tokenizer/
# (Lambda 実行時 /opt にマウントされる)
ONNX_FILE=$(find "$WORK_DIR/embedding" -maxdepth 2 -name "*.onnx" | head -1)
mv "$ONNX_FILE" "$WORK_DIR/embedding/model.onnx"

echo "[4/5] サイズ確認"
du -sh "$WORK_DIR/python" "$WORK_DIR/embedding"
TOTAL_MB=$(du -sm "$WORK_DIR" | awk '{print $1}')
echo "Total: ${TOTAL_MB}MB (Lambda layer 上限 250MB)"
if [ "$TOTAL_MB" -gt 240 ]; then
  echo "[ERROR] 240MB 超過。layer 上限に近すぎます。再見積必要。"
  exit 1
fi

echo "[5/5] zip 作成: $OUTPUT_ZIP"
cd "$WORK_DIR"
zip -qr "$OUTPUT_ZIP" python embedding
ls -lh "$OUTPUT_ZIP"

echo ""
echo "[OK] embedding layer ビルド完了"
echo ""
echo "次のステップ:"
echo "  aws lambda publish-layer-version --layer-name p003-embedding-e5small \\"
echo "    --description 'multilingual-e5-small ONNX qint8 (T2026-0502-U)' \\"
echo "    --compatible-runtimes python3.12 \\"
echo "    --zip-file fileb://$OUTPUT_ZIP --region ap-northeast-1"
echo ""
echo "  # 出力された LayerVersionArn を fetcher Lambda に attach"
echo "  aws lambda update-function-configuration --function-name p003-fetcher \\"
echo "    --layers <LayerVersionArn> --region ap-northeast-1"
echo ""
echo "  # env 切替"
echo "  aws lambda update-function-configuration --function-name p003-fetcher \\"
echo "    --environment 'Variables={...,EMBEDDING_MERGE_ENABLED=true,AI_MERGE_ENABLED=false}' \\"
echo "    --region ap-northeast-1"
