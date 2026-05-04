#!/usr/bin/env python3
"""
Daily article generator for くらしの節約ラボ
Generates 3 articles/day via Claude API + SEO optimization
"""

import anthropic, json, os, re, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ─── Setup ───────────────────────────────────────────────
JST      = timezone(timedelta(hours=9))
TODAY    = datetime.now(JST).strftime("%Y-%m-%d")
BASE_DIR = Path(__file__).parent.parent
ART_DIR  = BASE_DIR / "articles"
SCR_DIR  = Path(__file__).parent
SITE_URL = "https://beamish-palmier-604b39.netlify.app"

ART_DIR.mkdir(exist_ok=True)

with open(SCR_DIR / "topics.json",    encoding="utf-8") as f: TOPICS    = json.load(f)
with open(SCR_DIR / "affiliates.json",encoding="utf-8") as f: AFF_DATA  = json.load(f)

AMAZON_TAG = AFF_DATA["amazon_tag"]
client     = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

# ─── Topic Selection ─────────────────────────────────────
def get_todays_topics():
    start = datetime(2026, 5, 5, tzinfo=JST)
    day   = (datetime.now(JST) - start).days
    n     = len(TOPICS)
    return [TOPICS[(day * 3 + i) % n] for i in range(3)]

# ─── Affiliate Links ─────────────────────────────────────
def get_affiliate_links(topic):
    links = []
    kws   = topic.get("keywords", []) + [topic.get("title", "")]

    # match known products
    for p in AFF_DATA["products"]:
        if any(t in " ".join(kws) for t in p["tags"]):
            links.append(p)
        if len(links) >= 3:
            break

    # クレカ記事なら楽天カードを追加
    if "クレジットカード" in topic.get("category","") or "ポイント" in " ".join(kws):
        links.append({
            "name": "楽天カード（年会費永年無料）",
            "url":  AFF_DATA["rakuten_card"],
            "banner": AFF_DATA["rakuten_card_banner"],
            "emoji": "💳",
            "description": "還元率1%・新規入会ポイントあり"
        })

    # Amazon search fallback
    search = topic.get("amazon_search", topic["title"])
    links.append({
        "name":  f"{search} をAmazonで探す",
        "url":   f"https://www.amazon.co.jp/s?k={search.replace(' ','+')}&tag={AMAZON_TAG}",
        "emoji": "🛒",
        "description": "Amazonで最安値を確認する"
    })
    return links[:4]

# ─── Article Generation ──────────────────────────────────
def build_prompt(topic, links):
    link_list = "\n".join(f"- {l['name']}: {l['url']}" for l in links)
    return f"""あなたは日本の節約・暮らし系ブログ「くらしの節約ラボ」のプロライターです。

【記事情報】
タイトルテーマ: {topic['title']}
カテゴリ: {topic['category']}
キーワード: {', '.join(topic.get('keywords', []))}
ターゲット: 節約・家計管理に関心のある20〜40代

【使用するアフィリエイトリンク】
{link_list}

【出力形式】必ず以下のJSONのみを出力してください（説明文不要）:
{{
  "seo_title": "SEOタイトル（55文字以内・キーワードを含む）",
  "meta_description": "メタ説明文（110文字以内・具体的な数字を含む）",
  "h1": "記事H1タイトル（読者の悩みに直結・60文字以内）",
  "body_html": "記事本文HTML（h2/h3/p/ul/strong のみ使用・1500〜2000字）"
}}

【本文ルール】
- 冒頭: 読者の悩みに共感する2〜3文
- H2見出し: 4〜5個（各200〜400字）
- 具体的な数字・金額を必ず含める
- アフィリエイトリンクは以下の形式で自然に組み込む:
  <div class="affiliate-box" style="margin:20px 0;padding:16px;background:#F0FDF4;border:1.5px solid #BBF7D0;border-radius:12px;">
    <a href="URL" class="btn-amazon" target="_blank" rel="nofollow noopener">商品名を確認する →</a>
  </div>
- まとめセクション:
  <div class="summary-box"><h4>📋 まとめ</h4><ul>箇条書き</ul></div>"""

