#!/usr/bin/env python3
"""
Daily article generator — くらしの節約ラボ
3 articles/day · SEO-optimized · affiliate-injected
"""

import anthropic, json, os, re, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ─── Config ──────────────────────────────────────────────
JST      = timezone(timedelta(hours=9))
TODAY    = datetime.now(JST).strftime("%Y-%m-%d")
BASE_DIR = Path(__file__).parent.parent
ART_DIR  = BASE_DIR / "articles"
SCR_DIR  = Path(__file__).parent
SITE_URL = "https://beamish-palmier-604b39.netlify.app"

ART_DIR.mkdir(exist_ok=True)

with open(SCR_DIR / "topics.json",     encoding="utf-8") as f: TOPICS   = json.load(f)
with open(SCR_DIR / "affiliates.json", encoding="utf-8") as f: AFF      = json.load(f)

AMAZON_TAG = AFF["amazon_tag"]
client     = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

# ─── Commission priority sort ─────────────────────────────
PROGRAMS = sorted(AFF["programs"], key=lambda x: x["commission"], reverse=True)

# ─── Topic Selection ─────────────────────────────────────
def get_todays_topics():
    start = datetime(2026, 5, 5, tzinfo=JST)
    day   = (datetime.now(JST) - start).days
    n     = len(TOPICS)
    return [TOPICS[(day * 3 + i) % n] for i in range(3)]

# ─── Affiliate Link Matching ─────────────────────────────
def get_links(topic):
    """Returns list of affiliate links sorted by commission (highest first)."""
    kw_str = " ".join(topic.get("keywords", []) + [topic["title"], topic["category"]])
    matched = []

    # High-value programs first
    for prog in PROGRAMS:
        if any(t in kw_str for t in prog["tags"]):
            if not prog["url"].startswith("PENDING"):
                matched.append({**prog, "type": "program"})
            else:
                # Pending: use contact-au as bridge for communication/utility programs
                if prog["category"] in ["通信費節約", "光熱費節約"]:
                    matched.append({
                        **prog,
                        "url": f"{SITE_URL}/contact-au.html",
                        "type": "consult",
                        "description": f"{prog['name']}への乗り換えで月々節約できます。まずは無料診断で金額を確認しましょう。",
                        "cta": "無料で節約額を診断する"
                    })
        if len(matched) >= 3:
            break

    # Amazon products
    for p in AFF["amazon_products"]:
        if any(t in kw_str for t in p["tags"]):
            matched.append({**p, "type": "amazon", "commission": 0})
        if len(matched) >= 4:
            break

    # Amazon search fallback (always earns when clicked + purchased)
    search = topic.get("amazon_search", topic["title"])
    matched.append({
        "name": f"{search}をAmazonで探す",
        "url":  f"https://www.amazon.co.jp/s?k={search.replace(' ','+')}&tag={AMAZON_TAG}",
        "type": "amazon_search",
        "emoji": "🛒",
        "description": "Amazonで最安値・レビューを確認する",
        "cta": "Amazonで確認する",
        "commission": 0
    })
    return matched[:5]

# ─── Internal Link Discovery ─────────────────────────────
def get_internal_links(topic, current_filename=""):
    """Find 3 related articles for internal linking (SEO boost)."""
    links = []
    kws   = set(topic.get("keywords", []) + [topic["category"]])

    # Static articles
    static = [
        {"file": "article-carrier.html",     "title": "スマホ代を月3,000円安くする方法", "tags": {"通信費","スマホ","キャリア"}},
        {"file": "article-creditcard.html",   "title": "クレジットカードで年間2万円節約",  "tags": {"クレジットカード","ポイント","節約"}},
        {"file": "article-kitchen.html",      "title": "キッチン収納グッズおすすめ10選",   "tags": {"キッチン","収納","整理"}},
        {"file": "article-setsuyaku.html",    "title": "日用品代を月5,000円節約する方法",  "tags": {"節約","日用品","消耗品"}},
    ]
    for s in static:
        if kws & s["tags"] and s["file"] != current_filename:
            links.append({"url": f"../{s['file']}", "title": s["title"]})

    # Recent generated articles
    art_files = sorted(ART_DIR.glob("*.html"), reverse=True)[:20]
    for f in art_files:
        if f.name == current_filename or len(links) >= 3:
            break
        # Simple keyword match from filename slug
        slug_words = set(f.stem.replace("-", " ").split())
        if kws & slug_words or topic["category"].replace("節約","") in f.stem:
            # Read title from file
            try:
                content = f.read_text(encoding="utf-8")
                m = re.search(r'<h1 class="article-title">(.*?)</h1>', content)
                title = m.group(1) if m else f.stem
                links.append({"url": f"../articles/{f.name}", "title": title})
            except Exception:
                pass

    return links[:3]

