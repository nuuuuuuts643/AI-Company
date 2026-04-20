using UnityEngine;
using UnityEngine.UI;
using TMPro;

namespace FortressCity
{
    public class HowToPlayUI : MonoBehaviour
    {
        public static HowToPlayUI Instance { get; private set; }

        [SerializeField] Button closeButton;
        [SerializeField] Button prevButton;
        [SerializeField] Button nextButton;
        [SerializeField] TMP_Text pageText;
        [SerializeField] TMP_Text bodyText;

        int _page = 0;

        static readonly string[] Pages =
        {
            "◆ 目標\n\n12ヶ月間、城を守り抜け！\n\n城HPが0になったら即ゲームオーバー。\n勝てば伝説の守護者として語り継がれる。",

            "◆ 時間の流れ\n\n1ヶ月 = 4週間\nWeek 1〜3：準備期間\nWeek 4 → 月が変わる\n\n月が変わると敵が攻めてくる。\n準備不足のまま迎えるな。",

            "◆ 毎週の行動\n\n週を進める前に1つ選べ：\n\n訓練　→　歩兵+15、食料-25\n徴税　→　Gold+130\n修繕　→　城HP+80、Gold-100\n偵察　→　敵情報を入手\n民政　→　人口+25、食料+20\n\n修繕を怠ると城はじわじわ崩れる。",

            "◆ 月末レイド\n\n偵察済みなら敵の戦力・弱点がわかる。\n\n編成を4種から選んで出陣：\n全軍　均衡　温存　弱点特化\n\n勇者を出陣させると戦力+30%。\nただし倒れると3週間離脱する。",

            "◆ 城ダメージ\n\n勝っても負けても城HPは削られる。\n\n勝利 → -10〜20\n敗北 → -30〜80\n\n城HP0でゲームオーバー。\n毎週「修繕」を選んでHP管理が鍵。",

            "◆ 勇者のスキル\n\n出陣するたびに経験値が貯まる。\nレベルアップで3択スキルを選べ：\n\n剛力 → 歩兵ATK +30%\n鷹眼 → 弓・魔ATK +30%\n鉄壁 → 砦防御 +50%\n鼓舞 → 全兵種ATK +15%\n治癒 → 回復兵効果 ×2\n疾風 → 騎兵ATK +40%\n指揮 → 勇者補正 1.3→1.6",

            "◆ ランダムイベント\n\n週の35%の確率で選択を迫られる：\n\n旅の商人 → 食料を買う？\n流れ者の傭兵 → 雇う？\n盗賊団 → 払う or 戦う？\n石材商人 → Fort強化依頼？\n密偵 → 情報を買う？\n\nGoldと相談して判断しろ。",
        };

        void Awake()
        {
            Instance = this;
            gameObject.SetActive(false);
        }

        void Start()
        {
            closeButton.onClick.AddListener(Close);
            prevButton?.onClick.AddListener(() => FlipPage(-1));
            nextButton?.onClick.AddListener(() => FlipPage(+1));
        }

        public void Open(int startPage = 0)
        {
            _page = startPage;
            gameObject.SetActive(true);
            StartCoroutine(UITween.PanelOpen(gameObject));
            Render();
        }

        void Close() => StartCoroutine(UITween.PanelClose(gameObject));

        void FlipPage(int dir)
        {
            _page = (_page + dir + Pages.Length) % Pages.Length;
            Render();
        }

        void Render()
        {
            if (pageText) pageText.text = $"{_page + 1} / {Pages.Length}";
            if (bodyText) bodyText.text = Pages[_page];
        }
    }
}
