"""フォーマット・スキーマ処理。proc_ai.py から分離 (T2026-0504-A)。"""
from __future__ import annotations

import json
import re
from datetime import datetime

from proc_genre import _VALID_GENRE_SET, _validate_genres

_VALID_PHASES = ['発端', '拡散', 'ピーク', '現在地', '収束']
_VALID_LEVELS = ['major', 'sub', 'detail']

# T2026-0429-KP3 (2026-04-29): keyPoint ハード最小文字数。これを下回ったら 1 回だけ再生成を要求する。
# 旧スキーマ「200〜300 字」が prompt 上の推奨値でしかなく、実測 1.9% しか満たしていなかったため
# サーバ側で物理ガードを追加。proc_storage.KEYPOINT_MIN_LENGTH = 100 と完全一致させる。
_KEYPOINT_MIN_CHARS = 100

# パターン2 横断適用 (2026-04-29): perspectives / watchPoints / outlook にも最低文字数を schema 強制。
# 旧スキーマは keyPoint のみ minLength を持ち、他フィールドは「150字以内」等の上限のみで
# 実測 watchPoints 平均 38 字 / outlook 41 字 / perspectives 47 字程度の薄さに留まっていた。
# 最低文字数を schema に書くと Tool Use validation が schema 違反で再要求するため物理ガードになる。
# T2026-0430-K (2026-04-30): perspectives 60→80 字に引き上げ。
# 60 字下限では「概ね同様の論調で〜」だけの 65 字前後 fallback が量産され、
# UX 検証で「2 媒体の論調差を示す」目的が果たせていなかった。実測:
#   - aiGenerated active topics 477 件中 80 字未満 364 件 (76.3%) — 目標 60% 未満。
#   - 内訳: 60-79 字短文 13 件はほぼ全てが「概ね同様の論調」テンプレ fallback。
# 80 字に上げると Tool Use API が schema 違反を再要求するため物理ガード。
# プロンプトの「60 字以上 必須」表現も全て「80 字以上 必須」に統一する。
_PERSPECTIVES_MIN_CHARS = 80
_WATCHPOINTS_MIN_CHARS = 80   # ① 〇〇 ② △△ の 2 項目分 (各 40 字目安) の合計
_OUTLOOK_MIN_CHARS = 60

# T2026-0501-D (2026-05-01): retry 専用 keyPoint minLength。メイン schema は PO 指示で
# minLength=0 を維持するが、retry は「初回生成が <100 字で再要求」という強い文脈のため
# 最低 60 字を物理ガード (SLI keyPoint>=50字 閾値 + 10字バッファ)。
# 旧設計 (minLength=0) では Tool Use API がスキーマ強制を効かせず、retry も短文を返し続け
# 本番 SLI で keyPoint>=50字 充填率 38.6% で停滞 → 物理ガードで構造解消する。
_KEYPOINT_RETRY_MIN_CHARS = 60

# T2026-0428-J/E: 「トピックの状況」をユーザー視点で明確に区分する 4 値ラベル。
# 既存 phase (発端/拡散/ピーク/現在地/収束) は AI 内部判定の細粒度ラベル、
# statusLabel は detail page で読者に直接見せる粗粒度ラベル。
_VALID_STATUS_LABELS = ['発端', '進行中', '沈静化', '決着']


def clean_headline(title):
    """記事タイトルからメディア名サフィックスを除去 例: '記事 - 毎日新聞' → '記事'"""
    return re.sub(r'\s*[-－–|｜]\s*[^\s].{1,20}$', '', title).strip()


def _format_pub_date(raw_date) -> str:
    """pubDate（文字列またはUnix秒整数）を 'M/D' 形式に変換。パース失敗時は空文字を返す。"""
    if not raw_date:
        return ''
    # Unix timestamp（整数または数値文字列）
    try:
        ts = int(raw_date)
        if ts > 1_000_000_000:
            dt = datetime.utcfromtimestamp(ts if ts < 1e11 else ts / 1000)
            return f'{dt.month}/{dt.day}'
    except (TypeError, ValueError):
        pass
    s = str(raw_date)
    for fmt in ('%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%dT%H:%M:%S',
                '%Y-%m-%d', '%a, %d %b %Y %H:%M:%S %z', '%a, %d %b %Y %H:%M:%S GMT'):
        try:
            dt = datetime.strptime(s, fmt)
            return f'{dt.month}/{dt.day}'
        except ValueError:
            continue
    return ''


