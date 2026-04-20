using UnityEngine;

namespace FortressCity
{
    public class ArmyManager : MonoBehaviour
    {
        public static ArmyManager Instance { get; private set; }

        void Awake() { Instance = this; }

        public ArmyData GetFormation(FormationPreset preset, EnemyData enemy = null)
        {
            var army = GameManager.Instance.City.army;
            return preset switch
            {
                FormationPreset.Full                  => army.Clone(),
                FormationPreset.Balanced              => Scale(army, 0.6f),
                FormationPreset.Reserve               => Scale(army, 0.3f),
                FormationPreset.WeaknessSpecialized   => enemy != null
                                                            ? BuildWeakness(army, enemy.weakness)
                                                            : Scale(army, 0.5f),
                _                                     => army.Clone()
            };
        }

        ArmyData Scale(ArmyData army, float ratio) => new ArmyData
        {
            infantry  = Mathf.RoundToInt(army.infantry  * ratio),
            archer    = Mathf.RoundToInt(army.archer    * ratio),
            mage      = Mathf.RoundToInt(army.mage      * ratio),
            cavalry   = Mathf.RoundToInt(army.cavalry   * ratio),
            healer    = Mathf.RoundToInt(army.healer    * ratio),
            artillery = Mathf.RoundToInt(army.artillery * ratio),
        };

        ArmyData BuildWeakness(ArmyData army, UnitType weakness)
        {
            var f = Scale(army, 0.3f);
            f.SetCount(weakness, Mathf.RoundToInt(army.GetCount(weakness) * 0.9f));
            return f;
        }
    }
}
