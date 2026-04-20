using UnityEngine;

namespace FortressCity
{
    public class AudioManager : MonoBehaviour
    {
        public static AudioManager Instance { get; private set; }

        [Header("BGM")]
        [SerializeField] private AudioSource bgmSource;
        [SerializeField] private AudioClip   cityBGM;
        [SerializeField] private AudioClip   battleBGM;

        [Header("SE")]
        [SerializeField] private AudioSource seSource;
        [SerializeField] private AudioClip   buttonSE;
        [SerializeField] private AudioClip   upgradeSE;
        [SerializeField] private AudioClip   victorySE;
        [SerializeField] private AudioClip   defeatSE;
        [SerializeField] private AudioClip   hitSE;
        [SerializeField] private AudioClip   weekAdvanceSE;

        void Awake()
        {
            if (Instance != null) { Destroy(gameObject); return; }
            Instance = this;
            DontDestroyOnLoad(gameObject);
        }

        public void PlayCityBGM()   => SwitchBGM(cityBGM);
        public void PlayBattleBGM() => SwitchBGM(battleBGM);

        void SwitchBGM(AudioClip clip)
        {
            if (bgmSource == null || clip == null) return;
            if (bgmSource.clip == clip) return;
            bgmSource.clip = clip;
            bgmSource.loop = true;
            bgmSource.Play();
        }

        public void PlayButton()      => PlaySE(buttonSE);
        public void PlayUpgrade()     => PlaySE(upgradeSE);
        public void PlayVictory()     => PlaySE(victorySE);
        public void PlayDefeat()      => PlaySE(defeatSE);
        public void PlayHit()         => PlaySE(hitSE);
        public void PlayWeekAdvance() => PlaySE(weekAdvanceSE);

        void PlaySE(AudioClip clip) { if (seSource && clip) seSource.PlayOneShot(clip); }
    }
}
