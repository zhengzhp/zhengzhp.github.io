#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DualMind 博客文章发布脚本（方案 B：直接维护 Hexo 构建产物）

背景：zhengzhp.github.io 仓库里只有 Hexo 的构建产物，没有源码工程。
本脚本用「模板 + 元数据」的方式，把新文章发布到这个静态站点里，
并同步更新所有需要联动生成的页面：

  1. 文章页       2026/10/06/<slug>/index.html
  2. 首页列表     index.html（第 1 页，per_page = 5）
  3. 分页列表     page/2/index.html
  4. 归档总览     archives/index.html
  5. 年月归档     archives/YYYY/index.html、archives/YYYY/MM/index.html
  6. 标签页       tags/<tag>/index.html
  7. 搜索索引     content.json
  8. 上下篇导航   每篇文章页的 <nav id="article-nav">

脚本内部带有「字节级自检」：会用模板重新渲染已有文章的卡片/标签列表，
并与仓库中的原文逐字节比对，任何不一致都会直接报错退出，
避免模板漂移导致悄悄改坏站点。

用法：
    python3 tools/build_posts.py

新增文章：
    1. 在 tools/content/<slug>.body.html 写正文（HTML 片段，
       用 <a id="more"></a> 标记「摘要结束」的位置）
    2. 在下方 POSTS 列表里加一条记录（new=True, body_file=...）
    3. 重新运行本脚本
