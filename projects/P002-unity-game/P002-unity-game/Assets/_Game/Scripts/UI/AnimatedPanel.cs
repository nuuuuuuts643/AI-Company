using UnityEngine;

namespace FortressCity
{
    public class AnimatedPanel : MonoBehaviour
    {
        public void Open()
        {
            gameObject.SetActive(true);   // activate before starting coroutine
            StartCoroutine(UITween.PanelOpen(gameObject));
        }

        public void Close() => StartCoroutine(UITween.PanelClose(gameObject));
    }
}
