using UnityEngine;
using UnityEngine.UI;
using TMPro;

namespace FortressCity
{
    public class CityUIController : MonoBehaviour
    {
        [Header("Resources")]
        [SerializeField] TMP_Text goldText;
        [SerializeField] TMP_Text foodText;
        [SerializeField] TMP_Text populationText;
        [SerializeField] TMP_Text fortText;
        [SerializeField] TMP_Text lifeText;

        [Header("Time")]
        [SerializeField] TMP_Text weekText;
        [SerializeField] TMP_Text monthText;

        [Header("Fort HP")]
        [SerializeField] TMP_Text fortHPText;
        [SerializeField] Image    fortHPFill;

        [Header("Hero")]
        [SerializeField] TMP_Text   heroStatusText;
        [SerializeField] TMP_Text   heroLevelText;
        [SerializeField] GameObject heroRevivePanel;
        [SerializeField] TMP_Text   heroReviveText;

        [Header("Army")]
        [SerializeField] TMP_Text infantryText;
        [SerializeField] TMP_Text archerText;
        [SerializeField] TMP_Text mageText;
        [SerializeField] TMP_Text cavalryText;
        [SerializeField] TMP_Text healerText;
        [SerializeField] TMP_Text artilleryText;

        [Header("Buttons")]
        [SerializeField] Button advanceWeekButton;
        [SerializeField] Button manageButton;
        [SerializeField] Button helpButton;
        [SerializeField] Button raidButton;
        [SerializeField] Button scoutButton;

        [Header("Panels")]
        [SerializeField] GameObject managePanel;
        [SerializeField] GameObject raidPanel;
        [SerializeField] GameObject eventPanel;
        [SerializeField] TMP_Text   eventTitleText;
        [SerializeField] TMP_Text   eventDescText;
        [SerializeField] Button     eventDismissButton;
        [SerializeField] Button     choiceAButton;
        [SerializeField] Button     choiceBButton;

        int _prevGold=-1,_prevFood=-1,_prevPop=-1,_prevFort=-1,_prevLife=-1;
        int _prevInf=-1,_prevArch=-1,_prevMage=-1,_prevCav=-1,_prevHeal=-1,_prevArt=-1;

        void OnDestroy()
        {
            if (!TimeManager.Instance) return;
            TimeManager.Instance.OnWeekAdvanced  -= Refresh;
            TimeManager.Instance.OnMonthEnd      -= OnMonthEnd;
            TimeManager.Instance.OnEventTriggered -= ShowPassiveEvent;
            TimeManager.Instance.OnChoiceEvent   -= ShowChoiceEvent;
            TimeManager.Instance.OnIncomeDelta   -= SpawnIncomeFloats;
        }

        void Start()
        {
            TimeManager.Instance.OnWeekAdvanced  += Refresh;
            TimeManager.Instance.OnMonthEnd      += OnMonthEnd;
            TimeManager.Instance.OnEventTriggered += ShowPassiveEvent;
            TimeManager.Instance.OnChoiceEvent   += ShowChoiceEvent;
            TimeManager.Instance.OnIncomeDelta   += SpawnIncomeFloats;

            advanceWeekButton.onClick.AddListener(OnAdvanceWeek);
            manageButton?.onClick.AddListener(OpenManage);
            helpButton?.onClick.AddListener(() => HowToPlayUI.Instance?.Open());
            eventDismissButton?.onClick.AddListener(CloseEvent);
            raidButton?.onClick.AddListener(OpenRaid);
            scoutButton?.onClick.AddListener(OnScout);

            eventPanel?.SetActive(false);
            Refresh();
            UpdateRaidVisibility();
        }

        void OnAdvanceWeek()
        {
            var city = GameManager.Instance.City;
            if (city.week == 1 && city.month > 1) { Debug.Log("Resolve the raid first."); return; }

            if (WeeklyActionUI.Instance != null)
                WeeklyActionUI.Instance.Show(city, action => {
                    TimeManager.Instance.AdvanceWeek(action);
                    UpdateRaidVisibility();
                });
            else
            {
                TimeManager.Instance.AdvanceWeek();
                UpdateRaidVisibility();
            }
        }

        void OpenManage() => OpenPanel(managePanel);
        void OpenRaid()   => OpenPanel(raidPanel);
        void CloseEvent() => ClosePanel(eventPanel);

        static void OpenPanel(GameObject p)
        {
            if (!p) return;
            var ap = p.GetComponent<AnimatedPanel>();
            if (ap) ap.Open(); else p.SetActive(true);
        }
        static void ClosePanel(GameObject p)
        {
            if (!p) return;
            var ap = p.GetComponent<AnimatedPanel>();
            if (ap) ap.Close(); else p.SetActive(false);
        }

        void OnMonthEnd() { Refresh(); UpdateRaidVisibility(); }

        void OnScout()
        {
            var result = ScoutManager.Instance.PerformScout(3);
            ShowPassiveEvent(new WeekEventData { eventName = "偵察報告", description = result.message, isPositive = result.success });
            Refresh();
        }

        void UpdateRaidVisibility()
        {
            var city = GameManager.Instance.City;
            bool raidPhase = city.week == 1 && city.month > 1;
            raidButton?.gameObject.SetActive(raidPhase);
            scoutButton?.gameObject.SetActive(raidPhase && !city.scoutResultKnown);
            advanceWeekButton.interactable = !raidPhase;
        }

