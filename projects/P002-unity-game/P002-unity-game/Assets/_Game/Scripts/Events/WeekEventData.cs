using UnityEngine;
using System;

namespace FortressCity
{
    [Serializable]
    public class EventEffect
    {
        public int goldDelta;
        public int foodDelta;
        public int populationDelta;
        public int fortDelta;
        public int lifeDelta;
        public int infantryDelta;
    }

    [CreateAssetMenu(fileName = "WeekEventData", menuName = "FortressCity/Week Event Data")]
    public class WeekEventData : ScriptableObject
    {
        public string    eventName;
        [TextArea] public string description;
        [Range(0f, 1f)]
        public float     probability = 0.1f;
        public EventEffect effect;
        public bool      isPositive = true;
    }
}