# ─── Article Generation ──────────────────────────────────
def build_prompt(topic, links, internal_links):
    link_list = "\n".join(
        f"- 【{l.get('commission',0):,}円/件】{l['name']} ({l['url']}) — {l.get('description','')}"
        for l in links
    )
    int_links = "\n".join(f"- {il['title']}: {il['url']}" for il in internal_links)

    return f"""あなたは日本のSEO特化型節約ブログ「くらしの節約ラボ」のプロライターです。
Googleの検索意図に完全に応える、E-E-A-T（経験・専門性・権威性・信頼性）を満たした記事を書いてください。

【記事テーマ】{topic['title']}
【カテゴリ】{topic['category']}
【ターゲットキーワード】{', '.join(topic.get('keywords', []))}
【読者】節約・家計管理に関心のある20〜40代

【使用するアフィリエイトリンク（報酬の高い順）】
{link_list}

【内部リンク（自然に組み込む）】
{int_links}

【出力形式】以下の区切りタグで各要素を返してください。JSONは使わないこと。

<SEO_TITLE>SEOタイトル（55字以内）</SEO_TITLE>
<META_DESC>メタディスクリプション（110字以内）</META_DESC>
<H1>H1タイトル（60字以内）</H1>
<FAQ_Q1>質問1</FAQ_Q1><FAQ_A1>回答1</FAQ_A1>
<FAQ_Q2>質問2</FAQ_Q2><FAQ_A2>回答2</FAQ_A2>
<FAQ_Q3>質問3</FAQ_Q3><FAQ_A3>回答3</FAQ_A3>
<BODY>
記事本文HTML（h2/h3/p/ul/ol/strong/table タグのみ使用・1800〜2400字）
</BODY>

【本文の必須要素】
1. 冒頭（リード文）: 読者の悩みに共感 → この記事で解決できることを明示（200字）
2. H2×4〜5個: 各300〜400字・具体的な数字・実践可能なアドバイス
3. 比較テーブル: 以下のHTMLで商品・サービスを比較する
   <table class="carrier-table"><tr><th>項目</th><th>内容</th><th>特徴</th></tr>...</table>
4. アフィリエイトリンク: 以下のHTMLで自然に配置（記事中2〜3箇所）
   <div class="affiliate-box" style="margin:20px 0;padding:20px;background:#F0FDF4;border:2px solid #BBF7D0;border-radius:12px;text-align:center;">
     <p style="font-weight:700;margin-bottom:10px;">🔗 リンクテキスト</p>
     <a href="URL" class="btn-consult" target="_blank" rel="nofollow noopener" style="display:inline-block;background:linear-gradient(135deg,#16A34A,#0D9488);color:white;padding:14px 32px;border-radius:10px;font-weight:800;font-size:15px;text-decoration:none;">CTA文言 →</a>
   </div>
5. 内部リンク: 本文中に自然に埋め込む（アンカーテキスト形式）
6. まとめ:
   <div class="summary-box"><h4>📋 この記事のまとめ</h4><ul>具体的な箇条書き5項目</ul></div>

【SEOルール】
- メインキーワードをH1・最初のH2・本文冒頭100字以内に含める
- 共起語（関連語）を自然に散りばめる
- 文字数: 1800〜2400字
- 読者が「これは自分に役立つ」と感じる具体的な数字・事例を必ず含める"""

