using UnityEngine;
using UnityEngine.EventSystems;
using System.Collections;

namespace FortressCity
{
    // Attach to any Button for scale-bounce feedback.
    [RequireComponent(typeof(RectTransform))]
    public class ButtonFeedback : MonoBehaviour, IPointerDownHandler, IPointerUpHandler
    {
        [SerializeField] private float pressScale  = 0.88f;
        [SerializeField] private float duration    = 0.08f;
        [SerializeField] private bool  playSE      = true;

        private RectTransform rt;
        private Vector3       originalScale;
        private Coroutine     anim;

        void Awake()
        {
            rt            = GetComponent<RectTransform>();
            originalScale = rt.localScale;
        }

        public void OnPointerDown(PointerEventData _)
        {
            if (playSE) AudioManager.Instance?.PlayButton();
            if (anim != null) StopCoroutine(anim);
            anim = StartCoroutine(ScaleTo(originalScale * pressScale, duration));
        }

        public void OnPointerUp(PointerEventData _)
        {
            if (anim != null) StopCoroutine(anim);
            anim = StartCoroutine(ScaleTo(originalScale, duration));
        }

        IEnumerator ScaleTo(Vector3 target, float dur)
        {
            Vector3 start = rt.localScale;
            float   t     = 0;
            while (t < dur)
            {
                t           += Time.deltaTime;
                rt.localScale = Vector3.Lerp(start, target, t / dur);
                yield return null;
            }
            rt.localScale = target;
        }
    }
}
