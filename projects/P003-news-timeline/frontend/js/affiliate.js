// ===== アフィリエイトウィジェット =====
// 依存: config.js (AFFILIATE_MOSHIMO_A_ID, AFFILIATE_AMAZON_TAG, AFFILIATE_RAKUTEN_ID), app.js (esc)
function renderAffiliate(meta) {
  const section = document.getElementById('affiliate-section');
  const linksEl = document.getElementById('affiliate-links');
  if (!section || !linksEl) return;

  const moshimoId = (typeof AFFILIATE_MOSHIMO_A_ID !== 'undefined') ? AFFILIATE_MOSHIMO_A_ID : '';
  const amazonTag = (typeof AFFILIATE_AMAZON_TAG   !== 'undefined') ? AFFILIATE_AMAZON_TAG   : '';
  const rakutenId = (typeof AFFILIATE_RAKUTEN_ID   !== 'undefined') ? AFFILIATE_RAKUTEN_ID   : '';

  if (!moshimoId && !amazonTag && !rakutenId) return;

  const topicGenres = meta.genres || (meta.genre ? [meta.genre] : []);

  const GENRE_KEYWORD = {
    'テクノロジー': 'ガジェット 最新',
    'グルメ': 'お取り寄せ グルメ',
    'ファッション': 'ファッション アイテム',
    'スポーツ': 'スポーツ 用品',
    'エンタメ': 'エンタメ グッズ',
    '健康': '健康 書籍',
    'ビジネス': 'ビジネス 書籍',
    '科学': '科学 本',
    'くらし': 'くらし 雑貨',
    '総合': 'おすすめ 人気',
    '社会': '教養 書籍',
    '国際': '国際 書籍',
    '株・金融': '投資 書籍',
    '政治': 'ビジネス 書籍',
  };

  const keyword = GENRE_KEYWORD[topicGenres[0]] || 'おすすめ 人気';

  const q    = encodeURIComponent(keyword);
  const items = [];

  if (moshimoId) {
    const aid = encodeURIComponent(moshimoId);
    const amzUrl = encodeURIComponent(`https://www.amazon.co.jp/s?k=${q}`);
    const rktUrl = encodeURIComponent(`https://search.rakuten.co.jp/search/mall/${q}/`);
    const yhsUrl = encodeURIComponent(`https://shopping.yahoo.co.jp/search?p=${q}`);
    items.push(
      { href: `https://af.moshimo.com/af/c/click?a_id=${aid}&p_id=170&pc_id=185&pl_id=4062&url=${amzUrl}`,
        logoClass: 'amazon', logoText: '🛒', shop: 'Amazon.co.jp', label: `「${keyword}」をAmazonで探す` },
      { href: `https://af.moshimo.com/af/c/click?a_id=${aid}&p_id=54&pc_id=53&pl_id=616&url=${rktUrl}`,
        logoClass: 'rakuten', logoText: '楽天', shop: '楽天市場', label: `「${keyword}」を楽天市場で探す` },
      { href: `https://af.moshimo.com/af/c/click?a_id=${aid}&p_id=1225&pc_id=2254&pl_id=7610&url=${yhsUrl}`,
        logoClass: 'yahoo', logoText: 'Y!', shop: 'Yahoo!ショッピング', label: `「${keyword}」をYahoo!ショッピングで探す` },
    );
  } else {
    if (amazonTag) {
      items.push({
        href: `https://www.amazon.co.jp/s?k=${q}&tag=${encodeURIComponent(amazonTag)}`,
        logoClass: 'amazon', logoText: '🛒', shop: 'Amazon.co.jp', label: `「${keyword}」をAmazonで探す`,
      });
    }
    if (rakutenId) {
      items.push({
        href: `https://hb.afl.rakuten.co.jp/hgc/${encodeURIComponent(rakutenId)}/?pc=https://search.rakuten.co.jp/search/mall/${q}/`,
        logoClass: 'rakuten', logoText: '楽天', shop: '楽天市場', label: `「${keyword}」を楽天市場で探す`,
      });
    }
  }

  if (!items.length) {
    section.style.display = 'none';
    return;
  }

  linksEl.innerHTML = items.map(it => `
    <a href="${esc(it.href)}" target="_blank" rel="noopener sponsored" class="affiliate-link-item">
      <div class="affiliate-link-logo ${esc(it.logoClass)}">${it.logoText}</div>
      <div class="affiliate-link-body">
        <div class="affiliate-link-shop">${esc(it.shop)}</div>
        <div class="affiliate-link-title">${esc(it.label)}</div>
      </div>
      <span class="affiliate-link-arrow">›</span>
    </a>
  `).join('') + `<p class="affiliate-note">※ アフィリエイトリンクを含みます。購入者様の費用は変わりません。</p>`;

  section.style.display = '';
}