"""

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = 'https://zhengzhp.github.io'
PER_PAGE = 5          # 与 Hexo 的 per_page 一致
NEW_AUTHOR_YEAR = 2026

# 模板文章页：取一篇「引用 main.74f4aa、favicon.jpg 已修正」的文章作为骨架
SKELETON = '2019/01/06/call-apply/index.html'
# 归档页骨架（年月归档用同一套模板）
ARCHIVE_SKELETON = 'archives/2019/01/index.html'

# 标签配色（沿用 yilia 主题原本的 colorN 分配）
TAG_COLOR = {
    'js': '3', 'mongodb': '3', '面试': '3',
    'nodejs': '2',
    'react': '1',
    'css': '4', '位运算': '4',
    '一些问题': '5',
}


# --------------------------------------------------------------------------
# 文章元数据（按日期倒序，最新的在最前面）
# --------------------------------------------------------------------------
POSTS = [
    dict(
        slug='dualmind-architecture',
        title='DualMind 架构设计与技术选型：给 MV3 浏览器扩展划清边界',
        path='2026/10/06/dualmind-architecture/',
        iso='2026-10-06T06:40:00.000Z',
        ymd='2026-10-06',
        tags=['js', 'react'],
        new=True,
        body_file='tools/content/dualmind-architecture.body.html',
    ),
    dict(
        slug='dualmind-pitfalls',
        title='DualMind 踩坑实录：沉浸式翻译、手势窗口与那些「看起来像玄学」的 bug',
        path='2026/10/06/dualmind-pitfalls/',
        iso='2026-10-06T06:20:00.000Z',
        ymd='2026-10-06',
        tags=['js'],
        new=True,
        body_file='tools/content/dualmind-pitfalls.body.html',
    ),
    dict(
        slug='call-apply',
        title='关于call、apply、bind的一些理解',
        path='2019/01/06/call-apply/',
        iso='2019-01-06T10:21:35.000Z', ymd='2019-01-06',
        tags=['js'], new=False,
    ),
    dict(
        slug='mongoose-date',
        title='mongoose存储时间的问题',
        path='2018/10/02/mongoose-date/',
        iso='2018-10-02T15:11:25.000Z', ymd='2018-10-02',
        tags=['mongodb', 'nodejs'], new=False,
    ),
    dict(
        slug='some-problems',
        title='一些问题',
        path='2018/09/23/some-problems/',
        iso='2018-09-23T13:46:02.000Z', ymd='2018-09-23',
        tags=['一些问题'], new=False,
    ),
    dict(
        slug='interview-questions-2',
        title='前端面试题js,react篇',
        path='2018/04/22/interview-questions-2/',
        iso='2018-04-21T20:32:55.000Z', ymd='2018-04-22',
        tags=['js', '面试', 'react'], new=False,
    ),
    dict(
        slug='interview-questions-1',
        title='前端面试题css,html篇',
        path='2018/04/20/interview-questions-1/',
        iso='2018-04-20T11:15:43.000Z', ymd='2018-04-20',
        tags=['面试', 'css'], new=False,
    ),
    dict(
        slug='check2power',
        title='判断一个数字是2的几次方幂',
        path='2018/03/15/check2power/',
        iso='2018-03-15T10:02:01.000Z', ymd='2018-03-15',
        tags=['位运算', 'js'], new=False,
    ),
    dict(
        slug='bit-operation',
        title='位运算1',
        path='2018/03/14/bit-operation/',
        iso='2018-03-14T10:36:21.000Z', ymd='2018-03-14',
        tags=['位运算', 'js'], new=False,
    ),
    dict(
        slug='preface',
        title='序言',
        path='2017/07/10/preface/',
        iso='2017-07-10T12:39:38.000Z', ymd='2017-07-10',
        tags=[], new=False,
    ),
]

for p in POSTS:
    p['url'] = '/' + p['path']
    p['year'] = p['ymd'][:4]
    p['month'] = p['ymd'][5:7]


# --------------------------------------------------------------------------
# 基础工具
# --------------------------------------------------------------------------
def read(rel):
    with open(os.path.join(ROOT, rel), encoding='utf-8') as f:
        return f.read()


def write(rel, text):
    path = os.path.join(ROOT, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)


def h(text):
    """HTML 文本转义"""
    return (text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))


def attr(text):
    """HTML 属性转义"""
    return h(text).replace('"', '&quot;')


def strip_tags(html):
    """去掉标签得到纯文本，并压缩空白（用于生成 description）"""
    text = re.sub(r'<[^>]+>', '', html)
    text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    text = text.replace('&quot;', '"').replace('&#39;', "'")
    return re.sub(r'\s+', ' ', text).strip()


def build_description(excerpt_html, limit=120):
    text = strip_tags(excerpt_html)
    return text if len(text) <= limit else text[:limit]


def fail(msg):
    print('[FAIL] ' + msg, file=sys.stderr)
    sys.exit(1)


# --------------------------------------------------------------------------
# 标签列表模板（字节级还原 yilia 的 tagcloud 片段）
# --------------------------------------------------------------------------
TAG_PREFIX = '\n\t\t\t \n        \t\t'
TAG_JOINER = '\n      \t\t \n        \t\t'
TAG_SUFFIX = '\n      \t\t\n\t\t'
TAG_UNIT = ('<li class="article-tag-list-item">\n'
            '        \t\t\t<a href="javascript:void(0)" '
            'class="js-tag article-tag-list-link color{color}">{name}</a>\n'
            '        \t\t</li>')


def tags_inner(tags):
    if not tags:
        return TAG_PREFIX + TAG_SUFFIX
    units = [TAG_UNIT.format(color=TAG_COLOR.get(t, '3'), name=h(t)) for t in tags]
    return TAG_PREFIX + TAG_JOINER.join(units) + TAG_SUFFIX


def tag_ul(tags):
    return ('<ul class="article-tag-list">' + tags_inner(tags) + '</ul>')


# --------------------------------------------------------------------------
# 归档/标签页共用的「归档卡片」模板
# --------------------------------------------------------------------------
ARCHIVE_CARD = (
    '<article class="archive-article archive-type-post">\n'
    '  <div class="archive-article-inner">\n'
    '    <header class="archive-article-header">\n'
    '      \t<div class="article-meta">\n'
    '\t      \t<a href="{url}" class="archive-article-date">\n'
    '  \t<time datetime="{iso}" itemprop="datePublished">'
    '<i class="icon-calendar icon"></i>{ymd}</time>\n'
    '</a>\n'
    '        </div>\n'
    '    \t \n'
    '  \n'
    '    <h1 itemprop="name">\n'
    '      <a class="archive-article-title" href="{url}">{title}</a>\n'
    '    </h1>\n'
    '  \n'
    '\n'
    '        <div class="article-info info-on-right">\n'
    '          \n'
    '\t<div class="article-tag tagcloud">\n'
    '\t\t<i class="icon-price-tags icon"></i>\n'
    '\t\t{tag_ul}\n'
    '\t</div>\n'
    '\n'
    '          \n'
    '\n'
    '        </div>\n'
    '        <div class="clearfix"></div>\n'
    '    </header>\n'
    '  </div>\n'
    '</article>'
)


def archive_card(post):
    return ARCHIVE_CARD.format(
        url=post['url'], iso=post['iso'], ymd=post['ymd'],
        title=h(post['title']), tag_ul=tag_ul(post['tags']),
    )


# --------------------------------------------------------------------------
# 归档区段模板（从 archives/index.html 的 2018 区段提取，支持多卡片）
# --------------------------------------------------------------------------
ARCHIVE_SEC_HEAD = (
    '\n      <section class="archives-wrap">\n'
    '        <div class="archive-year-wrap">\n'
    '          <a href="/archives/{year}" class="archive-year">{year}</a>\n'
    '        </div>\n'
    '        <div class="archives">\n'
    '    \n'
    '    '
)
ARCHIVE_CARD_SEP = '\n  \n    \n    \n    '
ARCHIVE_SEC_TAIL = '\n  \n    \n    \n      \n        </div></section>\n'


def archive_section(year, posts, indent):
    """生成一个「按年分组」的归档区段（含若干张归档卡片）"""
    head = ARCHIVE_SEC_HEAD.format(year=year).replace('\n      ', '\n' + indent, 1)
    body = ARCHIVE_CARD_SEP.join(archive_card(p) for p in posts)
    return head + body + ARCHIVE_SEC_TAIL


# --------------------------------------------------------------------------
# 首页卡片模板
# --------------------------------------------------------------------------
INDEX_CARD = (
    '<article id="post-{slug}" class="article article-type-post  article-index" '
    'itemscope itemprop="blogPost">\n'
    '  <div class="article-inner">\n'
    '    \n'
    '      <header class="article-header">\n'
    '        \n'
    '  \n'
    '    <h1 itemprop="name">\n'
    '      <a class="article-title" href="{url}">{title}</a>\n'
    '    </h1>\n'
    '  \n'
    '\n'
    '        \n'
    '        <a href="{url}" class="archive-article-date">\n'
    '  \t<time datetime="{iso}" itemprop="datePublished">'
    '<i class="icon-calendar icon"></i>{ymd}</time>\n'
    '</a>\n'
    '        \n'
    '      </header>\n'
    '    \n'
    '    <div class="article-entry" itemprop="articleBody">\n'
    '      \n'
    '        {excerpt}\n'
    '        \n'
    '          <a class="article-more-a" href="{url}#more">more &gt;&gt;</a>\n'
    '        \n'
    '      \n'
    '\n'
    '      \n'
    '    </div>\n'
    '    <div class="article-info article-info-index">\n'
    '      \n'
    '      \n'
    '\t<div class="article-tag tagcloud">\n'
    '\t\t<i class="icon-price-tags icon"></i>\n'
    '\t\t{tag_ul}\n'
    '\t</div>\n'
    '\n'
    '      \n'
    '\n'
    '      \n'
    '        <p class="article-more-link">\n'
    '          <a class="article-more-a" href="{url}">展开全文 &gt;&gt;</a>\n'
    '        </p>\n'
    '      \n'
    '\n'
    '      \n'
    '      <div class="clearfix"></div>\n'
    '    </div>\n'
    '  </div>\n'
    '</article>'
)


# --------------------------------------------------------------------------
# 上下篇导航模板
# --------------------------------------------------------------------------
def nav_block(newer, older):
    out = '<nav id="article-nav">\n  \n'
    if newer:
        out += ('    <a href="{url}" id="article-nav-newer" class="article-nav-link-wrap">\n'
                '      <i class="icon-circle-left"></i>\n'
                '      <div class="article-nav-title">\n'
                '        \n'
                '          {title}\n'
                '        \n'
                '      </div>\n'
                '    </a>\n'
                '  \n').format(url=newer['url'], title=h(newer['title']))
    out += '  \n'
    if older:
        out += ('    <a href="{url}" id="article-nav-older" class="article-nav-link-wrap">\n'
                '      <div class="article-nav-title">{title}</div>\n'
                '      <i class="icon-circle-right"></i>\n'
                '    </a>\n'
                '  \n').format(url=older['url'], title=h(older['title']))
    out += '</nav>'
    return out


# --------------------------------------------------------------------------
# 自检：用模板重新渲染已有文章，与仓库原文逐字节比对
# --------------------------------------------------------------------------
def self_check():
    print('— 模板字节级自检 —')
    archives = read('archives/index.html')
    for slug in ('call-apply', 'mongoose-date', 'interview-questions-2'):
        post = next(p for p in POSTS if p['slug'] == slug)
        originals = re.findall(
            r'<article class="archive-article archive-type-post">.*?</article>', archives, re.S)
        target = archive_card(post)
        if target not in archives or target not in originals:
            fail(f'归档卡片模板与原文不一致：{slug}')
        print(f'  ✓ 归档卡片 {slug}')
    # 标签列表片段自检
    if tag_ul(['mongodb', 'nodejs']) not in archives:
        fail('标签列表模板与原文不一致')
    print('  ✓ 标签列表片段')
    # 文章页骨架自检
    skel = read(SKELETON)
    for anchor in ('<div class="article-entry" itemprop="articleBody">',
                   '<div class="article-info article-info-index">',
                   '<nav id="article-nav">',
                   '<meta name="keywords" content="js">'):
        if anchor not in skel:
            fail(f'骨架缺少锚点：{anchor}')
    print('  ✓ 文章页骨架锚点')
    print()


# --------------------------------------------------------------------------
# 生成文章页
# --------------------------------------------------------------------------
def render_article(post):
    html = read(SKELETON)
    old_title = '关于call、apply、bind的一些理解'
    body = read(post['body_file'])
    marker = '<a id="more"></a>'
    if marker not in body:
        fail(f'{post["body_file"]} 缺少 {marker} 标记')
    excerpt_html = body.split(marker)[0].rstrip('\n')
    desc = build_description(excerpt_html)
    keywords = ','.join(post['tags'])

    # --- head ---
    html = html.replace(
        f'<title>{old_title} | Zheng&#39;s Blog</title>',
        f'<title>{h(post["title"])} | Zheng&#39;s Blog</title>')
    html = re.sub(r'<meta name="description" content="[^"]*">',
                  f'<meta name="description" content="{attr(desc)}">', html, count=1)
    html = re.sub(r'<meta name="keywords" content="[^"]*">',
                  f'<meta name="keywords" content="{attr(keywords)}">', html, count=1)
    html = re.sub(r'<meta property="og:title" content="[^"]*">',
                  f'<meta property="og:title" content="{attr(post["title"])}">', html, count=1)
    html = re.sub(r'<meta property="og:url" content="[^"]*">',
                  f'<meta property="og:url" content="{SITE}/{post["path"]}index.html">', html, count=1)
    html = re.sub(r'<meta property="og:description" content="[^"]*">',
                  f'<meta property="og:description" content="{attr(desc)}">', html, count=1)
    html = re.sub(r'<meta property="og:updated_time" content="[^"]*">',
                  f'<meta property="og:updated_time" content="{post["iso"]}">', html, count=1)
    html = re.sub(r'<meta name="twitter:title" content="[^"]*">',
                  f'<meta name="twitter:title" content="{attr(post["title"])}">', html, count=1)
    html = re.sub(r'<meta name="twitter:description" content="[^"]*">',
                  f'<meta name="twitter:description" content="{attr(desc)}">', html, count=1)

    # --- article 容器 id ---
    html = html.replace('<article id="post-call-apply"', f'<article id="post-{post["slug"]}"', 1)

    # --- header（标题 + 日期）---
    old_header = (
        '    <h1 class="article-title" itemprop="name">\n'
        f'      {old_title}\n'
        '    </h1>\n'
        '  \n'
        '\n'
        '        \n'
        '        <a href="/2019/01/06/call-apply/" class="archive-article-date">\n'
        '  \t<time datetime="2019-01-06T10:21:35.000Z" itemprop="datePublished">'
        '<i class="icon-calendar icon"></i>2019-01-06</time>\n'
        '</a>'
    )
    if old_header not in html:
        fail('文章页 header 锚点未匹配')
    new_header = (
        '    <h1 class="article-title" itemprop="name">\n'
        f'      {h(post["title"])}\n'
        '    </h1>\n'
        '  \n'
        '\n'
        '        \n'
        f'        <a href="{post["url"]}" class="archive-article-date">\n'
        f'  \t<time datetime="{post["iso"]}" itemprop="datePublished">'
        f'<i class="icon-calendar icon"></i>{post["ymd"]}</time>\n'
        '</a>'
    )
    html = html.replace(old_header, new_header, 1)

    # --- 正文 ---
    start = html.index('<div class="article-entry" itemprop="articleBody">')
    end = html.index('<div class="article-info article-info-index">', start)
    seg = html[start:end]
    body_start = seg.index('>') + 1
    body_end = seg.rindex('    </div>\n')      # 正文容器的闭合
    html = html[:start] + seg[:body_start] + '\n' + body + '\n    ' + seg[body_end:] + html[end:]

    # --- 文章标签列表 ---
    ai_start = html.index('<div class="article-info article-info-index">')
    ai_end = html.index('<div class="share-btn', ai_start)
    seg = html[ai_start:ai_end]
    seg = re.sub(r'<ul class="article-tag-list">.*?</ul>', tag_ul(post['tags']), seg, count=1, flags=re.S)
    html = html[:ai_start] + seg + html[ai_end:]

    # --- 微信二维码 URL ---
    html = re.sub(r'qrcode\.php\?url=[^"]*',
                  f'qrcode.php?url={SITE}{post["url"]}', html, count=1)

    # --- 页脚年份 ---
    html = html.replace('&copy; 2019 ZhengZP', f'&copy; {NEW_AUTHOR_YEAR} ZhengZP', 1)

    write(os.path.join(post['path'], 'index.html'), html)


def update_all_navs():
    """按最新顺序重写每篇文章页的上下篇导航"""
    for i, post in enumerate(POSTS):
        rel = os.path.join(post['path'], 'index.html')
        html = read(rel)
        newer = POSTS[i - 1] if i > 0 else None
        older = POSTS[i + 1] if i + 1 < len(POSTS) else None
        i0 = html.index('<nav id="article-nav">')
        i1 = html.index('</nav>', i0) + len('</nav>')
        html = html[:i0] + nav_block(newer, older) + html[i1:]
        write(rel, html)


# --------------------------------------------------------------------------
# 列表页重建
# --------------------------------------------------------------------------
def extract_cards(html):
    """抽出首页式卡片，返回 slug -> 卡片 HTML"""
    cards = {}
    for m in re.finditer(
            r'<article id="post-([a-z0-9\-]+)" class="article article-type-post  article-index".*?</article>',
            html, re.S):
        cards[m.group(1)] = m.group(0)
    return cards


def reflow_list_page(rel, slugs, card_map):
    """把某个列表页的卡片区重排为给定的 slug 顺序，保留原有缩进与分隔符"""
    html = read(rel)
    open_mark = '<div id="js-content" class="content-ll">'
    nav_mark = '<nav id="page-nav">'
    start = html.index(open_mark) + len(open_mark)
    end = html.index(nav_mark, start)
    region = html[start:end]

    matches = list(re.finditer(
        r'<article id="post-([a-z0-9\-]+)" class="article article-type-post  article-index".*?</article>',
        region, re.S))
    if not matches:
        fail(f'{rel} 未找到任何卡片')
    prefix = region[:matches[0].start()]
    suffix = region[matches[-1].end():]
    sep = (region[matches[0].end():matches[1].start()]
           if len(matches) > 1 else '\n\n\n\n  \n    ')

    cards = [card_map[s] for s in slugs]
    new_region = prefix + sep.join(cards) + suffix
    write(rel, html[:start] + new_region + html[end:])


def render_index_card(post):
    body = read(post['body_file'])
    excerpt = body.split('<a id="more"></a>')[0].strip('\n')
    return INDEX_CARD.format(
        slug=post['slug'], url=post['url'], title=h(post['title']),
        iso=post['iso'], ymd=post['ymd'], excerpt=excerpt,
        tag_ul=tag_ul(post['tags']),
    )


def rebuild_lists():
    index_html = read('index.html')
    page2_html = read('page/2/index.html')
    card_map = extract_cards(index_html)
    card_map.update(extract_cards(page2_html))
    for post in POSTS:
        if post['new']:
            card_map[post['slug']] = render_index_card(post)
    missing = [p['slug'] for p in POSTS if p['slug'] not in card_map]
    if missing:
        fail(f'缺少卡片：{missing}')

    slugs = [p['slug'] for p in POSTS]
    reflow_list_page('index.html', slugs[:PER_PAGE], card_map)
    reflow_list_page('page/2/index.html', slugs[PER_PAGE:], card_map)
    print(f'首页列表：第 1 页 {len(slugs[:PER_PAGE])} 篇，第 2 页 {len(slugs[PER_PAGE:])} 篇')


# --------------------------------------------------------------------------
# 归档页
# --------------------------------------------------------------------------
def group_by_year(posts, indent):
    """把文章按年分组，返回若干 archives 区段 HTML"""
    years = []
    for p in posts:
        if not years or years[-1][0] != p['year']:
            years.append((p['year'], []))
        years[-1][1].append(p)
    return ''.join(archive_section(y, ps, indent) for y, ps in years)


ARCHIVE_TAIL = '          </div>\n        </div>\n      </div>\n      <footer id="footer">'


def archive_body_region(html):
    """定位归档/标签页的「列表区」边界，并保留原有的前缀缩进空白

    返回 (起始下标, 结束下标, 前缀空白)，其中前缀空白是 content-ll 到第一个
    <section> 之间的原始排版空白，重建时原样保留，避免破坏代码格式。
    """
    open_mark = '<div id="js-content" class="content-ll">'
    start = html.index(open_mark) + len(open_mark)
    end = html.index(ARCHIVE_TAIL, start)
    first_section = html.index('<section', start)
    prefix = html[start:first_section]
    return start, end, prefix


def remove_year_section(html, year):
    """移除归档总览里某个年份的区段（保证脚本可重复运行）"""
    m = re.search(r'\n      <section class="archives-wrap">\s*<div class="archive-year-wrap">\s*'
                  r'<a href="/archives/%s"' % year, html)
    if not m:
        return html
    end = html.index('</div></section>', m.start()) + len('</div></section>')
    return html[:m.start()] + html[end:]


def rebuild_archives():
    # 归档总览：先清掉旧的 2026 区段（幂等），再插到 2019 区段之前
    html = read('archives/index.html')
    html = remove_year_section(html, '2026')
    new_sec = archive_section('2026', [p for p in POSTS if p['year'] == '2026'], '      ')
    anchor = ('\n      <section class="archives-wrap">\n        <div class="archive-year-wrap">\n'
              '          <a href="/archives/2019"')
    if anchor not in html:
        fail('archives/index.html 找不到 2019 区段锚点')
    html = html.replace(anchor, new_sec + anchor, 1)
    write('archives/index.html', html)

    # 年月归档页：用 archives/2019/01 作为骨架
    skel = read(ARCHIVE_SKELETON)
    for year in sorted({p['year'] for p in POSTS if p['year'] == '2026'}):
        posts_y = [p for p in POSTS if p['year'] == year]
        months = sorted({p['month'] for p in posts_y})
        targets = [(f'archives/{year}/index.html', f'Archives: {year}', year, posts_y)]
        for mth in months:
            posts_m = [p for p in posts_y if p['month'] == mth]
            targets.append((f'archives/{year}/{mth}/index.html',
                            f'Archives: {year}/{int(mth)}', year, posts_m))
        for rel, title, yy, ps in targets:
            html = skel
            html = re.sub(r'<title>[^<]*</title>', f'<title>{title} | Zheng&#39;s Blog</title>', html, count=1)
            html = re.sub(r'<meta property="og:url" content="[^"]*">',
                          f'<meta property="og:url" content="{SITE}/{rel.replace("/index.html", "/")}index.html">',
                          html, count=1)
            html = html.replace('/archives/2019" class="archive-year">2019<',
                                f'/archives/{yy}" class="archive-year">{yy}<', 1)
            start, end, prefix = archive_body_region(html)
            html = html[:start] + prefix + group_by_year(ps, '      ') + html[end:]
            html = html.replace('&copy; 2019 ZhengZP', f'&copy; {NEW_AUTHOR_YEAR} ZhengZP')
            write(rel, html)
            print(f'  归档页 {rel}')


def rebuild_tag_pages():
    """重建受影响的标签页（原页面按年分组，这里按新顺序重建）"""
    for tag in ('js', 'react'):
        rel = f'tags/{tag}/index.html'
        html = read(rel)
        posts = [p for p in POSTS if tag in p['tags']]
        start, end, prefix = archive_body_region(html)
        html = html[:start] + prefix + group_by_year(posts, '      ') + html[end:]
        write(rel, html)
        print(f'  标签页 {rel}（{len(posts)} 篇）')


# --------------------------------------------------------------------------
# 搜索索引
# --------------------------------------------------------------------------
def rebuild_content_json():
    raw = read('content.json')
    data = json.loads(raw)
    pretty = '\n' in raw
    existing = {item['path'] for item in data}
    added = []
    for post in POSTS:
        if post['new'] and post['path'] not in existing:
            added.append({
                'title': post['title'],
                'date': post['iso'],
                'path': post['path'],
                'tags': [{
                    'name': t, 'slug': t,
                    'permalink': f'{SITE}/tags/{t}/',
                } for t in post['tags']],
            })
    data = added + data
    indent = 2 if pretty else None
    sep = (',', ': ') if pretty else (',', ':')
    text = json.dumps(data, ensure_ascii=False, indent=indent, separators=None if pretty else sep)
    write('content.json', text if pretty else text + '\n')
    print(f'搜索索引：新增 {len(added)} 条，共 {len(data)} 条')


# --------------------------------------------------------------------------
def main():
    print('=== 自检 ===')
    self_check()

    print('=== 生成文章页 ===')
    for post in POSTS:
        if post['new']:
            render_article(post)
            print(f'  {post["path"]}index.html')
    update_all_navs()
    print('  已重写全部文章页的上下篇导航')

    print('=== 重建列表页 ===')
    rebuild_lists()

    print('=== 重建归档页 ===')
    rebuild_archives()

    print('=== 重建标签页 ===')
    rebuild_tag_pages()

    print('=== 更新搜索索引 ===')
    rebuild_content_json()
    print('\n完成。')


if __name__ == '__main__':
    main()
