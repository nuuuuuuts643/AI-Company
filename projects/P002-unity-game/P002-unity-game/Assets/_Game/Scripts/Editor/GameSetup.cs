#if UNITY_EDITOR
using UnityEngine;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine.UI;
using UnityEngine.SceneManagement;
using TMPro;
using System.IO;
using System.Reflection;

namespace FortressCity.Editor
{
    public static class GameSetup
    {
        // ── Octopath-inspired palette ──────────────────────────────────
        static readonly Color C_PANEL      = new Color(0.05f, 0.02f, 0.10f, 0.97f);
        static readonly Color C_BORDER_DIM = new Color(0.45f, 0.33f, 0.05f, 1.00f);
        static readonly Color C_TEXT       = new Color(0.94f, 0.91f, 0.82f, 1.00f);
        static readonly Color C_GOLD_TXT   = new Color(1.00f, 0.84f, 0.38f, 1.00f);
        static readonly Color C_RED_TXT    = new Color(0.90f, 0.25f, 0.25f, 1.00f);
        static readonly Color C_STONE      = new Color(0.22f, 0.20f, 0.27f, 1.00f);
        static readonly Color C_STONE_LT   = new Color(0.30f, 0.28f, 0.36f, 1.00f);
        static readonly Color C_STONE_DK   = new Color(0.14f, 0.12f, 0.19f, 1.00f);

        // ── Entry point ────────────────────────────────────────────────
        static bool _pendingSetup = false;

        [MenuItem("FortressCity/Setup Everything")]
        public static void SetupEverything()
        {
            if (UnityEditor.EditorApplication.isPlaying)
            {
                _pendingSetup = true;
                UnityEditor.EditorApplication.isPlaying = false;
                UnityEditor.EditorApplication.playModeStateChanged += OnPlayModeStateChanged;
                return;
            }
            RunSetup();
        }

        static void OnPlayModeStateChanged(UnityEditor.PlayModeStateChange state)
        {
            if (state == UnityEditor.PlayModeStateChange.EnteredEditMode && _pendingSetup)
            {
                _pendingSetup = false;
                UnityEditor.EditorApplication.playModeStateChanged -= OnPlayModeStateChanged;
                RunSetup();
            }
        }

        static void RunSetup()
        {
            CreateFolders();
            SetupFont();
            var units   = CreateUnitSOs();
            var enemies = CreateEnemySOs();
            CreateWeekEventSOs();
            SetupBootScene();
            SetupCityScene(units, enemies);
            ConfigureBuildSettings();
            SetGameViewPortrait();
            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();
            Debug.Log("<color=lime>[FortressCity] Setup complete! Open Boot scene and press Play.</color>");
        }

        // ── Folders ────────────────────────────────────────────────────
        static void CreateFolders()
        {
            EnsureFolder("Assets/_Game/Data");
            EnsureFolder("Assets/_Game/Data/Units");
            EnsureFolder("Assets/_Game/Data/Enemies");
            EnsureFolder("Assets/_Game/Data/Events");
            EnsureFolder("Assets/_Game/Scenes");
            EnsureFolder("Assets/_Game/Fonts");
        }

        // ── Japanese font setup ────────────────────────────────────────
        static void SetupFont()
        {
            const string src    = "/System/Library/Fonts/\u30d2\u30e9\u30ae\u30ce\u89d2\u30b4\u30b7\u30c3\u30af W3.ttc";
            const string dstTtc = "Assets/_Game/Fonts/HiraginoW3.ttc";
            const string dstTmp = "Assets/_Game/Fonts/HiraginoW3_TMP.asset";

            if (!File.Exists(src)) { Debug.LogWarning("[FortressCity] Hiragino not found; Japanese text may show as boxes."); return; }

            if (!File.Exists(dstTtc))
            {
                File.Copy(src, dstTtc);
                AssetDatabase.ImportAsset(dstTtc, ImportAssetOptions.ForceSynchronousImport);
            }

            var baseFont = AssetDatabase.LoadAssetAtPath<Font>(dstTtc);
            if (baseFont == null) { Debug.LogWarning("[FortressCity] Could not load Hiragino font asset."); return; }

            // Delete broken asset and recreate cleanly
            if (AssetDatabase.LoadAssetAtPath<TMP_FontAsset>(dstTmp) != null)
                AssetDatabase.DeleteAsset(dstTmp);

            var tmpFont = TMP_FontAsset.CreateFontAsset(baseFont);
            tmpFont.atlasPopulationMode = AtlasPopulationMode.Dynamic;

            AssetDatabase.CreateAsset(tmpFont, dstTmp);

            // Sub-assets (atlas textures + material) must be added explicitly
            if (tmpFont.atlasTextures != null)
                foreach (var tex in tmpFont.atlasTextures)
                    if (tex != null) AssetDatabase.AddObjectToAsset(tex, dstTmp);
            if (tmpFont.material != null)
                AssetDatabase.AddObjectToAsset(tmpFont.material, dstTmp);

            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();
            s_japaneseFont = tmpFont;

            var settings = Resources.Load<TMP_Settings>("TMP Settings");
            if (settings != null)
            {
                var so = new SerializedObject(settings);
                SetRef(so, "m_defaultFontAsset", tmpFont);
                so.ApplyModifiedPropertiesWithoutUndo();
            }
        }

        // ── Set Game view to portrait ──────────────────────────────────
        static void SetGameViewPortrait()
        {
            try
            {
                var gvType   = System.Type.GetType("UnityEditor.GameView, UnityEditor");
                var sizesT   = System.Type.GetType("UnityEditor.GameViewSizes, UnityEditor");
                var gvsT     = System.Type.GetType("UnityEditor.GameViewSize, UnityEditor");
                var gvsModeT = System.Type.GetType("UnityEditor.GameViewSizeType, UnityEditor");
                if (gvType == null || sizesT == null || gvsT == null || gvsModeT == null) return;

                var inst  = sizesT.GetProperty("instance", BindingFlags.Static | BindingFlags.Public)?.GetValue(null);
                if (inst == null) return;
                var gType = inst.GetType().GetProperty("currentGroupType")?.GetValue(inst);
                var group = inst.GetType().GetMethod("GetGroup")?.Invoke(inst, new[] { gType });
                if (group == null) return;

                var fixedRes = System.Enum.Parse(gvsModeT, "FixedResolution");
                var ctor     = gvsT.GetConstructor(new[] { gvsModeT, typeof(int), typeof(int), typeof(string) });
                var newSize  = ctor?.Invoke(new[] { fixedRes, (object)1080, (object)1920, (object)"Portrait 1080x1920" });
                if (newSize == null) return;

                group.GetType().GetMethod("AddCustomSize")?.Invoke(group, new[] { newSize });
                int total = (int)(group.GetType().GetMethod("GetTotalCount")?.Invoke(group, null) ?? 0);

                var gv = EditorWindow.GetWindow(gvType, false, "Game", false);
                gvType.GetMethod("SizeSelectionCallback", BindingFlags.Instance | BindingFlags.NonPublic)
                      ?.Invoke(gv, new object[] { total - 1, newSize });
            }
            catch (System.Exception e)
            {
                Debug.LogWarning($"[FortressCity] Game view portrait setup failed: {e.Message}");
            }
        }

        static void EnsureFolder(string path)
        {
            if (!AssetDatabase.IsValidFolder(path))
            {
                var parts  = path.Split('/');
                var parent = string.Join("/", parts, 0, parts.Length - 1);
                AssetDatabase.CreateFolder(parent, parts[parts.Length - 1]);
            }
        }

        // ── ScriptableObjects ──────────────────────────────────────────
        static UnitData[] CreateUnitSOs()
        {
            var defs = new[]
            {
                // name, type, atk, hp, recruit, goldW, foodW, multiplier
                ("歩兵",   UnitType.Infantry,  12, 120, 40,  2, 1, new EnemyType[]{},                   1.5f),
                ("弓兵",   UnitType.Archer,    10, 80,  50,  2, 1, new EnemyType[]{ EnemyType.Flying },  2.0f),
                ("魔法兵", UnitType.Mage,      20, 60,  80,  3, 1, new EnemyType[]{ EnemyType.OrcHeavy },2.5f),
                ("騎兵",   UnitType.Cavalry,   15, 100, 70,  3, 2, new EnemyType[]{ EnemyType.GoblinHorde },2.0f),
                ("回復兵", UnitType.Healer,     5, 70,  60,  2, 1, new EnemyType[]{},                   1.0f),
                ("砲兵",   UnitType.Artillery, 25, 50,  100, 4, 2, new EnemyType[]{ EnemyType.Giant },   2.5f),
            };

            var result = new UnitData[defs.Length];
            for (int i = 0; i < defs.Length; i++)
            {
                var (name, type, atk, hp, rec, goldW, foodW, strong, mult) = defs[i];
                var path = $"Assets/_Game/Data/Units/{name}.asset";
                var so   = LoadOrCreate<UnitData>(path);
                so.unitName          = name;
                so.unitType          = type;
                so.baseAttack        = atk;
                so.baseHP            = hp;
                so.recruitCost       = rec;
                so.weeklyGoldCost    = goldW;
                so.weeklyFoodCost    = foodW;
                so.strongAgainst     = strong;
                so.bonusMultiplier   = mult;
                so.unitColor         = UnitColor(type);
                EditorUtility.SetDirty(so);
                result[i] = so;
            }
            return result;
        }

