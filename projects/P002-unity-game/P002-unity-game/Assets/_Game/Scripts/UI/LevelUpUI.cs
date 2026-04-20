using UnityEngine;
using UnityEngine.UI;
using TMPro;
using System.Collections.Generic;

namespace FortressCity
{
    public class LevelUpUI : MonoBehaviour
    {
        public static LevelUpUI Instance { get; private set; }

        [SerializeField] TMP_Text titleText;
        [SerializeField] Button[] skillButtons;   // 3 buttons
        [SerializeField] TMP_Text[] skillLabels;  // name labels inside buttons

        void Awake()
        {
            Instance = this;
            gameObject.SetActive(false);
        }

        public void Show(CityData city)
        {
            // Pick 3 random skills the hero doesn't already have
            var available = new List<HeroSkillType>();
            foreach (HeroSkillType s in System.Enum.GetValues(typeof(HeroSkillType)))
                if (!HeroSystem.HasSkill(city, s))
                    available.Add(s);

            if (available.Count == 0) { gameObject.SetActive(false); return; }

            // Shuffle
            for (int i = available.Count - 1; i > 0; i--)
            {
                int j = UnityEngine.Random.Range(0, i + 1);
                (available[i], available[j]) = (available[j], available[i]);
            }

            int count = Mathf.Min(3, available.Count);
            if (titleText) titleText.text = $"Level Up! Lv{city.heroLevel}\nスキルを選べ";

            gameObject.SetActive(true);
            StartCoroutine(UITween.PanelOpen(gameObject));

            for (int i = 0; i < skillButtons.Length; i++)
            {
                bool active = i < count;
                skillButtons[i].gameObject.SetActive(active);
                if (!active) continue;

                var skill = available[i];
                var data  = HeroSystem.GetData(skill);
                if (skillLabels[i]) skillLabels[i].text = $"{data.name}\n{data.description}";

                int idx = i;
                skillButtons[i].onClick.RemoveAllListeners();
                skillButtons[i].onClick.AddListener(() => PickSkill(city, available[idx]));
            }
        }

        void PickSkill(CityData city, HeroSkillType skill)
        {
            HeroSystem.AddSkill(city, skill);
            GameManager.Instance.SaveGame();
            StartCoroutine(UITween.PanelClose(gameObject));
        }
    }
}
