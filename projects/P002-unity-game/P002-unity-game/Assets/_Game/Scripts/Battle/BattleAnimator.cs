using UnityEngine;
using UnityEngine.UI;
using TMPro;
using System;
using System.Collections;

namespace FortressCity
{
    // Drives the battle visual sequence.
    // Designed to live on a Battle Canvas that is shown over the City scene.
    //
    // Canvas hierarchy:
    //   BattleCanvas
    //     PlayerSide   (Image: unit row — slides in from left)
    //     EnemySide    (Image: enemy sprite — slides in from right)
    //     ImpactPanel  (full-screen flash, alpha 0 normally)
    //     HitVFX       (particle or sprite burst at center)
    //     ResultText   (TMP: "Victory!" / "Defeat...")
    //     DamageText   (TMP: floating number)

    public class BattleAnimator : MonoBehaviour
    {
        public static BattleAnimator Instance { get; private set; }

        [Header("Sides")]
        [SerializeField] private RectTransform playerSide;
        [SerializeField] private RectTransform enemySide;
        [SerializeField] private Image         enemyImage;

        [Header("VFX")]
        [SerializeField] private Image    impactPanel;
        [SerializeField] private TMP_Text resultText;
        [SerializeField] private TMP_Text damageText;
        [SerializeField] private CameraShake cameraShake;

        [Header("Timing")]
        [SerializeField] private float marchDuration  = 0.5f;
        [SerializeField] private float clashPause     = 0.2f;
        [SerializeField] private float resultDuration = 1.0f;

        private Vector2 playerStartPos;
        private Vector2 enemyStartPos;

        void Awake()
        {
            Instance = this;
            playerStartPos = playerSide?.anchoredPosition ?? Vector2.zero;
            enemyStartPos  = enemySide?.anchoredPosition  ?? Vector2.zero;
            gameObject.SetActive(false);
        }

        public void PlayBattle(BattleReport report, EnemyData enemy, Action onComplete)
        {
            gameObject.SetActive(true);
            StartCoroutine(Sequence(report, enemy, onComplete));
        }

        IEnumerator Sequence(BattleReport report, EnemyData enemy, Action onComplete)
        {
            // Setup
            resultText.gameObject.SetActive(false);
            damageText.gameObject.SetActive(false);
            SetImpact(0f);

            if (enemyImage && enemy?.sprite) enemyImage.sprite = enemy.sprite;

            // Reset positions
            if (playerSide) playerSide.anchoredPosition = playerStartPos + Vector2.left * 400f;
            if (enemySide)  enemySide.anchoredPosition  = enemyStartPos  + Vector2.right * 400f;

            AudioManager.Instance?.PlayBattleBGM();

            // March in
            yield return March(marchDuration);

            // Clash flash
            AudioManager.Instance?.PlayHit();
            yield return Flash(0.8f, 0.1f);
            cameraShake?.Shake();

            yield return new WaitForSeconds(clashPause);

            // Damage text
            damageText.gameObject.SetActive(true);
            damageText.text  = $"-{report.casualties.TotalUnits()}";
            damageText.color = new Color(1f, 0.3f, 0.3f, 1f);
            yield return Fade(damageText, 0f, resultDuration * 0.5f);
            damageText.gameObject.SetActive(false);

            // Result
            bool win = report.result == BattleResult.Victory;
            resultText.gameObject.SetActive(true);
            resultText.text  = win ? "Victory!" : "Defeat...";
            resultText.color = win ? new Color(1f, 0.85f, 0.1f) : new Color(0.8f, 0.2f, 0.2f);

            if (win) AudioManager.Instance?.PlayVictory();
            else     AudioManager.Instance?.PlayDefeat();

            yield return new WaitForSeconds(resultDuration);

            // Slide out
            yield return March(marchDuration, reverse: true);

            gameObject.SetActive(false);
            AudioManager.Instance?.PlayCityBGM();
            onComplete?.Invoke();
        }

        IEnumerator March(float duration, bool reverse = false)
        {
            float t = 0;
            while (t < duration)
            {
                t += Time.deltaTime;
                float norm = Mathf.Clamp01(t / duration);
                float ease = reverse ? 1f - norm : norm;

                if (playerSide)
                    playerSide.anchoredPosition = Vector2.Lerp(
                        playerStartPos + Vector2.left * 400f, playerStartPos, ease);
                if (enemySide)
                    enemySide.anchoredPosition = Vector2.Lerp(
                        enemyStartPos + Vector2.right * 400f, enemyStartPos, ease);
                yield return null;
            }
        }

        IEnumerator Flash(float targetAlpha, float duration)
        {
            float t = 0;
            while (t < duration)
            {
                t += Time.deltaTime;
                SetImpact(Mathf.Lerp(0f, targetAlpha, t / duration));
                yield return null;
            }
            t = 0;
            while (t < duration)
            {
                t += Time.deltaTime;
                SetImpact(Mathf.Lerp(targetAlpha, 0f, t / duration));
                yield return null;
            }
        }

        IEnumerator Fade(TMP_Text text, float targetAlpha, float duration)
        {
            Color start = text.color;
            float t = 0;
            while (t < duration)
            {
                t += Time.deltaTime;
                var c = start;
                c.a = Mathf.Lerp(start.a, targetAlpha, t / duration);
                text.color = c;
                yield return null;
            }
        }

        void SetImpact(float alpha)
        {
            if (!impactPanel) return;
            var c = impactPanel.color;
            c.a = alpha;
            impactPanel.color = c;
        }
    }
}