def _build_headlines(articles: list, limit: int = 15) -> tuple[str, int]:
    """記事リストからプロンプト用の見出し文字列と件数を返す。"""
    lines = []
    for a in articles[:limit]:
        title    = clean_headline(a.get('title', ''))
        desc     = (a.get('description') or '').strip()
        date_str = _format_pub_date(a.get('pubDate', '') or a.get('publishedAt', '') or '')
        line = f'{date_str} {title}'.strip() if date_str else title
        if desc:
            line += f'\n  概要: {desc[:150]}'
        lines.append(line)
    return '\n'.join(lines), len(articles)


def _parse_story_json(text: str) -> dict | None:
    """APIレスポンステキストからJSONを抽出・パースする (legacy text-mode 用)。
    Tool Use 移行後はこの関数は使わない。tool_use.input が直接 dict で返る。"""
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
    if json_match:
        text = json_match.group(1)
    else:
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            text = json_match.group(0)
    return json.loads(text)


def _sanitize_timeline(raw_timeline, max_items: int = 6) -> list:
    """timelineリストを検証・正規化する。transitionは最後以外のアイテムにのみ付与。"""
    if not isinstance(raw_timeline, list):
        return []
    sanitized = []
    items = [e for e in raw_timeline if isinstance(e, dict) and e.get('event')][:max_items]
    for i, e in enumerate(items):
        item = {
            'date':  str(e.get('date', '')),
            'event': str(e.get('event', ''))[:40],
        }
        raw_tr = str(e.get('transition') or '').strip()
        if raw_tr and i < len(items) - 1:
            item['transition'] = raw_tr[:25]
        sanitized.append(item)
    return sanitized


def _keypoint_too_short(s) -> bool:
    """keyPoint が 100 字未満かどうかを判定。空・None も True (=不十分) として扱う。"""
    if not isinstance(s, str):
        return True
    return len(s.strip()) < _KEYPOINT_MIN_CHARS


def _emit_keypoint_metric(mode: str, keypoint, *, retried: bool) -> None:
    """T2026-0429-J: keyPoint 文字数を CloudWatch から拾える形で 1 行 print する。

    フォーマット: `[METRIC] keypoint_len mode=<mode> len=<n> ge100=<0|1> ge200=<0|1> retried=<0|1>`
    用途: 改善効果 (≥100 字 70% 達成) を本番ログから集計可能にする。
    """
    n = len((keypoint or '').strip()) if isinstance(keypoint, str) else 0
    print(
        f'[METRIC] keypoint_len mode={mode} len={n} '
        f'ge100={1 if n >= 100 else 0} '
        f'ge200={1 if n >= 200 else 0} '
        f'retried={1 if retried else 0}'
    )