def call_api(prompt, max_tokens=1024):
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}]
    )
    return resp.content[0].text.strip()

def generate(topic, links, internal_links):
    kw       = ', '.join(topic.get('keywords', []))
    link_txt = "\n".join(f"- {l['name']}: {l['url']} ({l.get('description','')})" for l in links)
    int_txt  = "\n".join(f"- {il['title']}: {il['url']}" for il in internal_links)

    # ── Step 1: Meta info (small, reliable) ──────────────
    meta_prompt = f"""日本の節約ブログ「くらしの節約ラボ」の記事メタ情報を生成してください。
テーマ: {topic['title']} / カテゴリ: {topic['category']} / キーワード: {kw}

以下の形式で返してください（他の文章は不要）:
<SEO_TITLE>55字以内のSEOタイトル</SEO_TITLE>
<META_DESC>110字以内のメタディスクリプション（具体的な数字を含める）</META_DESC>
<H1>60字以内のH1タイトル</H1>
<FAQ_Q1>よくある質問1</FAQ_Q1><FAQ_A1>その回答1（2〜3文）</FAQ_A1>
<FAQ_Q2>よくある質問2</FAQ_Q2><FAQ_A2>その回答2（2〜3文）</FAQ_A2>
<FAQ_Q3>よくある質問3</FAQ_Q3><FAQ_A3>その回答3（2〜3文）</FAQ_A3>"""

    meta_text = call_api(meta_prompt, max_tokens=800)

    def xtag(text, tag):
        m = re.search(rf'<{tag}>([\s\S]*?)</{tag}>', text)
        return m.group(1).strip() if m else ""

    seo_title = xtag(meta_text, "SEO_TITLE") or topic["title"]
    meta_desc = xtag(meta_text, "META_DESC") or topic["title"]
    h1        = xtag(meta_text, "H1") or topic["title"]
    faq = [
        {"q": xtag(meta_text, f"FAQ_Q{i}"), "a": xtag(meta_text, f"FAQ_A{i}")}
        for i in range(1, 4)
        if xtag(meta_text, f"FAQ_Q{i}")
    ]

    # ── Step 2: Body HTML (separate call, full tokens) ────
    body_prompt = f"""日本の節約ブログ「くらしの節約ラボ」の記事本文を書いてください。

タイトル: {h1}
カテゴリ: {topic['category']}
キーワード: {kw}

【アフィリエイトリンク（必ず組み込む）】
{link_txt}

【内部リンク（本文中に自然に組み込む）】
{int_txt}

【ルール】
- h2/h3/p/ul/ol/strong/table タグのみ使用
- 1800〜2200字
- 具体的な数字・金額を含める
- アフィリエイトリンクは以下のHTMLで2〜3箇所に配置:
  <div class="affiliate-box" style="margin:20px 0;padding:20px;background:#F0FDF4;border:2px solid #BBF7D0;border-radius:12px;text-align:center;"><p style="font-weight:700;margin-bottom:10px;">説明文</p><a href="URL" class="btn-consult" target="_blank" rel="nofollow noopener" style="display:inline-block;background:linear-gradient(135deg,#16A34A,#0D9488);color:white;padding:14px 32px;border-radius:10px;font-weight:800;text-decoration:none;">CTA文言 →</a></div>
- 最後にまとめセクション:
  <div class="summary-box"><h4>📋 この記事のまとめ</h4><ul><li>ポイント1</li>...</ul></div>

HTMLのみ返してください（説明文・コードブロック記号は不要）:"""

    body_html = call_api(body_prompt, max_tokens=3000)
    # コードブロック除去
    body_html = re.sub(r'^```[\w]*\n?', '', body_html)
    body_html = re.sub(r'\n?```$', '', body_html).strip()

    if len(body_html) < 200:
        raise ValueError(f"Body too short ({len(body_html)} chars)")

    return {
        "seo_title":        seo_title,
        "meta_description": meta_desc,
        "h1":               h1,
        "faq":              faq,
        "body_html":        body_html
    }

