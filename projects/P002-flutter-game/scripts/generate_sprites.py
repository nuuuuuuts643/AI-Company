#!/usr/bin/env python3
"""
ゲームスプライト自動生成スクリプト
pollinations.ai の無料APIを使用（APIキー不要）
リトライ付き・レート制限対策版
"""

import urllib.request
import urllib.parse
import urllib.error
import os
import time
import sys

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'assets', 'images')
os.makedirs(OUTPUT_DIR, exist_ok=True)

BASE_URL = "https://image.pollinations.ai/prompt/{prompt}?width=128&height=128&nologo=true&seed={seed}&model=flux"

SPRITES = [
    # --- 敵キャラ ---
    ("enemy_goblin",       "pixel art goblin warrior, green skin, red eyes, holding wooden club, simple RPG game sprite, black background, 8bit retro style", 101),
    ("enemy_goblin_shaman","pixel art goblin shaman, purple robe, glowing staff, magic sparkles, simple RPG game sprite, black background, 8bit retro style", 102),
    ("enemy_orc",          "pixel art orc warrior, gray skin, tusks, battle axe, muscular, simple RPG game sprite, black background, 8bit retro style", 103),
    ("enemy_orc_berserker","pixel art orc berserker, red eyes, dual axes, battle rage, simple RPG game sprite, black background, 8bit retro style", 104),
    ("enemy_fire_drake",   "pixel art fire dragon, red orange scales, breathing fire, simple RPG game sprite, black background, 8bit retro style", 105),
    ("enemy_sea_serpent",  "pixel art sea serpent, blue teal scales, coiled body, simple RPG game sprite, black background, 8bit retro style", 106),
    ("enemy_wind_wraith",  "pixel art wind ghost, translucent blue, wispy form, simple RPG game sprite, black background, 8bit retro style", 107),
    ("enemy_stone_golem",  "pixel art stone golem, rocky gray body, glowing eyes, simple RPG game sprite, black background, 8bit retro style", 108),
    ("enemy_dark_knight",  "pixel art dark knight, black armor, purple aura, simple RPG game sprite, black background, 8bit retro style", 109),
    ("enemy_shadow_bat",   "pixel art shadow bat, black wings, red eyes, simple RPG game sprite, black background, 8bit retro style", 110),
    ("enemy_lich_king",    "pixel art lich king boss, undead sorcerer, glowing crown, dark magic, simple RPG game sprite, black background, 8bit retro style", 201),
    ("enemy_shadow_lord",  "pixel art shadow lord boss, dark void form, multiple glowing eyes, simple RPG game sprite, black background, 8bit retro style", 202),

    # --- 味方ユニット ---
    ("unit_fire",  "pixel art fire swordsman hero, red armor, flaming sword, simple RPG game sprite, black background, 8bit retro style", 301),
    ("unit_water", "pixel art water archer hero, blue teal armor, bow and arrow, simple RPG game sprite, black background, 8bit retro style", 302),
    ("unit_wind",  "pixel art wind mage hero, green robe, wind staff, simple RPG game sprite, black background, 8bit retro style", 303),
    ("unit_earth", "pixel art earth guardian hero, brown stone armor, large shield, simple RPG game sprite, black background, 8bit retro style", 304),
    ("unit_light", "pixel art light paladin hero, golden armor, holy sword glowing, simple RPG game sprite, black background, 8bit retro style", 305),
    ("unit_dark",  "pixel art dark warlock hero, purple black robe, dark magic orb, simple RPG game sprite, black background, 8bit retro style", 306),
]

MAX_RETRIES = 3
DELAY_BETWEEN = 5.0   # 成功時の次リクエストまでの待機秒数
RETRY_DELAY  = 8.0    # リトライ前の待機秒数

def download_sprite(name, prompt, seed):
    encoded = urllib.parse.quote(prompt)
    url = BASE_URL.format(prompt=encoded, seed=seed)
    out_path = os.path.join(OUTPUT_DIR, f"{name}.png")

    if os.path.exists(out_path):
        size = os.path.getsize(out_path)
        if size > 1000:  # 最低1KB以上あれば有効と判断
            print(f"  [SKIP] {name}.png already exists ({size} bytes)")
            return True
        else:
            print(f"  [RETRY] {name}.png exists but too small ({size} bytes), re-downloading")
            os.remove(out_path)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"  [{attempt}/{MAX_RETRIES}] Generating: {name}...", flush=True)
            req = urllib.request.Request(
                url,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                    'Accept': 'image/png,image/*',
                }
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = resp.read()

            if len(data) < 1000:
                raise ValueError(f"Response too small: {len(data)} bytes")

            with open(out_path, 'wb') as f:
                f.write(data)
            size = os.path.getsize(out_path)
            print(f"  [OK] {name}.png ({size:,} bytes)", flush=True)
            return True

        except urllib.error.HTTPError as e:
            print(f"  [HTTP {e.code}] {name}: {e.reason}")
            if e.code == 429:
                wait = RETRY_DELAY * attempt
                print(f"  Rate limited. Waiting {wait}s...", flush=True)
                time.sleep(wait)
            else:
                time.sleep(RETRY_DELAY)

        except Exception as e:
            print(f"  [FAIL attempt {attempt}] {name}: {e}", flush=True)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)

    print(f"  [GIVE UP] {name} after {MAX_RETRIES} attempts")
    return False


if __name__ == '__main__':
    print(f"Generating {len(SPRITES)} sprites → {OUTPUT_DIR}")
    print(f"Delay: {DELAY_BETWEEN}s between requests, {RETRY_DELAY}s on retry\n")
    ok, fail = 0, 0
    for i, (name, prompt, seed) in enumerate(SPRITES):
        result = download_sprite(name, prompt, seed)
        if result:
            ok += 1
        else:
            fail += 1
        # 最後の1枚以外は待機
        if i < len(SPRITES) - 1:
            time.sleep(DELAY_BETWEEN)

    print(f"\n完了: {ok}/{len(SPRITES)} OK, {fail} failed")
    if ok > 0:
        print("次のステップ: flutter run で画像を確認")
