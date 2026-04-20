using UnityEngine;
using System;

namespace FortressCity
{
    public class TimeManager : MonoBehaviour
    {
        public static TimeManager Instance { get; private set; }

        public event Action                OnWeekAdvanced;
        public event Action                OnMonthEnd;
        public event Action<WeekEventData> OnEventTriggered;
        public event Action<ChoiceEvent>   OnChoiceEvent;
        public event Action<int, int, int> OnIncomeDelta;

        [SerializeField] private WeekEventData[] weekEvents;

        void Awake() { Instance = this; }

        public void AdvanceWeek(WeeklyAction action = WeeklyAction.Tax)
        {
            var city = GameManager.Instance.City;

            int goldBefore = city.gold;
            int foodBefore = city.food;
            int popBefore  = city.population;

            CityManager.Instance.ProcessWeek();
            ApplyWeeklyAction(city, action);

            int gd = city.gold       - goldBefore;
            int fd = city.food       - foodBefore;
            int pd = city.population - popBefore;
            if (gd != 0 || fd != 0 || pd != 0)
                OnIncomeDelta?.Invoke(gd, fd, pd);

            if (!TryTriggerChoiceEvent(city))
                TryTriggerPassiveEvent(city);

            city.week++;
            if (city.week > 4)
            {
                city.week = 1;
                city.month++;
                city.scoutResultKnown = false;
                GameManager.Instance.CheckWinLose();
                OnMonthEnd?.Invoke();
            }
            else
            {
                OnWeekAdvanced?.Invoke();
            }

            GameManager.Instance.SaveGame();
        }

        void ApplyWeeklyAction(CityData city, WeeklyAction action)
        {
            switch (action)
            {
                case WeeklyAction.Train:
                    city.army.infantry += 15;
                    city.food = Mathf.Max(0, city.food - 25);
                    break;
                case WeeklyAction.Tax:
                    city.gold += 130;
                    break;
                case WeeklyAction.Repair:
                    if (city.gold >= 100)
                    {
                        city.gold   -= 100;
                        city.fortHP  = Mathf.Min(city.maxFortHP, city.fortHP + 80);
                    }
                    break;
                case WeeklyAction.Scout:
                    city.scoutResultKnown = true;
                    break;
                case WeeklyAction.Govern:
                    city.population += 25;
                    city.food       += 20;
                    break;
            }
        }

        bool TryTriggerChoiceEvent(CityData city)
        {
            if (UnityEngine.Random.value > 0.35f) return false;
            var scenarios = BuildScenarios(city);
            var ev = scenarios[UnityEngine.Random.Range(0, scenarios.Length)];
            OnChoiceEvent?.Invoke(ev);
            return true;
        }

        ChoiceEvent[] BuildScenarios(CityData city) => new[]
        {
            new ChoiceEvent
            {
                title        = "旅の商人",
                description  = "商人が食料80を50Gで売ると言っている。",
                isPositive   = true,
                choiceALabel = "買う  -50G +80食",
                choiceBLabel = "断る",
                onChoiceA    = () => { city.gold = Mathf.Max(0, city.gold - 50); city.food += 80; },
                onChoiceB    = () => { }
            },
            new ChoiceEvent
            {
                title        = "流れ者の傭兵",
                description  = "腕利きの傭兵10人が100Gで雇えると言っている。",
                isPositive   = true,
                choiceALabel = "雇う  -100G +10歩",
                choiceBLabel = "断る",
                onChoiceA    = () => { if (city.gold >= 100) { city.gold -= 100; city.army.infantry += 10; } },
                onChoiceB    = () => { }
            },
            new ChoiceEvent
            {
                title        = "盗賊団の脅迫",
                description  = "盗賊団が「100G払え、さもなくば村を荒らす」と言ってきた。",
                isPositive   = false,
                choiceALabel = "払う  -100G",
                choiceBLabel = "戦う  -5歩 +50G",
                onChoiceA    = () => { city.gold = Mathf.Max(0, city.gold - 100); },
                onChoiceB    = () => { city.army.infantry = Mathf.Max(0, city.army.infantry - 5); city.gold += 50; }
            },
            new ChoiceEvent
            {
                title        = "石材商人",
                description  = "200Gで砦を補強してやると言っている。",
                isPositive   = true,
                choiceALabel = "頼む  -200G Fort+1",
                choiceBLabel = "断る",
                onChoiceA    = () => {
                    if (city.gold >= 200)
                    {
                        city.gold -= 200; city.fort++;
                        city.maxFortHP += 200; city.fortHP += 200;
                    }
                },
                onChoiceB    = () => { }
            },
            new ChoiceEvent
            {
                title        = "食糧危機",
                description  = "近隣の村から難民が押し寄せている。受け入れるか？",
                isPositive   = false,
                choiceALabel = "受け入れ -50食 +20人",
                choiceBLabel = "断る",
                onChoiceA    = () => { city.food = Mathf.Max(0, city.food - 50); city.population += 20; },
                onChoiceB    = () => { }
            },
            new ChoiceEvent
            {
                title        = "密偵の情報",
                description  = "密偵が敵の弱点情報を150Gで売ると言っている。",
                isPositive   = true,
                choiceALabel = "買う  -150G 偵察済",
                choiceBLabel = "断る",
                onChoiceA    = () => { if (city.gold >= 150) { city.gold -= 150; city.scoutResultKnown = true; } },
                onChoiceB    = () => { }
            },
        };

        void TryTriggerPassiveEvent(CityData city)
        {
            if (weekEvents == null) return;
            foreach (var ev in weekEvents)
            {
                if (UnityEngine.Random.value < ev.probability)
                {
                    ApplyEffect(city, ev);
                    OnEventTriggered?.Invoke(ev);
                    return;
                }
            }
        }

        void ApplyEffect(CityData city, WeekEventData ev)
        {
            var e = ev.effect;
            city.gold          = Mathf.Max(0,  city.gold          + e.goldDelta);
            city.food          = Mathf.Max(0,  city.food          + e.foodDelta);
            city.population    = Mathf.Max(10, city.population    + e.populationDelta);
            city.fort          = Mathf.Max(1,  city.fort          + e.fortDelta);
            city.life          = Mathf.Max(1,  city.life          + e.lifeDelta);
            city.army.infantry = Mathf.Max(0,  city.army.infantry + e.infantryDelta);
        }
    }
}