# ─── HTML Building ────────────────────────────────────────
def build_html(topic, content, links, internal_links, filename):
    url   = f"{SITE_URL}/articles/{filename}"
    h1    = content["h1"]
    title = content["seo_title"].replace('"','&quot;')
    desc  = content["meta_description"].replace('"','&quot;')

    # FAQ JSON-LD
    faq_items = content.get("faq", [])
    faq_ld = json.dumps({
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type":"Question","name":f["q"],"acceptedAnswer":{"@type":"Answer","text":f["a"]}}
            for f in faq_items
        ]
    }, ensure_ascii=False)

    # FAQ HTML
    faq_html = ""
    if faq_items:
        faq_html = '<h2>よくある質問</h2>'
        for f in faq_items:
            faq_html += f"""<details style="border:1.5px solid #E2E8F0;border-radius:10px;padding:14px 18px;margin-bottom:10px;">
  <summary style="font-weight:700;cursor:pointer;list-style:none;font-size:15px;">❓ {f['q']}</summary>
  <p style="margin-top:12px;color:#475569;">{f['a']}</p>
</details>"""

    # Internal links HTML
    int_html = ""
    if internal_links:
        int_html = '<div class="summary-box" style="margin-top:32px;"><h4>📚 関連記事</h4><ul>'
        for il in internal_links:
            int_html += f'<li><a href="{il["url"]}">{il["title"]}</a></li>'
        int_html += '</ul></div>'

    # Product cards for Amazon products only
    product_cards = ""
    for link in links:
        lt = link.get("type","")
        if lt == "amazon" and "amzn.to" in link.get("url",""):
            product_cards += f"""<div class="product-card">
  <div class="product-img-area">{link.get('emoji','🛒')}</div>
  <div class="product-info">
    <p class="product-name">{link['name']}</p>
    <p class="product-desc">{link.get('description','')}</p>
    <a href="{link['url']}" class="btn-amazon" target="_blank" rel="nofollow noopener">Amazonで見る →</a>
  </div>
</div>"""
        elif lt == "program" and "banner" in link:
            product_cards += f"""<div class="product-card">
  <div class="product-img-area">{link.get('emoji','💳')}</div>
  <div class="product-info">
    <p class="product-name">{link['name']}</p>
    <p class="product-desc">{link.get('description','')}</p>
    <a href="{link['url']}" target="_blank" rel="nofollow sponsored noopener">
      <img src="{link['banner']}" style="max-width:200px;border-radius:6px;margin-bottom:8px;" alt="{link['name']}">
    </a>
    <a href="{link['url']}" class="btn-amazon" target="_blank" rel="nofollow noopener">{link.get('cta','申し込む')} →</a>
  </div>
</div>"""

    # Article JSON-LD
    art_ld = json.dumps({
        "@context":"https://schema.org","@type":"Article",
        "headline":h1,"description":desc,
        "datePublished":TODAY,"dateModified":TODAY,
        "publisher":{"@type":"Organization","name":"くらしの節約ラボ","url":SITE_URL}
    }, ensure_ascii=False)

    # Breadcrumb JSON-LD
    bc_ld = json.dumps({
        "@context":"https://schema.org","@type":"BreadcrumbList",
        "itemListElement":[
            {"@type":"ListItem","position":1,"name":"ホーム","item":SITE_URL},
            {"@type":"ListItem","position":2,"name":topic["category"],"item":f"{SITE_URL}/articles/"},
            {"@type":"ListItem","position":3,"name":h1,"item":url}
        ]
    }, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} | くらしの節約ラボ</title>
  <meta name="description" content="{desc}">
  <meta property="og:title" content="{title}">
  <meta property="og:description" content="{desc}">
  <meta property="og:type" content="article">
  <meta property="og:url" content="{url}">
  <meta property="og:site_name" content="くらしの節約ラボ">
  <link rel="canonical" href="{url}">
  <link rel="stylesheet" href="../style.css">
  <script type="application/ld+json">{art_ld}</script>
  <script type="application/ld+json">{bc_ld}</script>
  <script type="application/ld+json">{faq_ld}</script>
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
      {faq_html}
      {product_cards}
      {int_html}

      <div style="margin-top:32px;padding:16px;background:#f0f0f0;border-radius:8px;font-size:12px;color:#636e72;">
        ※当記事はアフィリエイト広告を利用しています。記事内リンクから申込・購入された場合、当サイトに報酬が発生します。価格・情報は記事作成時点のものです。
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
        <li><a href="#">⚡ 光熱費節約</a></li>
        <li><a href="#">💳 クレカ節約</a></li>
        <li><a href="#">💰 日用品節約</a></li>
        <li><a href="#">🍳 整理収納</a></li>
      </ul>
    </div>
    <div class="widget">
      <h3 class="widget-title">関連記事</h3>
      <ul class="cat-list">
        {''.join(f'<li><a href="{il["url"]}">{il["title"]}</a></li>' for il in internal_links)}
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