        static EnemyData[] CreateEnemySOs()
        {
            var defs = new[]
            {
                // name, type, trait, weakness, powerMult, count
                ("ゴブリン群",   EnemyType.GoblinHorde, "数で圧倒する群れ。個々は弱いが数が多い。",   UnitType.Cavalry,   0.8f, 80),
                ("オーク重隊",   EnemyType.OrcHeavy,    "重装備で正面突破を得意とする。",              UnitType.Mage,      1.2f, 40),
                ("ワイバーン隊", EnemyType.Flying,       "飛行で壁を無視して奇襲する。",                UnitType.Archer,    1.0f, 20),
                ("ドラゴン",     EnemyType.Giant,        "単体で圧倒的な破壊力。要塞でも貫通する。",   UnitType.Artillery, 2.0f, 5),
            };

            var result = new EnemyData[defs.Length];
            for (int i = 0; i < defs.Length; i++)
            {
                var (name, type, trait, weak, mult, count) = defs[i];
                var path = $"Assets/_Game/Data/Enemies/{name}.asset";
                var so   = LoadOrCreate<EnemyData>(path);
                so.enemyName             = name;
                so.enemyType             = type;
                so.trait                 = trait;
                so.weakness              = weak;
                so.basePowerMultiplier   = mult;
                so.baseCount             = count;
                so.enemyColor            = new Color(0.9f, 0.2f, 0.2f);
                EditorUtility.SetDirty(so);
                result[i] = so;
            }
            return result;
        }

        static void CreateWeekEventSOs()
        {
            var defs = new[]
            {
                // name, desc, prob, gold, food, pop, fort, life, inf, positive
                ("豊作",       "今週は農作物が豊作でした。食料が増えます。",        0.12f,   0,  60,  0, 0, 0,  0, true),
                ("臨時収入",   "商人の通過税が入りました。",                         0.10f,  80,   0,  0, 0, 0,  0, true),
                ("移民流入",   "新しい住民が街にやってきました。",                   0.08f,   0,   0, 15, 0, 0,  5, true),
                ("職人来訪",   "腕利きの職人が城壁を修繕してくれました。",           0.07f,   0,   0,  0, 1, 0,  0, true),
                ("訓練成功",   "今週の訓練で歩兵が精強になりました。",               0.09f,   0,   0,  0, 0, 0, 10, true),
                ("疫病",       "街で疫病が発生しました。住民が減少します。",         0.08f,   0, -20,-10, 0,-1,  0, false),
                ("軍備事故",   "訓練中に事故が発生。歩兵が減少しました。",           0.07f, -30,   0,  0, 0, 0,-8, false),
                ("魔物の小被害","近郊で小規模な魔物被害。食料と住民が減ります。",   0.06f,   0, -30, -5, 0, 0,  0, false),
            };

            foreach (var (name, desc, prob, gold, food, pop, fort, life, inf, pos) in defs)
            {
                var path = $"Assets/_Game/Data/Events/{name}.asset";
                var so   = LoadOrCreate<WeekEventData>(path);
                so.eventName    = name;
                so.description  = desc;
                so.probability  = prob;
                so.isPositive   = pos;
                so.effect       = new EventEffect
                {
                    goldDelta       = gold,
                    foodDelta       = food,
                    populationDelta = pop,
                    fortDelta       = fort,
                    lifeDelta       = life,
                    infantryDelta   = inf,
                };
                EditorUtility.SetDirty(so);
            }
        }

        // ── Boot Scene ─────────────────────────────────────────────────
        static void SetupBootScene()
        {
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

            // Persistent singletons
            var gm = new GameObject("GameManager");
            gm.AddComponent<GameManager>();

            var al = new GameObject("AudioManager");
            al.AddComponent<AudioManager>();

            var sl = new GameObject("SceneLoader");
            sl.AddComponent<SceneLoader>();

            // Boot logic
            var boot = new GameObject("BootController");
            boot.AddComponent<BootController>();

            EditorSceneManager.SaveScene(scene, "Assets/_Game/Scenes/Boot.unity");
        }

        // ── City Scene ─────────────────────────────────────────────────
        static void SetupCityScene(UnitData[] units, EnemyData[] enemies)
        {
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

            // Camera
            var camGo   = new GameObject("Main Camera");
            var cam     = camGo.AddComponent<Camera>();
            cam.clearFlags       = CameraClearFlags.SolidColor;
            cam.backgroundColor  = new Color(0.04f, 0.02f, 0.08f);
            cam.orthographic     = true;
            cam.orthographicSize = 4.5f;
            camGo.transform.position = new Vector3(0, 0, -10);
            camGo.AddComponent<CameraShake>();
            camGo.tag = "MainCamera";

            // Managers
            AddManager<TimeManager>("TimeManager");
            AddManager<CityManager>("CityManager");
            AddManager<ArmyManager>("ArmyManager");
            AddManager<BattleManager>("BattleManager");
            AddManager<ScoutManager>("ScoutManager");

            // City renderer (placeholder layers)
            var cityRender = BuildCityRenderer();

            // Assign week events to TimeManager
            var tm   = Object.FindObjectOfType<TimeManager>();
            var evSO = LoadAllAtPath<WeekEventData>("Assets/_Game/Data/Events");
            var serialTM = new SerializedObject(tm);
            var evProp   = serialTM.FindProperty("weekEvents");
            evProp.arraySize = evSO.Length;
            for (int i = 0; i < evSO.Length; i++)
                evProp.GetArrayElementAtIndex(i).objectReferenceValue = evSO[i];
            serialTM.ApplyModifiedPropertiesWithoutUndo();

            // GameManager references
            var gmComp = Object.FindObjectOfType<GameManager>();
            if (gmComp == null)
            {
                var gmGo = new GameObject("GameManager");
                gmComp = gmGo.AddComponent<GameManager>();
            }
            var serialGM = new SerializedObject(gmComp);
            SetSOArray(serialGM, "unitDataList",  units);
            SetSOArray(serialGM, "enemyDataList", enemies);
            serialGM.ApplyModifiedPropertiesWithoutUndo();

            // Canvas
            var canvasGo = BuildCanvas(camGo);

            // Battle animator
            BuildBattleAnimator(canvasGo.transform, camGo.GetComponent<CameraShake>());

            EditorSceneManager.SaveScene(scene, "Assets/_Game/Scenes/City.unity");
        }

        // ── City Renderer ──────────────────────────────────────────────
        static GameObject BuildCityRenderer()
        {
            var root = new GameObject("CityRenderer");
            var cr   = root.AddComponent<CityRenderer>();

            CityEnv(root.transform);

            var fort0 = CityFortWalls(root.transform);
            var fort1 = CityFortKeep(root.transform);
            var fort2 = CityFortOuterRing(root.transform);
            fort1.SetActive(false); fort2.SetActive(false);

            var life0 = CityLifeCluster(root.transform, 0);
            var life1 = CityLifeCluster(root.transform, 1);
            var life2 = CityLifeCluster(root.transform, 2);
            life1.SetActive(false); life2.SetActive(false);

            var army0 = CityArmyTier(root.transform, 0);
            var army1 = CityArmyTier(root.transform, 1);
            var army2 = CityArmyTier(root.transform, 2);
            army0.SetActive(false); army1.SetActive(false); army2.SetActive(false);

            var hero   = CityHeroIcon(root.transform);

            var serial = new SerializedObject(cr);
            SetGOArray(serial, "fortLayers", new[] { fort0, fort1, fort2 });
            SetGOArray(serial, "lifeLayers", new[] { life0, life1, life2 });
            SetGOArray(serial, "armyTiers",  new[] { army0, army1, army2 });
            serial.FindProperty("heroObject").objectReferenceValue = hero;
            serial.ApplyModifiedPropertiesWithoutUndo();
            return root;
        }

