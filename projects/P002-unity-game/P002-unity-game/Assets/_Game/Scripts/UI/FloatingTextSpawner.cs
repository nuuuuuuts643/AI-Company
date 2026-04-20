using UnityEngine;
using TMPro;

namespace FortressCity
{
    public class FloatingTextSpawner : MonoBehaviour
    {
        public static FloatingTextSpawner Instance { get; private set; }

        [SerializeField] private int poolSize = 12;

        private FloatingText[] pool;
        private int            idx;

        void Awake()
        {
            Instance = this;
            pool     = new FloatingText[poolSize];
            for (int i = 0; i < poolSize; i++)
            {
                var go  = new GameObject($"FloatTxt_{i}");
                go.transform.SetParent(transform, false);
                var tmp = go.AddComponent<TextMeshProUGUI>();
                tmp.fontSize  = 52;
                tmp.fontStyle = TMPro.FontStyles.Bold;
                tmp.alignment = TMPro.TextAlignmentOptions.Center;
                tmp.raycastTarget = false;
                var rt = go.GetComponent<RectTransform>();
                rt.sizeDelta = new Vector2(320, 80);
                pool[i] = go.AddComponent<FloatingText>();
                go.SetActive(false);
            }
        }

        public void Spawn(string text, Color color, Vector2 anchoredPos)
        {
            if (pool == null) return;
            var ft = pool[idx % poolSize];
            if (ft == null) return;
            idx++;
            ft.GetComponent<RectTransform>().anchoredPosition = anchoredPos;
            ft.Play(text, color);
        }
    }
}