def generate(topic, links):
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=3000,
        messages=[{"role":"user","content": build_prompt(topic, links)}]
    )
    text = resp.content[0].text.strip()

    # JSON抽出
    m = re.search(r'\{[\s\S]*\}', text)
    if not m:
        raise ValueError(f"JSON not found in response: {text[:200]}")
    return json.loads(m.group())

# ─── HTML Building ────────────────────────────────────────
def build_html(topic, content, links, filename):
    product_cards = ""
    for link in links:
        if "banner" in link:
            product_cards += f"""
<div class="product-card">
  <div class="product-img-area">{link.get('emoji','💳')}</div>
  <div class="product-info">
    <p class="product-name">{link['name']}</p>
    <p class="product-desc">{link.get('description','')}</p>
    <a href="{link['url']}" target="_blank" rel="nofollow sponsored noopener" style="display:block;margin-bottom:8px;">
      <img src="{link['banner']}" style="max-width:200px;border-radius:6px;" alt="{link['name']}">
    </a>
    <a href="{link['url']}" class="btn-amazon" target="_blank" rel="nofollow noopener">申し込む →</a>
  </div>
</div>"""
        elif "amzn.to" in link.get("url","") or "amazon.co.jp" in link.get("url",""):
            if "s?k=" not in link.get("url",""):  # 特定商品のみカード表示
                product_cards += f"""
<div class="product-card">
  <div class="product-img-area">{link.get('emoji','🛒')}</div>
  <div class="product-info">
    <p class="product-name">{link['name']}</p>
    <p class="product-desc">{link.get('description','')}</p>
    <a href="{link['url']}" class="btn-amazon" target="_blank" rel="nofollow noopener">Amazonで見る →</a>
  </div>
</div>"""

    seo_title  = content['seo_title'].replace('"','&quot;')
    meta_desc  = content['meta_description'].replace('"','&quot;')
    h1         = content['h1']
    url        = f"{SITE_URL}/articles/{filename}"

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{seo_title} | くらしの節約ラボ</title>
  <meta name="description" content="{meta_desc}">
  <meta property="og:title" content="{seo_title}">
  <meta property="og:description" content="{meta_desc}">
  <meta property="og:type" content="article">
  <meta property="og:url" content="{url}">
  <link rel="canonical" href="{url}">
  <link rel="stylesheet" href="../style.css">
  <script type="application/ld+json">
  {{"@context":"https://schema.org","@type":"Article","headline":"{h1}","description":"{meta_desc}","datePublished":"{TODAY}","dateModified":"{TODAY}","publisher":{{"@type":"Organization","name":"くらしの節約ラボ","url":"{SITE_URL}"}}}}
  </script>
</head>
<body>
<header>
  <div class="header-inner">
    <a href="../index.html" class="logo">
      <div class="logo-icon">🏠</div>
      <div class="logo-text">
        <span class="logo-main">くらしの節約ラボ</span>
        <span class="logo-sub">暮らしをお得に、すっきりと</span>
      </div>
    </a>
    <nav>
      <a href="../index.html">ホーム</a>
      <a href="#">節約術</a>
      <a href="#">整理収納</a>
      <a href="../contact-au.html" class="nav-cta">無料料金診断</a>
    </nav>
  </div>
</header>

<div class="article-container">
  <main>
    <article>
      <div class="article-header">
        <span class="article-tag">{topic['category']}</span>
        <h1 class="article-title">{h1}</h1>
        <p class="article-meta">{TODAY}</p>
      </div>
      {content['body_html']}
      {product_cards}
      <div style="margin-top:32px;padding:16px;background:#f0f0f0;border-radius:8px;font-size:12px;color:#636e72;">
        ※当記事はアフィリエイト広告を利用しています。価格・情報は記事作成時点のものです。
      </div>
    </article>
  </main>
  <aside class="sidebar">
    <div class="widget cta-widget">
      <h3 class="widget-title">📞 無料料金診断</h3>
      <p>スマホ代・ネット代がいくら安くなるか無料で診断します。</p>
      <a href="../contact-au.html" class="cta-widget-btn">今すぐ無料相談 →</a>
    </div>
    <div class="widget">
      <h3 class="widget-title">カテゴリ</h3>
      <ul class="cat-list">
        <li><a href="#">📱 通信費節約</a></li>
        <li><a href="#">💳 クレカ節約</a></li>
        <li><a href="#">💰 日用品節約</a></li>
        <li><a href="#">🍳 整理収納</a></li>
      </ul>
    </div>
  </aside>