        public void Refresh()
        {
            var city = GameManager.Instance.City;

            SetPop(goldText,       ref _prevGold, city.gold,       $"Gold  {city.gold}");
            SetPop(foodText,       ref _prevFood, city.food,       $"Food  {city.food}");
            SetPop(populationText, ref _prevPop,  city.population, $"Pop   {city.population}");
            SetPop(fortText,       ref _prevFort, city.fort,       $"Fort  Lv{city.fort}");
            SetPop(lifeText,       ref _prevLife, city.life,       $"Life  Lv{city.life}");

            weekText.text  = $"Week {city.week}";
            monthText.text = $"Month {city.month} / {GameManager.WinMonth}";

            if (fortHPText)
            {
                float r = (float)city.fortHP / Mathf.Max(1, city.maxFortHP);
                string c = r > 0.5f ? "#88FF88" : r > 0.25f ? "#FFAA00" : "#FF4444";
                fortHPText.text = $"城HP <color={c}>{city.fortHP}/{city.maxFortHP}</color>";
            }
            if (fortHPFill)
                fortHPFill.fillAmount = (float)city.fortHP / Mathf.Max(1, city.maxFortHP);

            if (city.heroAlive)
            {
                if (heroStatusText) heroStatusText.text = "勇者 在陣";
                heroRevivePanel?.SetActive(false);
            }
            else
            {
                if (heroStatusText) heroStatusText.text = "勇者 離脱中";
                heroRevivePanel?.SetActive(true);
                if (heroReviveText) heroReviveText.text = $"復帰まで {city.heroReviveWeeksLeft} 週";
            }

            if (heroLevelText)
            {
                var skillNames = city.heroSkills.Count > 0
                    ? string.Join(" ", city.heroSkills.ConvertAll(s => HeroSystem.GetData((HeroSkillType)s).name))
                    : "スキルなし";
                heroLevelText.text = $"Lv{city.heroLevel}  {city.heroXP}/{city.XPForNextLevel}XP  {skillNames}";
            }

            if (infantryText)  SetPop(infantryText,  ref _prevInf,  city.army.infantry,  $"歩兵   {city.army.infantry}");
            if (archerText)    SetPop(archerText,    ref _prevArch, city.army.archer,    $"弓兵   {city.army.archer}");
            if (mageText)      SetPop(mageText,      ref _prevMage, city.army.mage,      $"魔法兵 {city.army.mage}");
            if (cavalryText)   SetPop(cavalryText,   ref _prevCav,  city.army.cavalry,   $"騎兵   {city.army.cavalry}");
            if (healerText)    SetPop(healerText,    ref _prevHeal, city.army.healer,    $"回復兵 {city.army.healer}");
            if (artilleryText) SetPop(artilleryText, ref _prevArt,  city.army.artillery, $"砲兵   {city.army.artillery}");
        }

        void SetPop(TMP_Text lbl, ref int prev, int cur, string text)
        {
            lbl.text = text;
            if (prev != -1 && prev != cur) StartCoroutine(UITween.NumberPop(lbl.GetComponent<RectTransform>()));
            prev = cur;
        }

        void ShowPassiveEvent(WeekEventData ev)
        {
            if (!eventPanel) return;
            SetEventText(ev.isPositive ? $"[吉] {ev.eventName}" : $"[凶] {ev.eventName}", ev.description);
            SetChoiceButtonsVisible(false);
            eventDismissButton?.gameObject.SetActive(true);
            OpenPanel(eventPanel);
        }

        void ShowChoiceEvent(ChoiceEvent ev)
        {
            if (!eventPanel) return;
            SetEventText(ev.isPositive ? $"[吉] {ev.title}" : $"[凶] {ev.title}", ev.description);
            SetChoiceButtonsVisible(true);
            eventDismissButton?.gameObject.SetActive(false);
            SetChoiceButton(choiceAButton, ev.choiceALabel, () => { ev.onChoiceA?.Invoke(); CloseEvent(); Refresh(); });
            SetChoiceButton(choiceBButton, ev.choiceBLabel, () => { ev.onChoiceB?.Invoke(); CloseEvent(); Refresh(); });
            OpenPanel(eventPanel);
        }

        void SetEventText(string t, string d) { if(eventTitleText) eventTitleText.text=t; if(eventDescText) eventDescText.text=d; }
        void SetChoiceButtonsVisible(bool v) { choiceAButton?.gameObject.SetActive(v); choiceBButton?.gameObject.SetActive(v); }
        void SetChoiceButton(Button btn, string lbl, System.Action cb)
        {
            if (!btn) return;
            btn.onClick.RemoveAllListeners();
            btn.onClick.AddListener(()=>cb());
            var t = btn.GetComponentInChildren<TMP_Text>();
            if (t) t.text = lbl;
        }

        void SpawnIncomeFloats(int gd, int fd, int pd)
        {
            var sp = FloatingTextSpawner.Instance;
            if (!sp) return;
            SpawnDelta(sp, gd, goldText,       "G", new Color(1f,0.85f,0.2f));
            SpawnDelta(sp, fd, foodText,       "F", new Color(0.4f,1f,0.4f));
            SpawnDelta(sp, pd, populationText, "人", new Color(0.5f,0.8f,1f));
        }

        void SpawnDelta(FloatingTextSpawner sp, int d, TMP_Text lbl, string unit, Color col)
        {
            if (d == 0 || !lbl) return;
            sp.Spawn($"{(d>0?"+":"")}{d}{unit}", col, lbl.GetComponent<RectTransform>().anchoredPosition + Vector2.up*70f);
        }
    }
}
