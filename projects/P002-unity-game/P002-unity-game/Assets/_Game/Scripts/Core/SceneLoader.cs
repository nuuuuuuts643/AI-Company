using UnityEngine;
using UnityEngine.SceneManagement;
using System.Collections;

namespace FortressCity
{
    public class SceneLoader : MonoBehaviour
    {
        public static SceneLoader Instance { get; private set; }

        [SerializeField] private Animator fadeAnimator;
        [SerializeField] private float    fadeDuration = 0.3f;

        void Awake()
        {
            if (Instance != null) { Destroy(gameObject); return; }
            Instance = this;
            DontDestroyOnLoad(gameObject);
        }

        public void LoadCity()   => StartCoroutine(Load("City"));
        public void LoadBattle() => StartCoroutine(Load("Battle"));
        public void LoadBoot()   => StartCoroutine(Load("Boot"));

        IEnumerator Load(string sceneName)
        {
            fadeAnimator?.SetTrigger("FadeOut");
            yield return new WaitForSeconds(fadeDuration);
            SceneManager.LoadScene(sceneName);
        }
    }
}