        // world-space quad (sortingOrder controls draw order)
        static GameObject Quad(string name, Transform parent, Color color, Vector3 pos, Vector2 size, int order = 10)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);
            go.transform.localPosition = pos;
            go.transform.localScale    = new Vector3(size.x, size.y, 1f);
            var sr = go.AddComponent<SpriteRenderer>();
            sr.sprite = CreateSolidSprite(color); sr.sortingOrder = order;
            return go;
        }

        static void CityEnv(Transform p)
        {
            Quad("SkyTop", p, new Color(0.04f,0.02f,0.10f), new Vector3(0, 2.5f,0), new Vector2(8,5), -10);
            Quad("SkyBot", p, new Color(0.08f,0.04f,0.18f), new Vector3(0,-0.5f,0), new Vector2(8,5),  -9);
            var rng = new System.Random(777);
            for (int i=0;i<55;i++)
            {
                float sx=(float)(rng.NextDouble()*6-3), sy=(float)(rng.NextDouble()*3.5f+1.2f);
                float br=(float)(rng.NextDouble()*0.5+0.5), sz=(float)(rng.NextDouble()*0.04+0.02);
                Quad($"S{i}",p,new Color(0.9f,0.88f,0.85f,br),new Vector3(sx,sy,0),Vector2.one*sz,-8);
            }
            Quad("Mtn1",p,new Color(0.10f,0.06f,0.18f),new Vector3(-3.2f,-0.4f,0),new Vector2(3.5f,3.2f),2);
            Quad("Mtn2",p,new Color(0.08f,0.05f,0.14f),new Vector3( 3.5f,-0.5f,0),new Vector2(3.2f,3.0f),2);
            Quad("Mtn3",p,new Color(0.07f,0.04f,0.12f),new Vector3( 0.2f,-0.7f,0),new Vector2(2.2f,2.8f),2);
            Quad("Ground",    p,new Color(0.08f,0.05f,0.02f),new Vector3(0,-2.7f,0),new Vector2(8,2.5f),5);
            Quad("GroundLine",p,new Color(0.18f,0.12f,0.04f),new Vector3(0,-1.85f,0),new Vector2(8,0.09f),6);
        }

        static GameObject CityFortWalls(Transform p)
        {
            var r = new GameObject("Fort_Walls"); r.transform.SetParent(p, false);
            Quad("WallBody", r.transform,C_STONE,   new Vector3(0,-1.58f,0),new Vector2(4.8f,1.22f),10);
            Quad("WallHi",   r.transform,C_STONE_LT,new Vector3(0,-0.98f,0),new Vector2(4.8f,0.07f),11);
            foreach (var bx in new[]{-2.05f,-1.38f,-0.68f,0f,0.68f,1.38f,2.05f})
                Quad("M",r.transform,C_STONE,new Vector3(bx,-0.76f,0),new Vector2(0.38f,0.48f),11);
            Quad("TL",   r.transform,C_STONE_DK,new Vector3(-2.32f,-0.92f,0),new Vector2(0.96f,2.62f),10);
            Quad("TLCap",r.transform,C_STONE,   new Vector3(-2.32f,-0.10f,0),new Vector2(1.14f,0.22f),11);
            foreach (var bx in new[]{-2.62f,-2.32f,-2.02f})
                Quad("TLM",r.transform,C_STONE,new Vector3(bx,0.10f,0),new Vector2(0.26f,0.30f),12);
            Quad("TR",   r.transform,C_STONE_DK,new Vector3( 2.32f,-0.92f,0),new Vector2(0.96f,2.62f),10);
            Quad("TRCap",r.transform,C_STONE,   new Vector3( 2.32f,-0.10f,0),new Vector2(1.14f,0.22f),11);
            foreach (var bx in new[]{ 2.02f, 2.32f, 2.62f})
                Quad("TRM",r.transform,C_STONE,new Vector3(bx,0.10f,0),new Vector2(0.26f,0.30f),12);
            Quad("Gate",    r.transform,new Color(0.04f,0.02f,0.07f),new Vector3(0,-1.82f,0),new Vector2(0.75f,0.85f),12);
            Quad("GateArch",r.transform,new Color(0.08f,0.04f,0.12f),new Vector3(0,-1.44f,0),new Vector2(0.75f,0.22f),12);
            for (int i=0;i<3;i++) Quad($"PC{i}",r.transform,new Color(0.12f,0.08f,0.16f),new Vector3(0,-1.68f+i*0.2f,0),new Vector2(0.72f,0.04f),13);
            Quad("FlagPole",r.transform,new Color(0.42f,0.34f,0.18f),new Vector3(-2.32f,0.72f,0),new Vector2(0.06f,1.05f),12);
            Quad("FlagBan", r.transform,new Color(0.68f,0.10f,0.10f),new Vector3(-2.10f,0.84f,0),new Vector2(0.36f,0.38f),13);
            return r;
        }

        static GameObject CityFortKeep(Transform p)
        {
            var r = new GameObject("Fort_Keep"); r.transform.SetParent(p, false);
            Quad("KeepBG",  r.transform,C_STONE_DK,new Vector3(0,-0.38f,0),new Vector2(1.52f,3.28f), 9);
            Quad("KeepFace",r.transform,C_STONE,   new Vector3(0,-0.38f,0),new Vector2(1.32f,3.06f), 9);
            Quad("KeepCap", r.transform,C_STONE,   new Vector3(0, 1.14f,0),new Vector2(1.72f,0.22f),10);
            foreach (var bx in new[]{-0.66f,-0.28f,0f,0.28f,0.66f})
                Quad("KM",r.transform,C_STONE,new Vector3(bx,1.33f,0),new Vector2(0.22f,0.30f),11);
            Quad("Win1",  r.transform,new Color(0.04f,0.02f,0.08f),new Vector3(0, 0.62f,0),new Vector2(0.22f,0.36f),11);
            Quad("Win2",  r.transform,new Color(0.04f,0.02f,0.08f),new Vector3(0,-0.20f,0),new Vector2(0.22f,0.36f),11);
            Quad("WinGlow",r.transform,new Color(0.50f,0.44f,0.10f,0.4f),new Vector3(0,0.62f,0),new Vector2(0.18f,0.28f),12);
            Quad("KFlagPole",r.transform,new Color(0.42f,0.34f,0.18f),new Vector3(0,2.08f,0),new Vector2(0.06f,1.48f),12);
            Quad("KBanner",  r.transform,new Color(0.72f,0.52f,0.05f),new Vector3(0.22f,2.34f,0),new Vector2(0.42f,0.52f),13);
            Quad("KBanSym",  r.transform,new Color(0.20f,0.08f,0.02f),new Vector3(0.22f,2.34f,0),new Vector2(0.18f,0.18f),14);
            return r;
        }

        static GameObject CityFortOuterRing(Transform p)
        {
            var r = new GameObject("Fort_OuterRing"); r.transform.SetParent(p, false);
            Quad("OWall",r.transform,C_STONE_DK,new Vector3(0,-1.68f,0),new Vector2(5.8f,0.78f),8);
            for (int i=0;i<9;i++) Quad($"OM{i}",r.transform,C_STONE,new Vector3(-2.5f+i*0.62f,-1.34f,0),new Vector2(0.30f,0.40f),9);
            Quad("OTL",r.transform,C_STONE_DK,new Vector3(-2.95f,-1.48f,0),new Vector2(0.55f,1.25f),8);
            Quad("OTR",r.transform,C_STONE_DK,new Vector3( 2.95f,-1.48f,0),new Vector2(0.55f,1.25f),8);
            return r;
        }

        static GameObject CityLifeCluster(Transform p, int level)
        {
            var r = new GameObject($"Life_{level+1}"); r.transform.SetParent(p, false);
            var wall=new Color(0.28f,0.22f,0.15f); var roof=new Color(0.38f,0.15f,0.07f);
            if (level==0)
            {
                Quad("H1W",r.transform,wall,new Vector3(1.60f,-2.04f,0),new Vector2(0.55f,0.52f),9);
                Quad("H1R",r.transform,roof,new Vector3(1.60f,-1.73f,0),new Vector2(0.62f,0.24f),10);
                Quad("H2W",r.transform,wall,new Vector3(2.12f,-2.10f,0),new Vector2(0.48f,0.44f),9);
                Quad("H2R",r.transform,new Color(0.28f,0.10f,0.04f),new Vector3(2.12f,-1.83f,0),new Vector2(0.54f,0.22f),10);
                Quad("H3W",r.transform,new Color(0.24f,0.18f,0.12f),new Vector3(1.85f,-2.15f,0),new Vector2(0.42f,0.36f),9);
                Quad("H3R",r.transform,roof,new Vector3(1.85f,-1.94f,0),new Vector2(0.48f,0.20f),10);
            }
            else if (level==1)
            {
                Quad("MktW",r.transform,new Color(0.30f,0.24f,0.17f),new Vector3(-1.55f,-1.88f,0),new Vector2(0.65f,0.72f),9);
                Quad("MktR",r.transform,new Color(0.18f,0.34f,0.14f),new Vector3(-1.55f,-1.50f,0),new Vector2(0.72f,0.28f),10);
                Quad("LhW", r.transform,wall,new Vector3(-1.88f,-2.00f,0),new Vector2(0.52f,0.60f),9);
                Quad("LhR", r.transform,new Color(0.30f,0.11f,0.05f),new Vector3(-1.88f,-1.68f,0),new Vector2(0.58f,0.24f),10);
                Quad("ShW", r.transform,wall,new Vector3(-1.22f,-2.10f,0),new Vector2(0.44f,0.38f),9);
                Quad("ShR", r.transform,roof,new Vector3(-1.22f,-1.88f,0),new Vector2(0.50f,0.20f),10);
            }
            else
            {
                Quad("TvW", r.transform,new Color(0.32f,0.25f,0.14f),new Vector3(0.88f,-1.72f,0),new Vector2(0.82f,1.02f),9);
                Quad("TvR", r.transform,new Color(0.44f,0.17f,0.07f),new Vector3(0.88f,-1.18f,0),new Vector2(0.90f,0.30f),10);
                Quad("Sign",r.transform,new Color(0.55f,0.42f,0.08f),new Vector3(1.28f,-1.58f,0),new Vector2(0.18f,0.28f),11);
                Quad("ExW", r.transform,new Color(0.25f,0.19f,0.12f),new Vector3(2.38f,-1.94f,0),new Vector2(0.50f,0.66f),9);
                Quad("ExR", r.transform,new Color(0.18f,0.34f,0.14f),new Vector3(2.38f,-1.58f,0),new Vector2(0.56f,0.26f),10);
            }
            return r;
        }

        static GameObject CityArmyTier(Transform p, int tier)
        {
            var r = new GameObject($"Army_Tier{tier+1}"); r.transform.SetParent(p, false);
            int n = tier==0?2:tier==1?4:6; float sp = tier==0?1.0f:tier==1?1.7f:2.1f;
            for (int i=0;i<n;i++)
            {
                float x = n>1 ? Mathf.Lerp(-sp,sp,i/(float)(n-1)) : 0;
                var fc = tier<2 ? new Color(0.65f,0.10f,0.10f) : new Color(0.72f,0.54f,0.06f);
                Quad($"Pole{i}",r.transform,new Color(0.38f,0.30f,0.18f),new Vector3(x,-2.10f,0),new Vector2(0.05f,0.70f),13);
                Quad($"Flag{i}",r.transform,fc,new Vector3(x+0.08f,-1.82f,0),new Vector2(0.22f,0.25f),14);
            }
            if (tier>=1) { int cnt=tier==1?6:10; for (int i=0;i<cnt;i++) Quad($"Sld{i}",r.transform,new Color(0.30f,0.30f,0.42f),new Vector3(-2.0f+i*(4.0f/(cnt-1)),-2.20f,0),new Vector2(0.17f,0.28f),13); }
            return r;
        }

        static GameObject CityHeroIcon(Transform p)
        {
            var r = new GameObject("Hero_Icon"); r.transform.SetParent(p, false);
            Quad("Glow",r.transform,new Color(0.90f,0.75f,0.10f,0.22f),new Vector3(0,1.80f,0),new Vector2(0.72f,0.72f),14);
            Quad("Cape",r.transform,new Color(0.50f,0.08f,0.08f),new Vector3(-0.04f,1.72f,0),new Vector2(0.38f,0.36f),14);
            Quad("Body",r.transform,new Color(0.85f,0.70f,0.10f),new Vector3(0,1.78f,0),new Vector2(0.28f,0.42f),15);
            Quad("Head",r.transform,new Color(0.88f,0.73f,0.12f),new Vector3(0,2.05f,0),new Vector2(0.22f,0.22f),15);
            foreach (var (hx,hy) in new[]{(-0.22f,1.96f),(0.22f,1.96f),(0f,2.28f)})
                Quad("Star",r.transform,new Color(1f,0.90f,0.30f),new Vector3(hx,hy,0),Vector2.one*0.09f,16);
            return r;
        }

        static Sprite CreateSolidSprite(Color color)
        {
            var tex = new Texture2D(4, 4);
            var pixels = new Color[16];
            for (int i = 0; i < 16; i++) pixels[i] = color;
            tex.SetPixels(pixels);
            tex.Apply();
            tex.filterMode = FilterMode.Point;
            return Sprite.Create(tex, new Rect(0, 0, 4, 4), new Vector2(0.5f, 0.5f), 4f);
        }

        // ── Canvas & UI ────────────────────────────────────────────────
        // Styled panel: dark fill with gold border. Returns inner content GO.
        static GameObject MakeStyledPanel(Transform parent, string name, Vector2 aMin, Vector2 aMax, Vector2 size, Vector2 pos)
        {
            var outer = new GameObject(name + "_Frame");
            outer.transform.SetParent(parent, false);
            outer.AddComponent<Image>().color = C_BORDER_DIM;
            var ort = outer.GetComponent<RectTransform>();
            ort.anchorMin = aMin; ort.anchorMax = aMax; ort.sizeDelta = size; ort.anchoredPosition = pos;
            var inner = new GameObject(name);
            inner.transform.SetParent(outer.transform, false);
            inner.AddComponent<Image>().color = C_PANEL;
            var irt = inner.GetComponent<RectTransform>();
            irt.anchorMin = Vector2.zero; irt.anchorMax = Vector2.one;
            irt.sizeDelta = new Vector2(-6f, -6f); irt.anchoredPosition = Vector2.zero;
            return inner;
        }

        static GameObject BuildCanvas(GameObject camGo)
        {
            var canvasGo = new GameObject("Canvas");
            var canvas   = canvasGo.AddComponent<Canvas>();
            canvas.renderMode        = RenderMode.ScreenSpaceOverlay;
            canvas.sortingOrder      = 0;
            var scaler               = canvasGo.AddComponent<CanvasScaler>();
            scaler.uiScaleMode       = CanvasScaler.ScaleMode.ScaleWithScreenSize;
            scaler.referenceResolution = new Vector2(1080, 1920);
            scaler.matchWidthOrHeight  = 0.5f;
            canvasGo.AddComponent<GraphicRaycaster>();
            var evSys = new GameObject("EventSystem");
            evSys.AddComponent<UnityEngine.EventSystems.EventSystem>();
            evSys.AddComponent<UnityEngine.EventSystems.StandaloneInputModule>();

            var T = canvasGo.transform;

            // ── HUD (top, opaque) ─────────────────────────────────────
            var hudInner = MakeStyledPanel(T,"StatPanel",new Vector2(0,1),new Vector2(1,1),new Vector2(0,190),new Vector2(0,-95));
            var hudRoot  = hudInner.transform.parent.gameObject;
            var goldTxt  = MakeTMP(hudInner.transform,"GoldText",  "<color=#FFD040>◆</color> 500G",new Vector2(-300, 44),40);
            var foodTxt  = MakeTMP(hudInner.transform,"FoodText",  "<color=#60D080>◆</color> 300F",new Vector2(   0, 44),40);
            var popTxt   = MakeTMP(hudInner.transform,"PopText",   "<color=#60A0E0>◆</color> 100", new Vector2( 300, 44),40);
            var fortTxt    = MakeTMP(hudInner.transform,"FortText",  "Fort  Lv1",new Vector2(-270,-28),34,new Color(0.9f,0.7f,0.3f));
            var lifeTxt    = MakeTMP(hudInner.transform,"LifeText",  "Life  Lv1",new Vector2( 270,-28),34,new Color(0.8f,0.3f,0.5f));
            var fortHPTxt  = MakeTMP(hudInner.transform,"FortHPText","城HP 200/200",new Vector2(0,-62),30,new Color(0.6f,0.9f,0.6f));

            // ── Week / Month floating over city ───────────────────────
            var wkPnl  = MakePanel(T,"WeekPanel",new Vector2(0,1),new Vector2(1,1),new Vector2(0,115),new Vector2(0,-255));
            wkPnl.GetComponent<Image>().color = Color.clear;
            var weekTxt  = MakeTMP(wkPnl.transform,"WeekText",  "◆  Week 1  ◆",Vector2.up*22,52,C_GOLD_TXT);
            var monthTxt = MakeTMP(wkPnl.transform,"MonthText", "Month 1",    -Vector2.up*35,38,C_TEXT);

            // ── Hero status floating ──────────────────────────────────
            var heroPnl   = MakePanel(T,"HeroStatusPanel",new Vector2(0,1),new Vector2(1,1),new Vector2(0,58),new Vector2(0,-370));
            heroPnl.GetComponent<Image>().color = Color.clear;
            var heroTxt   = MakeTMP(heroPnl.transform,"HeroText",  "◆ 勇者 在陣",        Vector2.up*18, 36,new Color(1f,0.85f,0.35f));
            var heroLvTxt = MakeTMP(heroPnl.transform,"HeroLevelText","Lv1  0/120XP", -Vector2.up*16,28,new Color(0.8f,0.75f,0.5f));
            var heroRevPanel = MakePanel(heroPnl.transform,"HeroRevivePanel",new Vector2(0.5f,0.5f),new Vector2(0.5f,0.5f),new Vector2(500,52),Vector2.zero);
            heroRevPanel.GetComponent<Image>().color = new Color(0.35f,0.04f,0.04f,0.92f);
            heroRevPanel.SetActive(false);
            var heroRevTxt = MakeTMP(heroRevPanel.transform,"HeroReviveText","復帰まで 3 週",Vector2.zero,34,C_RED_TXT);

            // ── Army panel ────────────────────────────────────────────
            var armyInner = MakeStyledPanel(T,"ArmyPanel",new Vector2(0,0),new Vector2(1,0),new Vector2(0,300),new Vector2(0,330));
            MakeTMP(armyInner.transform,"ArmyTitle","◆  軍 勢  ◆",new Vector2(0,118),38,C_GOLD_TXT);
            MakeTMP(armyInner.transform,"ArmyDiv","─────────────────────────────────",new Vector2(0,82),24,new Color(0.6f,0.45f,0.1f,0.8f));
            var infTxt  = MakeTMP(armyInner.transform,"InfantryText",  "歩兵    20",new Vector2(-265, 42),36);
            var arcTxt  = MakeTMP(armyInner.transform,"ArcherText",    "弓兵    10",new Vector2(-265, -8),36);
            var magTxt  = MakeTMP(armyInner.transform,"MageText",      "魔法兵   5",new Vector2(-265,-58),36);
            var cavTxt  = MakeTMP(armyInner.transform,"CavalryText",   "騎兵     5",new Vector2( 215, 42),36);
            var healTxt = MakeTMP(armyInner.transform,"HealerText",    "回復兵   5",new Vector2( 215, -8),36);
            var artTxt  = MakeTMP(armyInner.transform,"ArtilleryText", "砲兵     2",new Vector2( 215,-58),36);

            // ── Button panel ──────────────────────────────────────────
            var btnRoot = MakePanel(T,"ButtonPanel",new Vector2(0,0),new Vector2(1,0),new Vector2(0,180),new Vector2(0,90));
            btnRoot.GetComponent<Image>().color = new Color(0.04f,0.02f,0.09f,1f);
            var advBtn   = MakeButton(btnRoot.transform,"AdvanceWeekButton","1週進める",  new Vector2(-240,0),new Vector2(400,140),new Color(0.35f,0.22f,0.05f));
            var manBtn   = MakeButton(btnRoot.transform,"ManageButton",     "管理/投資",  new Vector2( 170,0),new Vector2(280,140),new Color(0.05f,0.08f,0.22f));
            var helpBtn  = MakeButton(btnRoot.transform,"HelpButton",       "？",          new Vector2( 460,0),new Vector2(100,140),new Color(0.12f,0.10f,0.25f));
            var raidBtn  = MakeButton(btnRoot.transform,"RaidButton",       "襲撃対応！",new Vector2(-240,0),new Vector2(420,140),new Color(0.40f,0.04f,0.04f));
            var scoutBtn = MakeButton(btnRoot.transform,"ScoutButton",      "偵察する",   new Vector2( 240,0),new Vector2(340,140),new Color(0.05f,0.12f,0.30f));
            raidBtn.SetActive(false); scoutBtn.SetActive(false);

            // ── Manage panel ──────────────────────────────────────────
            var managePanel = MakeStyledPanel(T,"ManagePanel",new Vector2(0.5f,0.5f),new Vector2(0.5f,0.5f),new Vector2(920,1160),Vector2.zero);
            var managePanelRoot = managePanel.transform.parent.gameObject;
            managePanelRoot.SetActive(false);
            MakeTMP(managePanel.transform,"Title","◆  管 理  ◆",new Vector2(0,498),56,C_GOLD_TXT);
            MakeTMP(managePanel.transform,"ManDiv","─────────────────────────────────",new Vector2(0,452),24,new Color(0.6f,0.45f,0.1f,0.8f));
            var fortCostTxt = MakeTMP(managePanel.transform,"FortCostText","Fort  Lv1 → 2  |  150G",new Vector2(0,400),36,C_TEXT);
            var lifeCostTxt = MakeTMP(managePanel.transform,"LifeCostText","Life  Lv1 → 2  |  150G",new Vector2(0,340),36,C_TEXT);
            var upgFortBtn  = MakeButton(managePanel.transform,"UpgradeFortButton","砦 強化",  new Vector2(-230,268),new Vector2(340,110),new Color(0.30f,0.15f,0.03f));
            var upgLifeBtn  = MakeButton(managePanel.transform,"UpgradeLifeButton","民力 強化",new Vector2( 230,268),new Vector2(340,110),new Color(0.05f,0.25f,0.08f));
            MakeTMP(managePanel.transform,"RecTitle","──  徴 兵  ──",new Vector2(0,192),42,C_GOLD_TXT);
            var unitNames = new[]{"歩兵 ×5","弓兵 ×5","魔法兵 ×5","騎兵 ×5","回復兵 ×5","砲兵 ×5"};
            var recBtns  = new GameObject[6]; var recCosts = new GameObject[6];
            for (int i=0;i<6;i++) {
                float y = 110-i*90;
                recBtns[i]  = MakeButton(managePanel.transform,$"RecruitBtn_{i}",unitNames[i],new Vector2(-200,y),new Vector2(320,78),new Color(0.06f,0.10f,0.28f));
                recCosts[i] = MakeTMP(managePanel.transform,$"RecruitCost_{i}","200G",new Vector2(230,y),34,C_GOLD_TXT);
            }
            var closeManage = MakeButton(managePanel.transform,"CloseButton","閉じる",new Vector2(0,-498),new Vector2(320,100),new Color(0.12f,0.06f,0.22f));

            // ── Raid panel ────────────────────────────────────────────
            var raidPanel = MakeStyledPanel(T,"RaidPanel",new Vector2(0.5f,0.5f),new Vector2(0.5f,0.5f),new Vector2(920,1300),Vector2.zero);
            var raidPanelRoot = raidPanel.transform.parent.gameObject;
            raidPanelRoot.SetActive(false);
            MakeTMP(raidPanel.transform,"Title","◆  月 末 襲 撃  ◆",new Vector2(0,566),52,C_RED_TXT);
            MakeTMP(raidPanel.transform,"RDiv","─────────────────────────────────",new Vector2(0,520),24,new Color(0.6f,0.1f,0.1f,0.8f));
            var enemyNameTxt = MakeTMP(raidPanel.transform,"EnemyNameText",    "???",       new Vector2(0,462),52,C_RED_TXT);
            var enemyPowTxt  = MakeTMP(raidPanel.transform,"EnemyPowerText",   "戦力: ???", new Vector2(0,396),38,C_TEXT);
            var enemyWeakTxt = MakeTMP(raidPanel.transform,"EnemyWeaknessText","弱点: ???", new Vector2(0,336),38,C_TEXT);
            var unknownOverlay = MakePanel(raidPanel.transform,"UnknownOverlay",new Vector2(0.5f,0.5f),new Vector2(0.5f,0.5f),new Vector2(640,108),new Vector2(0,424));
            unknownOverlay.GetComponent<Image>().color = new Color(0.15f,0.05f,0.05f,0.92f);
            MakeTMP(unknownOverlay.transform,"T","◇ 偵察未実施 — 敵は不明 ◇",Vector2.zero,32,new Color(0.6f,0.5f,0.5f));
            unknownOverlay.SetActive(false);
            MakeTMP(raidPanel.transform,"FormTitle","──  編 成  ──",new Vector2(0,264),40,C_GOLD_TXT);
            var fullBtn  = MakeButton(raidPanel.transform,"FullBtn",    "全軍",    new Vector2(-330,192),new Vector2(190,88),new Color(0.35f,0.08f,0.08f));
            var balBtn   = MakeButton(raidPanel.transform,"BalancedBtn","均衡",    new Vector2(-110,192),new Vector2(190,88),new Color(0.05f,0.15f,0.38f));
            var resBtn   = MakeButton(raidPanel.transform,"ReserveBtn", "温存",    new Vector2( 110,192),new Vector2(190,88),new Color(0.05f,0.22f,0.08f));
            var weakBtn  = MakeButton(raidPanel.transform,"WeaknessBtn","弱点特化",new Vector2( 330,192),new Vector2(190,88),new Color(0.25f,0.10f,0.35f));
            var heroToggle = MakeToggle(raidPanel.transform,"HeroToggle","勇者を出陣させる",new Vector2(0,98));
            var deployPreviewTxt = MakeTMP(raidPanel.transform,"DeployPreviewText","歩:20 弓:10 魔:5\n騎:5 回:5 砲:2\n合計:47",new Vector2(0,-28),36,new Color(0.7f,0.85f,1f));
            var deployBtn = MakeButton(raidPanel.transform,"DeployButton","出 撃 ！",new Vector2(0,-220),new Vector2(460,140),new Color(0.50f,0.05f,0.05f));
            var closeRaid = MakeButton(raidPanel.transform,"CloseRaidBtn","戻る",      new Vector2(0,-390),new Vector2(280, 90),new Color(0.10f,0.05f,0.20f));

            // ── Result panel ──────────────────────────────────────────
            var resultPanel = MakeStyledPanel(T,"BattleResultPanel",new Vector2(0.5f,0.5f),new Vector2(0.5f,0.5f),new Vector2(920,1100),Vector2.zero);
            var resultPanelRoot = resultPanel.transform.parent.gameObject;
            resultPanelRoot.SetActive(false);
            var resultTitle = MakeTMP(resultPanel.transform,"TitleText","Victory!",   new Vector2(0,428),88,C_GOLD_TXT);
            MakeTMP(resultPanel.transform,"ResDiv","─────────────────────────────────",new Vector2(0,348),24,new Color(0.6f,0.45f,0.1f,0.8f));
            var powerTxt    = MakeTMP(resultPanel.transform,"PowerText",      "戦力比: ---",new Vector2(0,296),40,C_TEXT);
            var casualTxt   = MakeTMP(resultPanel.transform,"CasualtiesText", "損耗: ---",  new Vector2(0,216),38,C_TEXT);
            var rewardTxt   = MakeTMP(resultPanel.transform,"RewardText",     "報酬: ---",  new Vector2(0,140),38,C_GOLD_TXT);
            var fortDmgTxt  = MakeTMP(resultPanel.transform,"FortHPText",     "城ダメージ: ---",new Vector2(0, 68),36,new Color(1f,0.5f,0.3f));
            var xpTxt       = MakeTMP(resultPanel.transform,"XPText",         "勇者XP: ---",new Vector2(0,  0),36,new Color(0.6f,1f,0.7f));
            var heroResTxt  = MakeTMP(resultPanel.transform,"HeroResultText", "",           new Vector2(0,-64),36,C_RED_TXT);
            var contBtn     = MakeButton(resultPanel.transform,"ContinueButton","次の月へ →",new Vector2(0,-380),new Vector2(480,130),new Color(0.06f,0.15f,0.35f));

            // ── Event panel ───────────────────────────────────────────
            var eventPanel = MakeStyledPanel(T,"EventPanel",new Vector2(0.5f,0.5f),new Vector2(0.5f,0.5f),new Vector2(880,650),Vector2.zero);
            var eventPanelRoot = eventPanel.transform.parent.gameObject;
            eventPanelRoot.SetActive(false);
            var evTitleTxt = MakeTMP(eventPanel.transform,"EventTitleText","週イベント",new Vector2(0,236),52,C_GOLD_TXT);
            MakeTMP(eventPanel.transform,"EvDiv","─────────────────────────────────",new Vector2(0,188),24,new Color(0.6f,0.45f,0.1f,0.8f));
            var evDescTxt  = MakeTMP(eventPanel.transform,"EventDescText","内容...",    new Vector2(0, 20),36,C_TEXT);
            evDescTxt.GetComponent<TextMeshProUGUI>().enableWordWrapping = true;
            var evDismiss  = MakeButton(eventPanel.transform,"DismissButton","OK",      new Vector2(0,-224),new Vector2(280,100),new Color(0.06f,0.22f,0.10f));
            var evChoiceA  = MakeButton(eventPanel.transform,"ChoiceAButton","選択A",   new Vector2(-200,-190),new Vector2(340,100),new Color(0.06f,0.22f,0.10f));
            var evChoiceB  = MakeButton(eventPanel.transform,"ChoiceBButton","選択B",   new Vector2( 200,-190),new Vector2(340,100),new Color(0.25f,0.08f,0.08f));
            evChoiceA.SetActive(false);
            evChoiceB.SetActive(false);

            // ── Weekly Action panel ───────────────────────────────────
            var waPanel = MakeStyledPanel(T,"WeeklyActionPanel",new Vector2(0.5f,0),new Vector2(0.5f,0),new Vector2(920,680),new Vector2(0,360));
            var waPanelRoot = waPanel.transform.parent.gameObject;
            waPanelRoot.SetActive(false);
            var waHeader = MakeTMP(waPanel.transform,"WAHeader","今週の行動を選べ",new Vector2(0,280),46,C_GOLD_TXT);
            MakeTMP(waPanel.transform,"WADiv","─────────────────────────────────",new Vector2(0,238),24,new Color(0.6f,0.45f,0.1f,0.8f));
            string[] waLabels = {"訓練\n歩兵+15 食-25","徴税\nGold+130","修繕\n城HP+80 Gold-100","偵察\n敵情報入手","民政\n人口+25 食+20"};
            var waButtons = new GameObject[5]; var waTexts = new TextMeshProUGUI[5];
            for (int i=0;i<5;i++) {
                float x = (i%3-1)*290f; float y = i<3 ? 140 : -20;
                waButtons[i] = MakeButton(waPanel.transform,$"WA_{i}",waLabels[i],new Vector2(x,y),new Vector2(256,148),new Color(0.06f,0.12f,0.28f));
                waTexts[i]   = waButtons[i].GetComponentInChildren<TextMeshProUGUI>();
            }
            var waUI    = waPanelRoot.AddComponent<WeeklyActionUI>();
            var serialWA = new SerializedObject(waUI);
            var waBtnProp = serialWA.FindProperty("actionButtons"); waBtnProp.arraySize=5;
            for (int i=0;i<5;i++) waBtnProp.GetArrayElementAtIndex(i).objectReferenceValue = waButtons[i].GetComponentInChildren<Button>();
            SetRef(serialWA,"headerText", waHeader.GetComponent<TextMeshProUGUI>());
            serialWA.ApplyModifiedPropertiesWithoutUndo();

            // ── Level Up panel ────────────────────────────────────────
            var luPanel = MakeStyledPanel(T,"LevelUpPanel",new Vector2(0.5f,0.5f),new Vector2(0.5f,0.5f),new Vector2(920,900),Vector2.zero);
            var luPanelRoot = luPanel.transform.parent.gameObject;
            luPanelRoot.SetActive(false);
            var luTitle = MakeTMP(luPanel.transform,"LUTitle","Level Up!\nスキルを選べ",new Vector2(0,360),56,C_GOLD_TXT);
            MakeTMP(luPanel.transform,"LUDiv","─────────────────────────────────",new Vector2(0,268),24,new Color(0.6f,0.45f,0.1f,0.8f));
            var luButtons = new GameObject[3]; var luLabels = new TextMeshProUGUI[3];
            for (int i=0;i<3;i++) {
                luButtons[i] = MakeButton(luPanel.transform,$"SkillBtn_{i}",$"スキル{i+1}",new Vector2(0,180-i*200),new Vector2(760,170),new Color(0.10f,0.06f,0.28f));
                luLabels[i]  = luButtons[i].GetComponentInChildren<TextMeshProUGUI>();
            }
            var luUI    = luPanelRoot.AddComponent<LevelUpUI>();
            var serialLU = new SerializedObject(luUI);
            SetRef(serialLU,"titleText", luTitle.GetComponent<TextMeshProUGUI>());
            var luBtnProp = serialLU.FindProperty("skillButtons"); luBtnProp.arraySize=3;
            var luLblProp = serialLU.FindProperty("skillLabels");  luLblProp.arraySize=3;
            for (int i=0;i<3;i++) {
                luBtnProp.GetArrayElementAtIndex(i).objectReferenceValue = luButtons[i].GetComponentInChildren<Button>();
                luLblProp.GetArrayElementAtIndex(i).objectReferenceValue = luLabels[i];
            }
            serialLU.ApplyModifiedPropertiesWithoutUndo();

            // ── Game Over / Victory panel ─────────────────────────────
            var goPanel = MakeStyledPanel(T,"GameOverPanel",new Vector2(0.5f,0.5f),new Vector2(0.5f,0.5f),new Vector2(920,680),Vector2.zero);
            var goPanelRoot = goPanel.transform.parent.gameObject;
            goPanelRoot.SetActive(false);
            var goTitle    = MakeTMP(goPanel.transform,"GOTitle",   "城が落ちた...",new Vector2(0,236),72,C_RED_TXT);
            var goSubtitle = MakeTMP(goPanel.transform,"GOSubtitle","Month X で敗北", new Vector2(0, 80),38,C_TEXT);
            goSubtitle.GetComponent<TextMeshProUGUI>().enableWordWrapping = true;
            var goReplay   = MakeButton(goPanel.transform,"ReplayButton","もう一度", new Vector2(0,-224),new Vector2(360,120),new Color(0.20f,0.08f,0.35f));
            var goUI = goPanelRoot.AddComponent<GameOverUI>();
            var serialGO = new SerializedObject(goUI);
            SetRef(serialGO,"titleText",    goTitle.GetComponent<TextMeshProUGUI>());
            SetRef(serialGO,"subtitleText", goSubtitle.GetComponent<TextMeshProUGUI>());
            SetRef(serialGO,"replayButton", goReplay.GetComponentInChildren<Button>());
            serialGO.ApplyModifiedPropertiesWithoutUndo();

            // ── How To Play panel ─────────────────────────────────────
            var htpPanel = MakeStyledPanel(T,"HowToPlayPanel",new Vector2(0.5f,0.5f),new Vector2(0.5f,0.5f),new Vector2(920,1100),Vector2.zero);
            var htpPanelRoot = htpPanel.transform.parent.gameObject;
            htpPanelRoot.SetActive(false);
            var htpPage = MakeTMP(htpPanel.transform,"PageText","1 / 7",new Vector2(0,450),34,new Color(0.6f,0.5f,0.3f));
            MakeTMP(htpPanel.transform,"HTPTitle","◆  遊 び 方  ◆",new Vector2(0,400),48,C_GOLD_TXT);
            MakeTMP(htpPanel.transform,"HTPDiv","─────────────────────────────────",new Vector2(0,358),24,new Color(0.6f,0.45f,0.1f,0.8f));
            var htpBody  = MakeTMP(htpPanel.transform,"BodyText","...",new Vector2(0,60),36,C_TEXT);
            htpBody.GetComponent<TextMeshProUGUI>().enableWordWrapping = true;
            var htpPrev  = MakeButton(htpPanel.transform,"PrevButton","< 前",  new Vector2(-300,-390),new Vector2(240,110),new Color(0.10f,0.08f,0.22f));
            var htpNext  = MakeButton(htpPanel.transform,"NextButton","次 >",  new Vector2( 300,-390),new Vector2(240,110),new Color(0.10f,0.08f,0.22f));
            var htpClose = MakeButton(htpPanel.transform,"CloseButton","閉じる",new Vector2(0,-390),new Vector2(240,110),new Color(0.06f,0.18f,0.10f));
            var htpUI    = htpPanelRoot.AddComponent<HowToPlayUI>();
            htpPanelRoot.AddComponent<CanvasGroup>();
            htpPanelRoot.AddComponent<AnimatedPanel>();
            var serialHTP = new SerializedObject(htpUI);
            SetRef(serialHTP,"closeButton", htpClose.GetComponentInChildren<Button>());
            SetRef(serialHTP,"prevButton",  htpPrev.GetComponentInChildren<Button>());
            SetRef(serialHTP,"nextButton",  htpNext.GetComponentInChildren<Button>());
            SetRef(serialHTP,"pageText",    htpPage.GetComponent<TextMeshProUGUI>());
            SetRef(serialHTP,"bodyText",    htpBody.GetComponent<TextMeshProUGUI>());
            serialHTP.ApplyModifiedPropertiesWithoutUndo();

            // FloatingText pool
            var floatPool = new GameObject("FloatingTextPool");
            floatPool.transform.SetParent(T, false);
            floatPool.AddComponent<FloatingTextSpawner>();

            // ── Wire CityUIController ─────────────────────────────────
            var cityUIGo = new GameObject("CityUIController"); cityUIGo.transform.SetParent(T, false);
            var cityUI   = cityUIGo.AddComponent<CityUIController>();
            var serialUI = new SerializedObject(cityUI);
            SetRef(serialUI,"goldText",          goldTxt.GetComponent<TextMeshProUGUI>());
            SetRef(serialUI,"foodText",          foodTxt.GetComponent<TextMeshProUGUI>());
            SetRef(serialUI,"populationText",    popTxt.GetComponent<TextMeshProUGUI>());
            SetRef(serialUI,"fortText",          fortTxt.GetComponent<TextMeshProUGUI>());
            SetRef(serialUI,"lifeText",          lifeTxt.GetComponent<TextMeshProUGUI>());
            SetRef(serialUI,"weekText",          weekTxt.GetComponent<TextMeshProUGUI>());
            SetRef(serialUI,"monthText",         monthTxt.GetComponent<TextMeshProUGUI>());
            SetRef(serialUI,"fortHPText",        fortHPTxt.GetComponent<TextMeshProUGUI>());
            SetRef(serialUI,"heroStatusText",    heroTxt.GetComponent<TextMeshProUGUI>());
            SetRef(serialUI,"heroLevelText",     heroLvTxt.GetComponent<TextMeshProUGUI>());
            SetRef(serialUI,"heroRevivePanel",   heroRevPanel);
            SetRef(serialUI,"heroReviveText",    heroRevTxt.GetComponent<TextMeshProUGUI>());
            SetRef(serialUI,"infantryText",      infTxt.GetComponent<TextMeshProUGUI>());
            SetRef(serialUI,"archerText",        arcTxt.GetComponent<TextMeshProUGUI>());
            SetRef(serialUI,"mageText",          magTxt.GetComponent<TextMeshProUGUI>());
            SetRef(serialUI,"cavalryText",       cavTxt.GetComponent<TextMeshProUGUI>());
            SetRef(serialUI,"healerText",        healTxt.GetComponent<TextMeshProUGUI>());
            SetRef(serialUI,"artilleryText",     artTxt.GetComponent<TextMeshProUGUI>());
            SetRef(serialUI,"advanceWeekButton", advBtn.GetComponentInChildren<Button>());
            SetRef(serialUI,"manageButton",      manBtn.GetComponentInChildren<Button>());
            SetRef(serialUI,"helpButton",        helpBtn.GetComponentInChildren<Button>());
            SetRef(serialUI,"raidButton",        raidBtn.GetComponentInChildren<Button>());
            SetRef(serialUI,"scoutButton",       scoutBtn.GetComponentInChildren<Button>());
            SetRef(serialUI,"managePanel",       managePanelRoot);
            SetRef(serialUI,"raidPanel",         raidPanelRoot);
            SetRef(serialUI,"eventPanel",        eventPanelRoot);
            SetRef(serialUI,"eventTitleText",    evTitleTxt.GetComponent<TextMeshProUGUI>());
            SetRef(serialUI,"eventDescText",     evDescTxt.GetComponent<TextMeshProUGUI>());
            SetRef(serialUI,"eventDismissButton",evDismiss.GetComponentInChildren<Button>());
            SetRef(serialUI,"choiceAButton",    evChoiceA.GetComponentInChildren<Button>());
            SetRef(serialUI,"choiceBButton",    evChoiceB.GetComponentInChildren<Button>());
            serialUI.ApplyModifiedPropertiesWithoutUndo();

            // ── Wire ManageUIController ───────────────────────────────
            var manageUI     = managePanelRoot.AddComponent<ManageUIController>();
            var serialManage = new SerializedObject(manageUI);
            SetRef(serialManage,"upgradeFortButton",upgFortBtn.GetComponentInChildren<Button>());
            SetRef(serialManage,"upgradeLifeButton",upgLifeBtn.GetComponentInChildren<Button>());
            SetRef(serialManage,"fortCostText",fortCostTxt.GetComponent<TextMeshProUGUI>());
            SetRef(serialManage,"lifeCostText",lifeCostTxt.GetComponent<TextMeshProUGUI>());
            SetRef(serialManage,"closeButton",closeManage.GetComponentInChildren<Button>());
            var recBtnProp=serialManage.FindProperty("recruitButtons"); var recCostProp=serialManage.FindProperty("recruitCostTexts");
            recBtnProp.arraySize=6; recCostProp.arraySize=6;
            for (int i=0;i<6;i++) {
                recBtnProp.GetArrayElementAtIndex(i).objectReferenceValue  = recBtns[i].GetComponentInChildren<Button>();
                recCostProp.GetArrayElementAtIndex(i).objectReferenceValue = recCosts[i].GetComponent<TextMeshProUGUI>();
            }
            serialManage.ApplyModifiedPropertiesWithoutUndo();

            // ── Wire BattleResultUI + RaidUIController ────────────────
            var battleResultUI = resultPanelRoot.AddComponent<BattleResultUI>();
            var serialResult   = new SerializedObject(battleResultUI);
            SetRef(serialResult,"titleText",      resultTitle.GetComponent<TextMeshProUGUI>());
            SetRef(serialResult,"powerText",      powerTxt.GetComponent<TextMeshProUGUI>());
            SetRef(serialResult,"casualtiesText", casualTxt.GetComponent<TextMeshProUGUI>());
            SetRef(serialResult,"rewardText",     rewardTxt.GetComponent<TextMeshProUGUI>());
            SetRef(serialResult,"heroText",       heroResTxt.GetComponent<TextMeshProUGUI>());
            SetRef(serialResult,"fortHPText",     fortDmgTxt.GetComponent<TextMeshProUGUI>());
            SetRef(serialResult,"xpText",         xpTxt.GetComponent<TextMeshProUGUI>());
            SetRef(serialResult,"continueButton", contBtn.GetComponentInChildren<Button>());
            serialResult.ApplyModifiedPropertiesWithoutUndo();

            var raidUI    = raidPanelRoot.AddComponent<RaidUIController>();
            var serialRaid = new SerializedObject(raidUI);
            SetRef(serialRaid,"enemyNameText",     enemyNameTxt.GetComponent<TextMeshProUGUI>());
            SetRef(serialRaid,"enemyPowerText",    enemyPowTxt.GetComponent<TextMeshProUGUI>());
            SetRef(serialRaid,"enemyWeaknessText", enemyWeakTxt.GetComponent<TextMeshProUGUI>());
            SetRef(serialRaid,"unknownOverlay",    unknownOverlay);
            SetRef(serialRaid,"fullButton",        fullBtn.GetComponentInChildren<Button>());
            SetRef(serialRaid,"balancedButton",    balBtn.GetComponentInChildren<Button>());
            SetRef(serialRaid,"reserveButton",     resBtn.GetComponentInChildren<Button>());
            SetRef(serialRaid,"weaknessButton",    weakBtn.GetComponentInChildren<Button>());
            SetRef(serialRaid,"heroToggle",        heroToggle);
            SetRef(serialRaid,"deployPreviewText", deployPreviewTxt.GetComponent<TextMeshProUGUI>());
            SetRef(serialRaid,"deployButton",      deployBtn.GetComponentInChildren<Button>());
            SetRef(serialRaid,"resultUI",          battleResultUI);
            serialRaid.ApplyModifiedPropertiesWithoutUndo();

            // ── Runtime polish: AnimatedPanel + ButtonClickEffect ─────────
            foreach (var panel in new[] { managePanelRoot, raidPanelRoot, resultPanelRoot, eventPanelRoot, waPanelRoot, luPanelRoot, goPanelRoot })
            {
                panel.AddComponent<CanvasGroup>();
                panel.AddComponent<AnimatedPanel>();
            }

            foreach (var btn in canvasGo.GetComponentsInChildren<Button>(true))
                if (btn.gameObject.GetComponent<ButtonClickEffect>() == null)
                    btn.gameObject.AddComponent<ButtonClickEffect>();

            return canvasGo;
        }

        static void BuildBattleAnimator(Transform canvasTransform, CameraShake shake)
        {
            var ba    = MakePanel(canvasTransform, "BattleCanvas",
                new Vector2(0.5f,0.5f), new Vector2(0.5f,0.5f),
                new Vector2(1080,1920), Vector2.zero);
            ba.SetActive(false);

            // Impact flash (full-screen)
            var impactGo  = MakePanel(ba.transform, "ImpactPanel",
                new Vector2(0,0), new Vector2(1,1), Vector2.zero, Vector2.zero);
            var impactImg = impactGo.GetComponent<Image>();
            impactImg.color = new Color(1f, 1f, 1f, 0f);
            SetRect(impactGo, Vector2.zero, Vector2.zero, Vector2.zero, Vector2.one);

            var playerSide = MakePanel(ba.transform, "PlayerSide",
                new Vector2(0.5f,0.5f), new Vector2(0.5f,0.5f),
                new Vector2(400, 200), new Vector2(-250, 0));
            MakeTMP(playerSide.transform, "Label", "味方", Vector2.zero, 60, new Color(0.4f,0.8f,1f));

            var enemySide = MakePanel(ba.transform, "EnemySide",
                new Vector2(0.5f,0.5f), new Vector2(0.5f,0.5f),
                new Vector2(400, 200), new Vector2(250, 0));
            var enemyImg  = enemySide.GetComponent<Image>();
            MakeTMP(enemySide.transform, "Label", "敵軍", Vector2.zero, 60, new Color(1f,0.4f,0.4f));

            var resultTxt = MakeTMP(ba.transform, "ResultText", "Victory!", Vector2.up * 400, 100, Color.yellow);
            var damageTxt = MakeTMP(ba.transform, "DamageText", "-50",       Vector2.zero,      80, Color.red);
            resultTxt.SetActive(false);
            damageTxt.SetActive(false);

            var anim    = ba.AddComponent<BattleAnimator>();
            var serialA = new SerializedObject(anim);
            SetRef(serialA, "playerSide",  playerSide.GetComponent<RectTransform>());
            SetRef(serialA, "enemySide",   enemySide.GetComponent<RectTransform>());
            SetRef(serialA, "enemyImage",  enemyImg);
            SetRef(serialA, "impactPanel", impactImg);
            SetRef(serialA, "resultText",  resultTxt.GetComponent<TextMeshProUGUI>());
            SetRef(serialA, "damageText",  damageTxt.GetComponent<TextMeshProUGUI>());
            SetRef(serialA, "cameraShake", shake);
            serialA.ApplyModifiedPropertiesWithoutUndo();
        }

        // ── Build settings ─────────────────────────────────────────────
        static void ConfigureBuildSettings()
        {
            var scenes = new[]
            {
                new EditorBuildSettingsScene("Assets/_Game/Scenes/Boot.unity", true),
                new EditorBuildSettingsScene("Assets/_Game/Scenes/City.unity", true),
            };
            EditorBuildSettings.scenes = scenes;

            // Portrait orientation
            PlayerSettings.defaultInterfaceOrientation = UIOrientation.Portrait;
            PlayerSettings.allowedAutorotateToPortrait  = true;
            PlayerSettings.allowedAutorotateToLandscapeLeft  = false;
            PlayerSettings.allowedAutorotateToLandscapeRight = false;
        }

        // ── Utility helpers ────────────────────────────────────────────
        static T AddManager<T>(string name) where T : Component
        {
            var go = new GameObject(name);
            return go.AddComponent<T>();
        }

        static GameObject MakePanel(Transform parent, string name,
            Vector2 anchorMin, Vector2 anchorMax, Vector2 size, Vector2 pos)
        {
            var go  = new GameObject(name);
            go.transform.SetParent(parent, false);
            go.AddComponent<Image>().color = new Color(0, 0, 0, 0.01f);
            var rt  = go.GetComponent<RectTransform>();
            rt.anchorMin       = anchorMin;
            rt.anchorMax       = anchorMax;
            rt.sizeDelta       = size;
            rt.anchoredPosition = pos;
            return go;
        }

        static void SetRect(GameObject go, Vector2 pos, Vector2 size,
            Vector2 anchorMin = default, Vector2 anchorMax = default)
        {
            var rt = go.GetComponent<RectTransform>() ?? go.AddComponent<RectTransform>();
            rt.anchoredPosition = pos;
            rt.sizeDelta        = size;
            if (anchorMin != default) rt.anchorMin = anchorMin;
            if (anchorMax != default) rt.anchorMax = anchorMax;
        }

        static TMP_FontAsset s_japaneseFont;

        static TMP_FontAsset GetFont()
        {
            if (s_japaneseFont != null) return s_japaneseFont;
            // Try to find any Japanese-capable font in the project
            var guids = AssetDatabase.FindAssets("t:TMP_FontAsset");
            foreach (var g in guids)
            {
                var path = AssetDatabase.GUIDToAssetPath(g);
                // Prefer NotoSans or any CJK font if present
                if (path.Contains("Noto") || path.Contains("CJK") || path.Contains("JP"))
                {
                    s_japaneseFont = AssetDatabase.LoadAssetAtPath<TMP_FontAsset>(path);
                    return s_japaneseFont;
                }
            }
            return null; // fall back to TMP default
        }

        static GameObject MakeTMP(Transform parent, string name, string text,
            Vector2 pos, int size, Color? color = null)
        {
            var go  = new GameObject(name);
            go.transform.SetParent(parent, false);
            var tmp = go.AddComponent<TextMeshProUGUI>();
            tmp.text      = text;
            tmp.fontSize  = size;
            tmp.color     = color ?? Color.white;
            tmp.alignment = TextAlignmentOptions.Center;
            var font = GetFont();
            if (font != null) tmp.font = font;
            var rt        = go.GetComponent<RectTransform>();
            rt.anchoredPosition = pos;
            rt.sizeDelta        = new Vector2(800, size + 20);
            return go;
        }

        static GameObject MakeButton(Transform parent, string name, string label,
            Vector2 pos, Vector2 size, Color? bgColor = null)
        {
            var go  = new GameObject(name);
            go.transform.SetParent(parent, false);
            var img = go.AddComponent<Image>();
            img.color = bgColor ?? new Color(0.2f, 0.2f, 0.3f, 0.9f);
            var btn = go.AddComponent<Button>();
            btn.targetGraphic = img;
            go.AddComponent<ButtonFeedback>();
            var rt  = go.GetComponent<RectTransform>();
            rt.anchoredPosition = pos;
            rt.sizeDelta        = size;

            var textGo  = new GameObject("Text");
            textGo.transform.SetParent(go.transform, false);
            var tmp     = textGo.AddComponent<TextMeshProUGUI>();
            tmp.text      = label;
            tmp.fontSize  = Mathf.RoundToInt(size.y * 0.4f);
            tmp.color     = Color.white;
            tmp.alignment = TextAlignmentOptions.Center;
            var trt       = textGo.GetComponent<RectTransform>();
            trt.anchorMin = Vector2.zero;
            trt.anchorMax = Vector2.one;
            trt.sizeDelta = Vector2.zero;

            return go;
        }

        static Toggle MakeToggle(Transform parent, string name, string label, Vector2 pos)
        {
            var go  = new GameObject(name);
            go.transform.SetParent(parent, false);
            var rt  = go.AddComponent<RectTransform>();
            rt.anchoredPosition = pos;
            rt.sizeDelta        = new Vector2(500, 70);

            // Background box (required by Toggle)
            var bgGo  = new GameObject("Background");
            bgGo.transform.SetParent(go.transform, false);
            var bgImg = bgGo.AddComponent<Image>();
            bgImg.color = new Color(0.25f, 0.25f, 0.3f);
            var bgRT  = bgGo.GetComponent<RectTransform>();
            bgRT.anchoredPosition = new Vector2(-190, 0);
            bgRT.sizeDelta        = new Vector2(60, 60);

            // Checkmark (shown when on)
            var chkGo  = new GameObject("Checkmark");
            chkGo.transform.SetParent(bgGo.transform, false);
            var chkImg = chkGo.AddComponent<Image>();
            chkImg.color = new Color(0.3f, 0.9f, 0.3f);
            var chkRT  = chkGo.GetComponent<RectTransform>();
            chkRT.anchorMin  = Vector2.zero;
            chkRT.anchorMax  = Vector2.one;
            chkRT.sizeDelta  = new Vector2(-8, -8);

            // Label
            MakeTMP(go.transform, "Label", label, new Vector2(30, 0), 36);

            // Toggle component
            var toggle         = go.AddComponent<Toggle>();
            toggle.targetGraphic = bgImg;
            toggle.graphic       = chkImg;
            toggle.isOn          = true;
            return toggle;
        }

        static T LoadOrCreate<T>(string path) where T : ScriptableObject
        {
            var existing = AssetDatabase.LoadAssetAtPath<T>(path);
            if (existing) return existing;
            var so = ScriptableObject.CreateInstance<T>();
            AssetDatabase.CreateAsset(so, path);
            return so;
        }

        static T[] LoadAllAtPath<T>(string folder) where T : Object
        {
            var guids = AssetDatabase.FindAssets($"t:{typeof(T).Name}", new[] { folder });
            var result = new T[guids.Length];
            for (int i = 0; i < guids.Length; i++)
                result[i] = AssetDatabase.LoadAssetAtPath<T>(AssetDatabase.GUIDToAssetPath(guids[i]));
            return result;
        }

        static void SetRef(SerializedObject so, string prop, Object value)
        {
            var p = so.FindProperty(prop);
            if (p != null) p.objectReferenceValue = value;
        }

        static void SetSOArray<T>(SerializedObject so, string prop, T[] items) where T : Object
        {
            var p = so.FindProperty(prop);
            if (p == null) return;
            p.arraySize = items.Length;
            for (int i = 0; i < items.Length; i++)
                p.GetArrayElementAtIndex(i).objectReferenceValue = items[i];
        }

        static void SetGOArray(SerializedObject so, string prop, GameObject[] items)
        {
            var p = so.FindProperty(prop);
            if (p == null) return;
            p.arraySize = items.Length;
            for (int i = 0; i < items.Length; i++)
                p.GetArrayElementAtIndex(i).objectReferenceValue = items[i];
        }

        static Color UnitColor(UnitType t) => t switch
        {
            UnitType.Infantry  => new Color(0.7f, 0.7f, 0.7f),
            UnitType.Archer    => new Color(0.4f, 0.8f, 0.3f),
            UnitType.Mage      => new Color(0.5f, 0.3f, 0.9f),
            UnitType.Cavalry   => new Color(0.9f, 0.7f, 0.2f),
            UnitType.Healer    => new Color(0.3f, 0.9f, 0.7f),
            UnitType.Artillery => new Color(0.9f, 0.4f, 0.2f),
            _                  => Color.white
        };
    }
}
#endif
