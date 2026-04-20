using UnityEngine;
using UnityEngine.UI;
using TMPro;
using System;

namespace FortressCity
{
    public class WeeklyActionUI : MonoBehaviour
    {
        public static WeeklyActionUI Instance { get; private set; }

        [SerializeField] Button[]   actionButtons;  // 5 buttons
        [SerializeField] TMP_Text[] actionLabels;
        [SerializeField] TMP_Text   headerText;

        Action<WeeklyAction> _onPick;

        static readonly (WeeklyAction action, string label, string detail)[] Defs =
        {
            (WeeklyAction.Train,  "訓練",  "歩兵+15  食-25"),
            (WeeklyAction.Tax,    "徴税",  "Gold+130"),
            (WeeklyAction.Repair, "修繕",  "城HP+80  Gold-100"),
            (WeeklyAction.Scout,  "偵察",  "敵情報を入手"),
            (WeeklyAction.Govern, "民政",  "人口+25  食+20"),
        };

        void Awake()
        {
            Instance = this;
            gameObject.SetActive(false);
        }

        void Start()
        {
            for (int i = 0; i < actionButtons.Length && i < Defs.Length; i++)
            {
                int idx = i;
                if (actionLabels != null && idx < actionLabels.Length)
                    actionLabels[idx].text = $"{Defs[idx].label}\n{Defs[idx].detail}";

                actionButtons[i].onClick.AddListener(() =>
                {
                    var ap = GetComponent<AnimatedPanel>();
                    if (ap) ap.Close(); else gameObject.SetActive(false);
                    _onPick?.Invoke(Defs[idx].action);
                });
            }
        }

        public void Show(CityData city, Action<WeeklyAction> onPick)
        {
            _onPick = onPick;
            var month = city.month;
            if (headerText)
                headerText.text = $"Month {month} / Week {city.week + 1}\n今週の行動を選べ";

            // Grey out Repair if can't afford
            if (actionButtons.Length > 2)
                actionButtons[2].interactable = city.gold >= 100;

            // Grey out Scout if already known
            if (actionButtons.Length > 3)
                actionButtons[3].interactable = !city.scoutResultKnown;

            var ap = GetComponent<AnimatedPanel>();
            if (ap) ap.Open(); else gameObject.SetActive(true);
        }
    }
}
