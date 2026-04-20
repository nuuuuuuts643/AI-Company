using UnityEngine;
using UnityEngine.UI;
using TMPro;

namespace FortressCity
{
    public class BattleResultUI : MonoBehaviour
    {
        public static BattleResultUI Instance { get; private set; }

        [SerializeField] TMP_Text titleText;
        [SerializeField] TMP_Text powerText;
        [SerializeField] TMP_Text casualtiesText;
        [SerializeField] TMP_Text rewardText;
        [SerializeField] TMP_Text heroText;
        [SerializeField] TMP_Text fortHPText;
        [SerializeField] TMP_Text xpText;
        [SerializeField] Button   continueButton;

        BattleReport _pendingReport;

        void Awake()
        {
            Instance = this;
            gameObject.SetActive(false);
        }

        void Start() => continueButton.onClick.AddListener(OnContinue);

        public void Show(BattleReport report)
        {
            _pendingReport = report;
            gameObject.SetActive(true);
            StartCoroutine(UITween.PanelOpen(gameObject));

            bool win        = report.result == BattleResult.Victory;
            titleText.text  = win ? "Victory!" : "Defeat...";
            titleText.color = win ? new Color(1f, 0.85f, 0.1f) : new Color(0.8f, 0.2f, 0.2f);

            powerText.text = $"戦力比: {report.playerPower:F0} vs {report.enemyPower:F0}";

            var c = report.casualties;
            casualtiesText.text =
                $"損耗: 歩{c.infantry} 弓{c.archer} 魔{c.mage} 騎{c.cavalry} 回{c.healer} 砲{c.artillery}";

            rewardText.text = win
                ? $"報酬: Gold+{report.goldReward}  Food+{report.foodReward}"
                : "敗北ペナルティ適用";

            // Fort damage
            var city = GameManager.Instance.City;
            if (fortHPText)
            {
                string dmgColor = report.fortDamage >= 30 ? "#FF4444" : "#FF9900";
                fortHPText.text = $"城ダメージ: <color={dmgColor}>-{report.fortDamage}</color>  残HP: {city.fortHP}/{city.maxFortHP}";
            }

            // Hero XP
            if (xpText)
            {
                if (report.heroXPGained > 0)
                {
                    string lvlStr = report.heroLeveledUp
                        ? $"  <color=#FFD700>LEVEL UP! Lv{report.heroLevelAfter}</color>"
                        : $"  (Lv{report.heroLevelAfter} {city.heroXP}/{city.XPForNextLevel}XP)";
                    xpText.text = $"勇者XP: +{report.heroXPGained}{lvlStr}";
                }
                else
                {
                    xpText.text = "勇者: 非出陣";
                }
            }

            heroText.gameObject.SetActive(report.heroFell);
            if (report.heroFell) heroText.text = "勇者が倒れた！  3週後に復活";
        }

        void OnContinue()
        {
            StartCoroutine(UITween.PanelClose(gameObject));

            if (_pendingReport != null && _pendingReport.heroLeveledUp)
                LevelUpUI.Instance?.Show(GameManager.Instance.City);

            FindObjectOfType<CityUIController>()?.SendMessage("Refresh", SendMessageOptions.DontRequireReceiver);
        }
    }
}
