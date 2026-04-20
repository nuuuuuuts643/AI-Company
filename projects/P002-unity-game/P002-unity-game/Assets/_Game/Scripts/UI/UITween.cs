using UnityEngine;
using System.Collections;

namespace FortressCity
{
    public static class UITween
    {
        public static IEnumerator PanelOpen(GameObject panel, float duration = 0.18f)
        {
            var rt = panel.GetComponent<RectTransform>();
            var cg = panel.GetComponent<CanvasGroup>();
            if (cg == null) cg = panel.AddComponent<CanvasGroup>();
            // panel must already be SetActive(true) before this coroutine starts
            cg.alpha = 0f;
            rt.localScale = new Vector3(0.88f, 0.88f, 1f);
            float t = 0;
            while (t < duration)
            {
                t += Time.unscaledDeltaTime;
                float p = Mathf.SmoothStep(0f, 1f, t / duration);
                cg.alpha = p;
                float s = Mathf.Lerp(0.88f, 1f, p);
                rt.localScale = new Vector3(s, s, 1f);
                yield return null;
            }
            cg.alpha = 1f;
            rt.localScale = Vector3.one;
        }

        public static IEnumerator PanelClose(GameObject panel, float duration = 0.12f)
        {
            var rt = panel.GetComponent<RectTransform>();
            var cg = panel.GetComponent<CanvasGroup>();
            if (cg == null) cg = panel.AddComponent<CanvasGroup>();
            float t = 0;
            while (t < duration)
            {
                t += Time.unscaledDeltaTime;
                float p = Mathf.SmoothStep(0f, 1f, t / duration);
                cg.alpha = 1f - p;
                float s = Mathf.Lerp(1f, 0.88f, p);
                rt.localScale = new Vector3(s, s, 1f);
                yield return null;
            }
            panel.SetActive(false);
            cg.alpha = 1f;
            rt.localScale = Vector3.one;
        }

        public static IEnumerator NumberPop(RectTransform rt, float duration = 0.28f)
        {
            float t = 0;
            while (t < duration)
            {
                t += Time.unscaledDeltaTime;
                float s = 1f + 0.22f * Mathf.Sin((t / duration) * Mathf.PI);
                rt.localScale = new Vector3(s, s, 1f);
                yield return null;
            }
            rt.localScale = Vector3.one;
        }
    }
}
