using UnityEngine;
using System.Collections;

namespace FortressCity
{
    public class CameraShake : MonoBehaviour
    {
        [SerializeField] private float duration  = 0.25f;
        [SerializeField] private float magnitude = 12f;

        private Vector3 originPos;

        void Awake() => originPos = transform.localPosition;

        public void Shake() => StartCoroutine(DoShake());

        IEnumerator DoShake()
        {
            float elapsed = 0f;
            while (elapsed < duration)
            {
                elapsed += Time.deltaTime;
                float dampen = 1f - (elapsed / duration);
                transform.localPosition = originPos + (Vector3)Random.insideUnitCircle * magnitude * dampen;
                yield return null;
            }
            transform.localPosition = originPos;
        }
    }
}
