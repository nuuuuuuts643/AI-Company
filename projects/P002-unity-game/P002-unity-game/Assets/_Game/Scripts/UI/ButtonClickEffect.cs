using UnityEngine;
using UnityEngine.EventSystems;
using System.Collections;

namespace FortressCity
{
    [RequireComponent(typeof(UnityEngine.UI.Button))]
    public class ButtonClickEffect : MonoBehaviour, IPointerDownHandler, IPointerUpHandler
    {
        const float PRESS_SCALE = 0.91f;
        const float DURATION    = 0.07f;

        public void OnPointerDown(PointerEventData _) => StartCoroutine(ScaleTo(PRESS_SCALE, DURATION));
        public void OnPointerUp(PointerEventData _)   => StartCoroutine(ScaleTo(1f, DURATION));

        IEnumerator ScaleTo(float target, float dur)
        {
            float start = transform.localScale.x;
            float t = 0;
            while (t < dur)
            {
                t += Time.unscaledDeltaTime;
                float s = Mathf.Lerp(start, target, t / dur);
                transform.localScale = new Vector3(s, s, 1f);
                yield return null;
            }
            transform.localScale = new Vector3(target, target, 1f);
        }
    }
}
