using UnityEngine;
using UnityEngine.UI;
using TMPro;

namespace FortressCity
{
    public class RaidUIController : MonoBehaviour
    {
        [Header("Enemy Info")]
        [SerializeField] TMP_Text   enemyNameText;
        [SerializeField] TMP_Text   enemyPowerText;
        [SerializeField] TMP_Text   enemyWeaknessText;
        [SerializeField] GameObject unknownOverlay;

        [Header("Formation Presets")]
        [SerializeField] Button fullButton;
        [SerializeField] Button balancedButton;
        [SerializeField] Button reserveButton;
        [SerializeField] Button weaknessButton;

        [Header("Hero")]
        [SerializeField] Toggle heroToggle;

        [Header("Deploy")]
        [SerializeField] TMP_Text deployPreviewText;
        [SerializeField] Button   deployButton;

        [Header("Result")]
        [SerializeField] BattleResultUI resultUI;

        private EnemyData       currentEnemy;
        private int             currentEnemyPower;
        private FormationPreset selectedPreset = FormationPreset.Balanced;

        void OnEnable()
        {
            if (GameManager.Instance == null) return;
            SetupEnemy();
            SelectPreset(selectedPreset);
        }

        void Start()
        {
            fullButton.onClick.AddListener(()     => SelectPreset(FormationPreset.Full));
            balancedButton.onClick.AddListener(() => SelectPreset(FormationPreset.Balanced));
            reserveButton.onClick.AddListener(()  => SelectPreset(FormationPreset.Reserve));
            weaknessButton.onClick.AddListener(() => SelectPreset(FormationPreset.WeaknessSpecialized));
            deployButton.onClick.AddListener(Deploy);
            SetupEnemy();
            SelectPreset(selectedPreset);
        }

        void SetupEnemy()
        {
            var city    = GameManager.Instance.City;
            var enemies = GameManager.Instance.EnemyDataList;
            int idx     = (city.month - 1) % enemies.Length;
            currentEnemy      = enemies[idx];
            currentEnemyPower = Mathf.RoundToInt(currentEnemy.basePowerMultiplier * 100 * city.month);

            bool known = city.scoutResultKnown;
            unknownOverlay?.SetActive(!known);
            enemyNameText.text     = known ? currentEnemy.enemyName : "???";
            enemyPowerText.text    = known ? $"戦力: {currentEnemyPower}" : "戦力: ???";
            enemyWeaknessText.text = known ? $"弱点: {UnitName(currentEnemy.weakness)}" : "弱点: ???";
            weaknessButton.interactable = known;
        }

        void SelectPreset(FormationPreset preset)
        {
            selectedPreset = preset;
            var f = ArmyManager.Instance.GetFormation(preset, currentEnemy);
            deployPreviewText.text =
                $"歩:{f.infantry} 弓:{f.archer} 魔:{f.mage}\n騎:{f.cavalry} 回:{f.healer} 砲:{f.artillery}\n合計:{f.TotalUnits()}";
        }

        void Deploy()
        {
            var city  = GameManager.Instance.City;
            var setup = new BattleSetup
            {
                deployedArmy = ArmyManager.Instance.GetFormation(selectedPreset, currentEnemy),
                enemy        = currentEnemy,
                enemyPower   = currentEnemyPower,
                heroDeployed = heroToggle != null && heroToggle.isOn && city.heroAlive
            };

            var report = BattleManager.Instance.ResolveBattle(setup);

            // Close raid panel immediately
            var ap = GetComponent<AnimatedPanel>();
            if (ap) ap.Close(); else gameObject.SetActive(false);

            // Play battle animation, then show result
            if (BattleAnimator.Instance != null)
            {
                BattleAnimator.Instance.PlayBattle(report, currentEnemy, () => AfterBattle(report));
            }
            else
            {
                AfterBattle(report);
            }
        }

        void AfterBattle(BattleReport report)
        {
            var city = GameManager.Instance.City;
            city.week = 2;
            GameManager.Instance.SaveGame();
            resultUI?.Show(report);
        }

        string UnitName(UnitType t) => t switch
        {
            UnitType.Infantry  => "歩兵",
            UnitType.Archer    => "弓兵",
            UnitType.Mage      => "魔法兵",
            UnitType.Cavalry   => "騎兵",
            UnitType.Healer    => "回復兵",
            UnitType.Artillery => "砲兵",
            _                  => t.ToString()
        };
    }
}
