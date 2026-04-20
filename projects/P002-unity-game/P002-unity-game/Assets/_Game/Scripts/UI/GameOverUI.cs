using UnityEngine;
using UnityEngine.UI;
using TMPro;
using UnityEngine.SceneManagement;

namespace FortressCity
{
    public class GameOverUI : MonoBehaviour
    {
        public static GameOverUI Instance { get; private set; }

        [SerializeField] TMP_Text titleText;
        [SerializeField] TMP_Text subtitleText;
        [SerializeField] Button   replayButton;

        void Awake()
        {
            Instance = this;
            gameObject.SetActive(false);
        }

        void Start()
        {
            replayButton.onClick.AddListener(OnReplay);
            GameManager.Instance.OnGameOver += ShowGameOver;
            GameManager.Instance.OnVictory  += ShowVictory;
        }

        void OnDestroy()
        {
            if (GameManager.Instance == null) return;
            GameManager.Instance.OnGameOver -= ShowGameOver;
            GameManager.Instance.OnVictory  -= ShowVictory;
        }

        void ShowGameOver()
        {
            if (titleText)    titleText.text    = "城が落ちた...";
            if (subtitleText) subtitleText.text = $"Month {GameManager.Instance.City.month} で敗北\n次こそ勝て";
            titleText.color = new Color(0.8f, 0.2f, 0.2f);
            Open();
        }

        void ShowVictory()
        {
            if (titleText)    titleText.text    = "12ヶ月防衛達成！";
            if (subtitleText) subtitleText.text = "城は守られた。\n勇者の伝説は語り継がれるだろう。";
            titleText.color = new Color(1f, 0.85f, 0.1f);
            Open();
        }

        void Open()
        {
            gameObject.SetActive(true);
            StartCoroutine(UITween.PanelOpen(gameObject));
        }

        void OnReplay()
        {
            GameManager.Instance.ResetGame();
            SceneManager.LoadScene("City");
        }
    }
}
