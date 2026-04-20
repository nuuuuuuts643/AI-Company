using UnityEngine;

namespace FortressCity
{
    [CreateAssetMenu(fileName = "UnitData", menuName = "FortressCity/Unit Data")]
    public class UnitData : ScriptableObject
    {
        public string   unitName;
        public UnitType unitType;
        [TextArea] public string description;

        [Header("Stats")]
        public int   baseAttack = 10;
        public int   baseHP     = 100;

        [Header("Costs")]
        public int recruitCost     = 50;
        public int weeklyGoldCost  = 2;
        public int weeklyFoodCost  = 1;

        [Header("Effectiveness")]
        public EnemyType[] strongAgainst;
        [Range(1.5f, 3f)]
        public float bonusMultiplier = 2f;

        [Header("Visuals")]
        public Sprite icon;
        public Color  unitColor = Color.white;
    }
}