def _build_story_schema(mode: str, *, cnt: int = 1) -> dict:
    """Tool Use 用 JSON Schema を mode 別に構築。
    mode: 'minimal' | 'standard' | 'full'
    cnt:  記事件数。minimal モードのときのみ参照する。
          T2026-0430-G: minimal mode でも cnt>=2 (媒体が 2 つ以上) のときは
          perspectives を生成する。watchPoints/timeline/statusLabel は引き続き
          minimal regime では生成しない (1〜2 件では差分が薄い)。
    """
    # T2026-0428-J/E (2026-04-28): フィールド再設計（最終確定版）。
    # 「なぜ今か」はグラフ(記事数スパイク)が示すべきであり AI に語らせない。
    # AI 要約は「状況解説 / 各メディアの見解 / 注目ポイント / AI予想」の 4 軸に集中。
    # 削除: spreadReason, backgroundContext, background, whatChanged
    # 追加: statusLabel (粗粒度フェーズ), watchPoints (今後の観察軸)
    base_props = {
        'aiSummary': {'type': 'string', 'description': '150字以内・2文構成。「何が起きたか」+「何を意味するか」。事実羅列禁止、読んだ人が結論を理解できる内容にする。人名は初出時に「肩書き＋正式名称」必須 (例: 米国のトランプ大統領 / ミャンマーの民主化指導者アウンサンスーチー氏)。略称・苗字単独・通称のみは禁止。'},
        # T2026-0501-B (2026-05-01): keyPoint プロンプトをフック型に改修。
        # PO FB「トピックが無難すぎる・表題に惹きがない」を受け、読者の「え、なんで？」
        # 「自分にどう関係する？」を引き出す 4 原則を明示。
        # ①驚き・逆説で始める ②数字・固有名詞 ③読者影響の明示 ④「なぜなら〜」で構造提示。
        # T2026-0501-G (2026-05-01): 初動③を「今後どうなりそうか」→「なぜこうなったか・構造的背景」に修正。
        # 「今後の見通し・予測」は outlook 専任フィールドと内容重複するため keyPoint から除外。
        # T2026-0503-UX-NO-KEYPOINT-23 (2026-05-03): 「空文字を返す」脱出ハッチを削除。
        # 23.1% の topic で keyPoint 未生成 → 「何が変わったのか不明確」でも必ず書く。
        # 変化が不明確な場合は「何が起きたか」「なぜ重要か」「構造的背景」の3点で代替。
        'keyPoint': {'type': 'string', 'minLength': 0, 'description': '読者の「え、なんで？」「自分にどう関係する？」を引き出すフック型で書く。フック型4原則: ①驚き・逆説で始める（「〇〇なのに〇〇」「実は〜」「意外にも〜」）②具体的な数字・固有名詞を必ず含む ③読者への影響を明示する ④「なぜなら〜」「背景には〜」で構造的理由を示す。【記事1件・初動フェーズ】: ①何が起きたか（驚き・逆説で始める）②なぜ重要か（読者への影響）③なぜこうなったか・構造的背景（「背景には〜」「なぜなら〜」で根拠を示す）。【記事2件以上・変化フェーズ】: 1文目=今回何が変わったか（驚き・逆説で始める）2文目=以前の状況（これまでは〜だった）3文目=今回の追加情報・具体数字・固有名詞 4文目=読者への影響（「なぜなら〜」「背景には〜」）。変化が不明確な場合は「何が起きたか」「なぜ重要か」「構造的背景」の3点から100字以上で書く（空文字禁止）。禁止: 一般論から始める/単なる記事要約/背景説明だけで終わる/抽象的表現で逃げる/人名・組織を略称や苗字単独で書く（読者の前提知識を要求しない=情報の地図原則）/今後の見通し・予測を含めない（それは outlook の役割）。100字以上必須。人名・組織名は段落内で1回は「肩書き＋正式名称」で書く。2回目以降は略称可。'},
        'outlook': {'type': 'string', 'minLength': _OUTLOOK_MIN_CHARS, 'description': 'AI予想として「この先どうなるか」を1文で。**60 字以上 必須**。〜が予想される/〜の可能性があるで締める。文末に [確信度:高] [確信度:中] [確信度:低] のいずれかを必ず付与 (例: 「合意成立の可能性がある [確信度:中]」)。記事内に明示根拠あり=高、複数の状況証拠=中、推測ベース=低。後で新記事と照合して当否判定するため、検証可能な仮説として書くこと。'},
        # T2026-0501-OL2: outlook の根拠となる因果チェーン。情報の地図ビジョンの中核。
        # 1 次効果で止まらず 2 次/3 次連鎖まで踏み込ませるため、構造化フィールドとして強制。
        'causalChain': {
            'type': 'array',
            'description': (
                'outlookの根拠となる因果チェーン。各ステップにfrom/to/mechanism/confidence を持つ。'
                '相関ではなく因果であること（mechanismで経路を説明できること）を確認してから出力。'
                '第三変数による疑似相関は含めない。3〜6ステップ推奨。'
            ),
            'items': {
                'type': 'object',
                'properties': {
                    'from': {'type': 'string', 'description': '原因となる出来事・状態'},
                    'to': {'type': 'string', 'description': '結果となる出来事・状態'},
                    'mechanism': {'type': 'string', 'description': 'なぜfromがtoを引き起こすかの経路（第三変数排除済み）'},
                    'confidence': {'type': 'number', 'description': '0.0〜1.0 この因果リンクの確信度'},
                },
                'required': ['from', 'to', 'mechanism', 'confidence'],
            },
            'minItems': 2,
            'maxItems': 8,
        },
        'topicTitle': {'type': 'string', 'description': '30文字以内のテーマ名(体言止め)。具体的な固有名詞を含む。例: 岸田政権の解散戦略。日本語で15字制限は体言止めの語句が途中で切れて意味不明になる事故 (2026-05-02 UX 観察) のため 30 字に緩和済。'},
        'latestUpdateHeadline': {'type': 'string', 'description': '最新の動きを40文字以内の1文(〜が〜した形式)。'},
        'isCoherent': {'type': 'boolean', 'description': 'true=全記事が同一主語・同一流れ。false=異主語/異論点混在。'},
        'topicLevel': {'type': 'string', 'enum': _VALID_LEVELS, 'description': 'major=国家間・産業横断/sub=majorの一側面/detail=個別発表'},
        'parentTopicTitle': {'type': ['string', 'null'], 'description': '上位テーマ名。独立トピックは null。'},
        'relatedTopicTitles': {'type': 'array', 'items': {'type': 'string'}, 'maxItems': 3, 'description': '因果・波及関係にある別テーマ。'},
        'genres': {'type': 'array', 'items': {'type': 'string', 'enum': list(_VALID_GENRE_SET)}, 'minItems': 1, 'maxItems': 2},
    }
    # T2026-0501-OL2: causalChain は全モード必須 (outlook が必須なら根拠も必須にする)。
    # minItems=2 で物理ガード。AI が出さなければ Tool Use API がスキーマ違反を再要求する。
    required = ['aiSummary', 'keyPoint', 'outlook', 'causalChain', 'topicTitle', 'latestUpdateHeadline', 'isCoherent', 'topicLevel', 'genres']

    if mode == 'minimal':
        # minimal は timeline/watchPoints/statusLabel は無し (記事1〜2件では差分が出ない)。
        # T2026-0430-G (2026-04-30): cnt>=2 (媒体が 2 つ以上) のときは perspectives のみ
        # 例外的に生成する。実測 ac=2 が aiGenerated 母集団の 49% を占め、minimal mode で
        # perspectives=None 強制が perspectives 充填率を 45% に張り付かせていたため。
        if cnt >= 2:
            base_props['perspectives'] = {
                'type': 'string',
                'minLength': _PERSPECTIVES_MIN_CHARS,
                'description': '2 媒体の見解を「[メディア名] は〜」の構文で並列列挙 (**80 字以上 必須**)。各社の本文 (ある場合) を根拠にし、推測ではなく実際の論調差を抽出する。論調差が薄い場合でも単なる「概ね同様の論調」では不可。各社が何に焦点を当てているか (扱う論点・取り上げ方の重心) を 1 文ずつ書き、最後に「両社で論調差は限定的」と結ぶ等、80 字以上の情報量を確保する。',
            }
            required.append('perspectives')
    else:
        base_props['statusLabel'] = {
            'type': 'string',
            'enum': _VALID_STATUS_LABELS,
            'description': 'トピックの現在状況を読者向け 4 値で示す。発端=注目され始めた直後/進行中=報道が続き熱量がある/沈静化=報道頻度が落ちている/決着=結論や合意が出て話題が閉じた。phase の細粒度ラベルとは別に、ユーザー向け粗粒度として独立に判定する。',
        }
        base_props['watchPoints'] = {
            'type': 'string',
            'minLength': _WATCHPOINTS_MIN_CHARS,
            'description': 'これからの注目ポイントを複数軸で簡潔に案内する(80〜150字)。**80 字以上 必須**。断言や予測は避け「ここを見ておくといい」という観察視点を提示する。形式: ①〇〇の進捗 ②△△の対応 ③□□の動向 のように 2〜3 項目を ① ② ③ 番号付きで列挙し、各項目を 40 字程度の説明で書く。outlook (AI予想) とは役割が異なり、こちらは「どこを見るべきか」のガイドに徹する。',
        }
        base_props['perspectives'] = {'type': 'string', 'minLength': _PERSPECTIVES_MIN_CHARS, 'description': '各社の懸念・可能性・着目点を並列列挙(2〜3社・**80 字以上 必須**)。各社が何に焦点を当てているか(扱う論点・取り上げ方の重心)を 1 文ずつ書く。論調差が薄くても短文 fallback (例: 「概ね同様」だけで終わる) は禁止。例: 朝日は経済への打撃を懸念し関税試算を主軸にする、産経は安全保障上の利益を指摘し防衛装備の前向きな影響を強調、毎日は外交プロセスの不透明性に着目し交渉経緯を詳述する。'}
        base_props['phase'] = {'type': 'string', 'enum': _VALID_PHASES}
        base_props['timeline'] = {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'date': {'type': 'string'},
                    'event': {'type': 'string'},
                    'transition': {'type': 'string'},
                },
                'required': ['event'],
            },
            'maxItems': 6 if mode == 'full' else 3,
        }
        required += ['statusLabel', 'watchPoints', 'perspectives', 'phase', 'timeline']
        if mode == 'full':
            base_props['forecast'] = {'type': 'string', 'description': '今後どうなるか。記事内容を根拠にした仮説(2文)。〜が見込まれる/〜の可能性があるで締める。文末に [確信度:高] [確信度:中] [確信度:低] のいずれかを必ず付与 (例: 「..今後数ヶ月で進展が見込まれる [確信度:中]」)。記事内に明示根拠あり=高、複数の状況証拠=中、推測ベース=低。'}
            required += ['forecast']

    return {
        'type': 'object',
        'properties': base_props,
        'required': required,
    }


