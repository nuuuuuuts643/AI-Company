using UnityEngine;

namespace FortressCity
{
    [CreateAssetMenu(fileName = "EnemyData", menuName = "FortressCity/Enemy Data")]
    public class EnemyData : ScriptableObject
    {
        public string    enemyName;
        public EnemyType enemyType;
        [TextArea] public string trait;
        public UnitType  weakness;

        [Header("Power Scaling")]
        public float basePowerMultiplier = 1f;
        public int   baseCount           = 50;

        [Header("Visuals")]
        public Sprite sprite;
        public Color  enemyColor = Color.red;
    }
}
