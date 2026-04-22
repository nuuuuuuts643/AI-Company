# 必要アセット一覧 — 封印の戦線 (P002)

## 状態凡例
- ✅ 実装済み（コードで生成）
- 🟡 プレースホルダー（ColoredRect/図形で代替中）
- ❌ 未実装（実装が必要）

---

## 画像 (`assets/images/`)

### キャラクタースプライト（ドット絵 48×64px, PNG透過）
| ファイル | 内容 | 状態 |
|---|---|---|
| `units/unit_swordsman_fire.png` | 炎剣士 (4方向×3アニメ) | 🟡 |
| `units/unit_archer_wind.png` | 風弓兵 | 🟡 |
| `units/unit_mage_water.png` | 水魔法使い | 🟡 |
| `units/unit_knight_earth.png` | 土の騎士 | 🟡 |
| `units/unit_priest_light.png` | 光の聖職者 | 🟡 |
| `units/unit_necromancer_dark.png` | 闇の死霊術師 | 🟡 |
| `units/unit_druid_wind.png` | 霊樹使い | 🟡 |
| `units/unit_bomber_fire.png` | 炎爆弾兵 | 🟡 |

### 敵スプライト（ドット絵 48×56px, PNG透過）
| ファイル | 内容 | 状態 |
|---|---|---|
| `enemies/enemy_goblin.png` | ゴブリン (歩行4フレーム) | 🟡 |
| `enemies/enemy_goblin_shaman.png` | ゴブリンシャーマン | 🟡 |
| `enemies/enemy_orc.png` | オーク | 🟡 |
| `enemies/enemy_orc_berserker.png` | オークバーサーカー | 🟡 |
| `enemies/enemy_fire_drake.png` | ファイアドレイク (飛行) | 🟡 |
| `enemies/enemy_sea_serpent.png` | 海蛇 | 🟡 |
| `enemies/enemy_wind_wraith.png` | 風霊 | 🟡 |
| `enemies/enemy_stone_golem.png` | ストーンゴーレム (大型96×96) | 🟡 |
| `enemies/enemy_dark_knight.png` | 闇の騎士 | 🟡 |
| `enemies/enemy_shadow_bat.png` | 影蝙蝠 | 🟡 |
| `enemies/boss_lich_king.png` | リッチキング (BOSS 128×128) | 🟡 |
| `enemies/boss_shadow_lord.png` | 影の王 (BOSS 128×128) | 🟡 |

### 背景レイヤー（各背景3レイヤー: far/mid/near）
| ファイル | サイズ | 状態 |
|---|---|---|
| `backgrounds/bg_forest_far.png` | 390×300px | 🟡 |
| `backgrounds/bg_forest_mid.png` | 390×300px | 🟡 |
| `backgrounds/bg_forest_near.png` | 390×200px | 🟡 |
| `backgrounds/bg_volcano_*.png` | 同上 | 🟡 |
| `backgrounds/bg_sea_*.png` | 同上 | 🟡 |
| `backgrounds/bg_dark_castle_*.png` | 同上 | 🟡 |

### UI・エフェクト
| ファイル | 内容 | 状態 |
|---|---|---|
| `ui/card_frame_unit.png` | ユニットカード枠 | 🟡 |
| `ui/card_frame_spell.png` | 魔法カード枠 | 🟡 |
| `ui/card_frame_trap.png` | 罠カード枠 | 🟡 |
| `ui/element_icons/*.png` | 属性アイコン (32×32) 6枚 | 🟡 |
| `ui/wall_stage1.png` | 城壁ドット絵 | 🟡 |
| `effects/explosion.png` | 爆発スプライトシート | 🟡 |
| `effects/chain_flash.png` | チェーン光エフェクト | 🟡 |
| `effects/fireball.png` | 炎弾 | 🟡 |

### スキンプレビュー (256×256px)
| ファイル | 状態 |
|---|---|
| `skins/skin_default_preview.png` | 🟡 |
| `skins/skin_cherry_blossom_preview.png` | 🟡 |
| `skins/skin_iron_knight_preview.png` | 🟡 |

### アプリアイコン
| ファイル | サイズ | 状態 |
|---|---|---|
| `icon-1024.png` | 1024×1024 | ❌ App Store提出用 |
| `icon-180.png` | 180×180 | ❌ iPhone @3x |

---

## フォント (`assets/fonts/`)
| ファイル | 内容 | 状態 |
|---|---|---|
| `DotGothic16-Regular.ttf` | ドット絵フォント（Google Fonts） | ❌ 要ダウンロード |

**取得方法:**
```bash
# Google Fonts から DotGothic16 をダウンロード
# https://fonts.google.com/specimen/DotGothic16
```

---

## BGM (`assets/audio/bgm/`)
| ファイル | 内容 | ループ | 状態 |
|---|---|---|---|
| `bgm_title.mp3` | タイトル画面BGM | ✓ | ❌ |
| `bgm_battle1.mp3` | バトルBGM 1（森） | ✓ | ❌ |
| `bgm_battle2.mp3` | バトルBGM 2（火山） | ✓ | ❌ |
| `bgm_battle3.mp3` | バトルBGM 3（海） | ✓ | ❌ |
| `bgm_final_boss.mp3` | ボス戦BGM | ✓ | ❌ |
| `bgm_result_clear.mp3` | クリアジングル（短） | ✗ | ❌ |
| `bgm_result_gameover.mp3` | ゲームオーバーBGM（短） | ✗ | ❌ |

## SE (`assets/audio/se/`)
| ファイル | 内容 | 状態 |
|---|---|---|
| `se_place_unit.ogg` | ユニット配置音 | ❌ |
| `se_cast_spell.ogg` | 魔法発動音 | ❌ |
| `se_attack_sword.ogg` | 剣撃音 | ❌ |
| `se_attack_arrow.ogg` | 弓矢音 | ❌ |
| `se_attack_magic.ogg` | 魔法攻撃音 | ❌ |
| `se_enemy_death.ogg` | 敵撃破音 | ❌ |
| `se_boss_death.ogg` | ボス撃破音（迫力） | ❌ |
| `se_chain_2x.ogg` | チェーン×2音 | ❌ |
| `se_chain_3x.ogg` | チェーン×3音 | ❌ |
| `se_chain_max.ogg` | MAX CHAINジングル | ❌ |
| `se_wall_damage.ogg` | 城壁ダメージ音 | ❌ |
| `se_ui_tap.ogg` | UIタップ音 | ❌ |
| `se_card_draw.ogg` | カードドロー音 | ❌ |
| `se_level_up.ogg` | レベルアップジングル | ❌ |

---

## データファイル (`assets/data/`)
| ファイル | 内容 | 状態 |
|---|---|---|
| `card_overrides.json` | カード上書き定義（将来の動的更新用） | ❌ |
| `event_table.json` | イベントテーブル（将来の動的更新用） | ❌ |

---

## 素材調達先の提案
- **ドット絵**: itch.io の CC0 / royalty-free アセット（例: "Fantasy RPG Pack"）
- **BGM**: opengameart.org / zapsplat.com
- **SE**: freesound.org / zapsplat.com
- **フォント**: Google Fonts（DotGothic16）

---

*このファイルは自動生成されました。新規アセット追加時は状態列を更新してください。*