</div>

<footer>
  <div class="footer-inner">
    <div class="footer-logo">🏠 くらしの節約ラボ</div>
    <div class="footer-links">
      <a href="../index.html">ホーム</a>
      <a href="#">プライバシーポリシー</a>
    </div>
  </div>
  <div class="footer-note">&copy; 2026 くらしの節約ラボ ｜ 当サイトはアフィリエイト広告を利用しています。</div>
</footer>
</body>
</html>"""

# ─── Index Update ─────────────────────────────────────────
def update_index(articles):
    idx = BASE_DIR / "index.html"
    html = idx.read_text(encoding="utf-8")
    cards = ""
    for a in reversed(articles):
        cards += f"""
      <div class="card">
        <div class="card-img">{a['emoji']}</div>
        <div class="card-body">
          <span class="card-category">{a['category']}</span>
          <p class="card-title">{a['h1']}</p>
          <p class="card-meta">{TODAY}</p>
        </div>
        <div class="card-footer">
          <a href="articles/{a['filename']}" class="card-link">記事を読む →</a>
        </div>
      </div>
"""
    html = html.replace('<div class="card-grid">', '<div class="card-grid">' + cards, 1)
    idx.write_text(html, encoding="utf-8")

# ─── Sitemap ──────────────────────────────────────────────
def update_sitemap(filenames):
    sm = BASE_DIR / "sitemap.xml"
    if sm.exists():
        content = sm.read_text()
        existing = set(re.findall(r'<loc>(.*?)</loc>', content))
    else:
        existing = set()
        content = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>{SITE_URL}/</loc><lastmod>{TODAY}</lastmod><changefreq>daily</changefreq><priority>1.0</priority></url>
  <url><loc>{SITE_URL}/article-carrier.html</loc><lastmod>{TODAY}</lastmod><changefreq>monthly</changefreq><priority>0.8</priority></url>
  <url><loc>{SITE_URL}/article-creditcard.html</loc><lastmod>{TODAY}</lastmod><changefreq>monthly</changefreq><priority>0.8</priority></url>
  <url><loc>{SITE_URL}/article-kitchen.html</loc><lastmod>{TODAY}</lastmod><changefreq>monthly</changefreq><priority>0.8</priority></url>
  <url><loc>{SITE_URL}/article-setsuyaku.html</loc><lastmod>{TODAY}</lastmod><changefreq>monthly</changefreq><priority>0.8</priority></url>
</urlset>"""

    new_entries = ""
    for fn in filenames:
        url = f"{SITE_URL}/articles/{fn}"
        if url not in existing:
            new_entries += f'  <url><loc>{url}</loc><lastmod>{TODAY}</lastmod><changefreq>monthly</changefreq><priority>0.7</priority></url>\n'

    content = content.replace("</urlset>", new_entries + "</urlset>")
    sm.write_text(content)

# ─── robots.txt ───────────────────────────────────────────
def ensure_robots():
    rb = BASE_DIR / "robots.txt"
    if not rb.exists():
        rb.write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n")

# ─── Main ─────────────────────────────────────────────────
def main():
    print(f"🚀 記事生成開始: {TODAY}")
    ensure_robots()
    topics   = get_todays_topics()
    articles = []
    filenames = []

    for i, topic in enumerate(topics):
        print(f"  [{i+1}/3] {topic['title']}")
        try:
            links    = get_affiliate_links(topic)
            content  = generate(topic, links)
            filename = f"{TODAY}-{topic['slug']}.html"
            filepath = ART_DIR / filename

            html = build_html(topic, content, links, filename)
            filepath.write_text(html, encoding="utf-8")

            articles.append({
                "filename": filename,
                "h1":       content["h1"],
                "category": topic["category"],
                "emoji":    topic.get("emoji","📝")
            })
            filenames.append(filename)
            print(f"  ✅ {filename}")

        except Exception as e:
            print(f"  ❌ エラー ({topic['slug']}): {e}", file=sys.stderr)

    if articles:
        update_index(articles)
        update_sitemap(filenames)
        print(f"\n✅ 完了: {len(articles)}本 生成")
    else:
        print("⚠️ 記事生成に失敗しました", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