def _sanitize_causal_chain(raw, max_items: int = 8) -> list:
    """T2026-0501-OL2: causalChain を検証・正規化する。

    各要素は {from, to, mechanism, confidence} を必須とし、欠落 or 型違反は除外。
    confidence は 0.0〜1.0 にクランプ。max_items を超えたら切り詰める。
    Returns: [{from,to,mechanism,confidence}, ...]
    """
    if not isinstance(raw, list):
        return []
    out = []
    for step in raw[:max_items]:
        if not isinstance(step, dict):
            continue
        f = str(step.get('from') or '').strip()
        t = str(step.get('to') or '').strip()
        m = str(step.get('mechanism') or '').strip()
        c = step.get('confidence')
        if not f or not t or not m:
            continue
        try:
            cf = float(c)
        except (TypeError, ValueError):
            continue
        cf = max(0.0, min(1.0, cf))
        out.append({'from': f[:200], 'to': t[:200], 'mechanism': m[:300], 'confidence': cf})
    return out


def _normalize_story_result(result: dict, mode: str) -> dict:
    """tool_use.input を内部 dict 形式に正規化。"""
    parent_title    = result.get('parentTopicTitle')
    related_titles  = result.get('relatedTopicTitles') or []
    causal_chain    = _sanitize_causal_chain(result.get('causalChain'))
    if mode == 'minimal':
        # T219 修正 (2026-04-28): minimal モード (記事1-2件) は phase 概念が薄い
        # → 「発端」固定はユーザーに「フェーズ機能が機能していない」誤印象を与える
        # phase=None で返し、frontend 側の存在チェックで非表示にさせる
        kp_minimal = str(result.get('keyPoint') or '').strip()[:400]
        return {
            'aiSummary':              str(result.get('aiSummary') or '').strip(),
            'keyPoint':               kp_minimal,
            # T2026-0430-A: 品質メトリクスを output dict に伝搬し、proc_storage で DDB に保存する。
            'keyPointLength':         len(kp_minimal),
            'keyPointRetried':        bool(result.get('_kpRetried', False)),
            'keyPointFallback':       bool(result.get('_kpFallback', False)),
            'statusLabel':            None,
            'watchPoints':            '',
            # T2026-0430-G: minimal mode でも cnt>=2 で perspectives を生成する。
            # AI が出さなかった場合は None のまま (空文字列ではなく None で観測上の差を残す)。
            'perspectives':           result.get('perspectives') if isinstance(result.get('perspectives'), str) and result.get('perspectives').strip() else None,
            'outlook':                str(result.get('outlook') or '').strip(),
            # T2026-0501-OL2: outlook の根拠となる因果チェーン (必ず array で返す。空配列もあり得る)。
            'causalChain':            causal_chain,
            'forecast':               '',
            'timeline':               [],
            'phase':                  None,
            'summaryMode':            'minimal',
            'topicTitle':             str(result.get('topicTitle') or '').strip()[:30],  # T2026-0502-UX 15→30: 日本語15字は体言止めの語句が途中で切れて意味不明になる事故の恒久対処
            'latestUpdateHeadline':   str(result.get('latestUpdateHeadline') or '').strip()[:40],
            'isCoherent':             result.get('isCoherent') is not False,
            'topicLevel':             result.get('topicLevel') if result.get('topicLevel') in _VALID_LEVELS else 'detail',
            'parentTopicTitle':       str(parent_title).strip()[:30] if parent_title and parent_title != 'null' else None,
            'relatedTopicTitles':     [str(t).strip()[:30] for t in related_titles[:3]] if isinstance(related_titles, list) and related_titles else [],
            'genres':                 _validate_genres(result.get('genres')),
        }
    # standard / full 共通
    # T219 (2026-04-28): AI が phase='発端' を返した場合、standard/full mode (記事3件以上) では矯正
    # prompt で禁止しているが contract violation 防御として normalize 層でも矯正する
    raw_phase = result.get('phase')
    if raw_phase == '発端' and mode in ('standard', 'full'):
        raw_phase = '拡散'
    raw_status = result.get('statusLabel')
    kp_full = str(result.get('keyPoint') or '').strip()[:400]
    out = {
        'aiSummary':              str(result.get('aiSummary') or '').strip(),
        # T2026-0428-J/E: keyPoint は 200〜300 字の物語形式に拡張。truncate は 400 字で安全側に。
        'keyPoint':               kp_full,
        # T2026-0430-A: 品質メトリクスを output dict に伝搬し、proc_storage で DDB に保存する。
        'keyPointLength':         len(kp_full),
        'keyPointRetried':        bool(result.get('_kpRetried', False)),
        'keyPointFallback':       bool(result.get('_kpFallback', False)),
        'statusLabel':            raw_status if raw_status in _VALID_STATUS_LABELS else None,
        'watchPoints':            str(result.get('watchPoints') or '').strip()[:200],
        'perspectives':           result.get('perspectives') if isinstance(result.get('perspectives'), str) else None,
        'outlook':                str(result.get('outlook') or '').strip(),
        # T2026-0501-OL2: outlook の根拠となる因果チェーン (必ず array で返す。空配列もあり得る)。
        'causalChain':            causal_chain,
        'forecast':               str(result.get('forecast') or '').strip() if mode == 'full' else '',
        'timeline':               _sanitize_timeline(result.get('timeline'), max_items=6 if mode == 'full' else 3),
        'phase':                  raw_phase if raw_phase in _VALID_PHASES else '現在地',
        'summaryMode':            mode,
        'topicTitle':             str(result.get('topicTitle') or '').strip()[:30],  # T2026-0502-UX 15→30: 日本語15字は体言止めの語句が途中で切れて意味不明になる事故の恒久対処
        'latestUpdateHeadline':   str(result.get('latestUpdateHeadline') or '').strip()[:40],
        'isCoherent':             result.get('isCoherent') is not False,
        'topicLevel':             result.get('topicLevel') if result.get('topicLevel') in _VALID_LEVELS else 'detail',
        'parentTopicTitle':       str(parent_title).strip()[:30] if parent_title and parent_title != 'null' else None,
        'relatedTopicTitles':     [str(t).strip()[:30] for t in related_titles[:3]] if isinstance(related_titles, list) and related_titles else [],
        'genres':                 _validate_genres(result.get('genres')),
    }
    return out
