using UnityEngine;
using TMPro;
using System.Collections;

namespace FortressCity
{
    // Pool-friendly floating text. Spawned by FloatingTextSpawner.
    [RequireComponent(typeof(TextMeshProUGUI))]
    public class FloatingText : MonoBehaviour
    {
        [SerializeField] private float riseSpeed  = 80f;
        [SerializeField] private float lifetime   = 0.9f;

        private TextMeshProUGUI tmp;

        void Awake() => tmp = GetComponent<TextMeshProUGUI>();

        public void Play(string text, Color color)
        {
            tmp.text  = text;
            tmp.color = color;
            gameObject.SetActive(true);
            StartCoroutine(Animate());
        }

        IEnumerator Animate()
        {
            float elapsed = 0f;
            var   rt      = GetComponent<RectTransform>();
            var   start   = rt.anchoredPosition;
            var   startC  = tmp.color;

            while (elapsed < lifetime)
            {
                elapsed              += Time.deltaTime;
                float t               = elapsed / lifetime;
                rt.anchoredPosition   = start + Vector2.up * riseSpeed * t;
                var c                 = startC;
                c.a                   = 1f - t;
                tmp.color             = c;
                yield return null;
            }
            gameObject.SetActive(false);
        }
    }
}