# ─── Index & Sitemap ──────────────────────────────────────
def update_index(articles):
    idx  = BASE_DIR / "index.html"
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
      </div>\n"""
    html = html.replace('<div class="card-grid">', '<div class="card-grid">' + cards, 1)
    idx.write_text(html, encoding="utf-8")

def update_sitemap(filenames):
    sm = BASE_DIR / "sitemap.xml"
    if sm.exists():
        content  = sm.read_text()
        existing = set(re.findall(r'<loc>(.*?)</loc>', content))
    else:
        existing = set()
        content  = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>{SITE_URL}/</loc><lastmod>{TODAY}</lastmod><changefreq>daily</changefreq><priority>1.0</priority></url>
  <url><loc>{SITE_URL}/article-carrier.html</loc><lastmod>{TODAY}</lastmod><changefreq>monthly</changefreq><priority>0.8</priority></url>
  <url><loc>{SITE_URL}/article-creditcard.html</loc><lastmod>{TODAY}</lastmod><changefreq>monthly</changefreq><priority>0.8</priority></url>
  <url><loc>{SITE_URL}/article-kitchen.html</loc><lastmod>{TODAY}</lastmod><changefreq>monthly</changefreq><priority>0.8</priority></url>
  <url><loc>{SITE_URL}/article-setsuyaku.html</loc><lastmod>{TODAY}</lastmod><changefreq>monthly</changefreq><priority>0.8</priority></url>
</urlset>"""

    new = ""
    for fn in filenames:
        url = f"{SITE_URL}/articles/{fn}"
        if url not in existing:
            new += f'  <url><loc>{url}</loc><lastmod>{TODAY}</lastmod><changefreq>monthly</changefreq><priority>0.7</priority></url>\n'
    content = content.replace("</urlset>", new + "</urlset>")
    sm.write_text(content)

def ensure_robots():
    rb = BASE_DIR / "robots.txt"
    if not rb.exists():
        rb.write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n")

# ─── Main ─────────────────────────────────────────────────
def main():
    print(f"🚀 記事生成開始: {TODAY}")
    ensure_robots()

    topics    = get_todays_topics()
    articles  = []
    filenames = []

    for i, topic in enumerate(topics):
        print(f"  [{i+1}/3] {topic['title']}")
        try:
            filename       = f"{TODAY}-{topic['slug']}.html"
            links          = get_links(topic)
            internal_links = get_internal_links(topic, filename)
            content        = generate(topic, links, internal_links)
            html           = build_html(topic, content, links, internal_links, filename)

            (ART_DIR / filename).write_text(html, encoding="utf-8")

            articles.append({
                "filename": filename,
                "h1":       content["h1"],
                "category": topic["category"],
                "emoji":    topic.get("emoji","📝")
            })
            filenames.append(filename)
            print(f"  ✅ {filename}")

        except Exception as e:
            print(f"  ❌ {topic['slug']}: {e}", file=sys.stderr)

    if articles:
        update_index(articles)
        update_sitemap(filenames)
        print(f"\n✅ 完了: {len(articles)}本")
    else:
        print("⚠️ 全記事の生成に失敗", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
