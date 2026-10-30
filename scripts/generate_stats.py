"""Refresh a GitHub profile using public, authored pull requests only (stdlib)."""

import json
import os
from collections import Counter
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

USER = "Yzzz88"
ROOT = Path(__file__).resolve().parents[1]
CST = timezone(timedelta(hours=8))


def api(path, params=None):
    url = "https://api.github.com/" + path
    if params:
        url += "?" + urlencode(params)
    headers = {"Accept": "application/vnd.github+json", "User-Agent": USER + "-profile"}
    if os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    with urlopen(Request(url, headers=headers), timeout=30) as response:
        return json.load(response)


def collect():
    pulls = []
    for page in range(1, 11):
        result = api("search/issues", {
            "q": f"is:pr is:public author:{USER}", "per_page": 100,
            "page": page, "sort": "created", "order": "desc",
        })
        if result.get("incomplete_results") or result["total_count"] > 1000:
            raise RuntimeError("GitHub returned incomplete search results; keep the previous snapshot.")
        pulls.extend(result["items"])
        if len(pulls) >= result["total_count"]:
            break
    pulls = [p for p in pulls if p["repository_url"].split("/")[-2].lower() != USER.lower()]
    repos = {}
    for pull in pulls:
        repo = pull["repository_url"].split("/repos/")[1]
        if repo not in repos:
            info = api("repos/" + repo)
            repos[repo] = {"stars": info["stargazers_count"], "url": info["html_url"]}
    return {"updated_at": datetime.now(CST).isoformat(), "pulls": pulls, "repos": repos}


def svg_start(height, label, width=1000):
    return [f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{escape(label, quote=True)}">
<style>
text {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Microsoft YaHei', sans-serif; fill: #19191e; }}
.mono {{ font-family: Consolas, 'Liberation Mono', monospace; }}
.eyebrow {{ font-size: 12px; font-weight: 600; letter-spacing: 2.3px; fill: #8061bb; }}
.muted {{ fill: #85838c; font-size: 13px; }}
.line {{ stroke: #eeedf2; stroke-width: 1; }}
</style><rect width="{width}" height="{height}" rx="0" fill="#fff"/>''']


def txt(x, y, content, attrs=""):
    return f'<text x="{x}" y="{y}" {attrs}>{escape(str(content))}</text>'


def star_count(count):
    return f"{count / 1000:.1f}k" if count >= 1000 else str(count)


def public_data(data):
    # Ignore API metadata, search ordering and the check timestamp.
    return {"repos": data["repos"], "pulls": [
        {key: p[key] for key in ("number", "title", "html_url", "repository_url", "state", "pull_request")}
        for p in sorted(data["pulls"], key=lambda p: p["html_url"])
    ]}


def refresh():
    data = collect()
    snapshot_path = ROOT / "data" / "stats.json"
    if snapshot_path.exists():
        previous = json.loads(snapshot_path.read_text(encoding="utf-8"))
        if public_data(previous) == public_data(data):
            print("No public data changes; keeping files and update timestamp unchanged.")
            return False
    render(data)
    print("Public data changed; profile updated.")
    return True


def render(data):
    pulls, repos = data["pulls"], data["repos"]
    merged = [p for p in pulls if p["pull_request"].get("merged_at")]
    opened = [p for p in pulls if p["state"] == "open"]
    now = datetime.fromisoformat(data["updated_at"]).astimezone(CST)
    recent = sum(datetime.fromisoformat(p["pull_request"]["merged_at"].replace("Z", "+00:00")) >= now - timedelta(days=30) for p in merged)
    counts = Counter(p["repository_url"].split("/repos/")[1] for p in merged)
    pending = Counter(p["repository_url"].split("/repos/")[1] for p in opened)
    ordered = sorted(repos, key=lambda r: (-counts[r], -pending[r], -repos[r]["stars"], r))
    assets = ROOT / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    hero = svg_start(226, f"{USER} — AI Agent 与开源贡献")
    hero += [txt(40, 43, "■ AI AGENT · OPEN SOURCE", 'class="eyebrow"'),
             txt(40, 112, USER, 'font-size="53" font-weight="700" letter-spacing="-2"'),
             txt(40, 157, "关注 Agent 工具调用、执行可靠性与沙箱边界。", 'font-size="18" fill="#65616f"'),
             txt(40, 190, "通过问题复现、回归测试与代码修复参与开源。", 'class="muted"'), "</svg>"]
    (assets / "hero.svg").write_text("\n".join(hero), encoding="utf-8")
    hero_mobile = svg_start(196, f"{USER} — AI Agent 与开源贡献", width=320)
    hero_mobile += [txt(12, 26, "■ AI AGENT · OPEN SOURCE", 'class="eyebrow" style="font-size:10px;letter-spacing:1.2px"'),
                    txt(12, 79, USER, 'font-size="38" font-weight="700" letter-spacing="-1"'),
                    txt(12, 118, "关注 Agent 工具调用、", 'font-size="19"'),
                    txt(12, 147, "执行可靠性与沙箱边界。", 'font-size="19"'),
                    txt(12, 181, "问题复现 · 回归测试 · 代码修复", 'class="muted" style="font-size:16px"'), "</svg>"]
    (assets / "hero-mobile.svg").write_text("\n".join(hero_mobile), encoding="utf-8")

    height = 388 + len(ordered) * 67 + 72
    svg = svg_start(height, f"{len(merged)} 个 PR 已合并，{len(opened)} 个 PR 待合并，涉及 {len(repos)} 个上游仓库")
    svg += [txt(40, 34, "■ MERGED PULL REQUESTS", 'class="eyebrow"'),
            txt(960, 34, "github.com/" + USER, 'class="muted mono" text-anchor="end"'),
            '<path d="M40 56H960" class="line"/>',
            txt(40, 148, len(merged), 'font-size="76" font-weight="700" letter-spacing="-3"'),
            txt(145, 142, "个 PR 已合并", 'font-size="23" font-weight="600"'),
            txt(40, 182, f"近 30 天 +{recent} · 投向他人的公开仓库", 'class="muted"'),
            txt(694, 135, len(opened), 'font-size="33" font-weight="600"'),
            txt(694, 164, "待合并 PR", 'class="muted"'),
            txt(865, 135, len(repos), 'font-size="33" font-weight="600"'),
            txt(865, 164, "上游仓库", 'class="muted"'),
            txt(40, 224, "最近 90 天 · 合并时间线", 'class="muted"'),
            '<path d="M46 293H954" class="line"/>']
    first = now.date() - timedelta(days=89)
    days = Counter(datetime.fromisoformat(p["pull_request"]["merged_at"].replace("Z", "+00:00")).astimezone(CST).date() for p in merged)
    for day, count in sorted(days.items()):
        if first <= day <= now.date():
            x = 46 + (day - first).days / 89 * 908
            # One dot per merged PR, with a count for days above six merges.
            for level in range(min(count, 6)):
                svg.append(f'<circle cx="{x:.1f}" cy="{282 - level * 9}" r="3.8" fill="#8663bf"/>')
            if count > 6:
                svg.append(txt(f"{x:.1f}", 217, count, 'class="muted" text-anchor="middle"'))
    svg += [txt(40, 318, first.strftime("%m-%d"), 'class="muted mono"'),
            txt(960, 318, now.strftime("%m-%d"), 'class="muted mono" text-anchor="end"'),
            txt(40, 365, "上游仓库", 'class="muted"'),
            txt(688, 365, "已合并", 'class="muted" text-anchor="end"'),
            txt(806, 365, "待合并", 'class="muted" text-anchor="end"'),
            txt(960, 365, "STARS", 'class="muted mono" text-anchor="end"')]
    for index, repo in enumerate(ordered):
        y = 388 + index * 67
        svg += [f'<path d="M40 {y}H960" class="line"/>',
                f'<rect x="40" y="{y + 23}" width="24" height="24" rx="5" fill="#f2eef9"/>',
                txt(52, y + 40, repo.split("/")[1][0].upper(), 'font-size="14" font-weight="700" text-anchor="middle" style="fill:#8061bb"'),
                txt(80, y + 40, repo, 'class="mono" font-size="16" font-weight="600"'),
                txt(688, y + 40, counts[repo], 'font-size="17" font-weight="600" text-anchor="end"'),
                txt(806, y + 40, pending[repo], 'font-size="17" text-anchor="end" style="fill:#8061bb"'),
                txt(960, y + 40, "☆ " + star_count(repos[repo]["stars"]), 'class="muted mono" text-anchor="end"')]
    footer = 388 + len(ordered) * 67
    svg += [f'<path d="M40 {footer}H960" class="line"/>',
            txt(40, footer + 38, "GitHub REST API · 每小时检查 · 变化时更新", 'class="muted"'),
            txt(960, footer + 38, now.strftime("%Y-%m-%d %H:%M") + " (UTC+8)", 'class="muted mono" text-anchor="end"'), "</svg>"]
    (assets / "contributions.svg").write_text("\n".join(svg), encoding="utf-8")

    mobile_footer = 370 + len(ordered) * 112
    mobile = svg_start(mobile_footer + 90, f"{len(merged)} 个 PR 已合并，{len(opened)} 个 PR 待合并，涉及 {len(repos)} 个上游仓库", width=320)
    mobile += [txt(12, 30, "■ 开源贡献统计", 'font-size="19" font-weight="600" style="fill:#8061bb"'),
               '<path d="M12 48H308" class="line"/>',
               txt(12, 116, len(merged), 'font-size="60" font-weight="700"'),
               txt(84, 108, "个 PR 已合并", 'font-size="23" font-weight="600"'),
               txt(12, 160, len(opened), 'font-size="28" font-weight="600"'),
               txt(44, 158, "待合并 PR", 'font-size="18"'),
               txt(175, 160, len(repos), 'font-size="28" font-weight="600"'),
               txt(207, 158, "上游仓库", 'font-size="18"'),
               txt(12, 196, f"近 30 天 +{recent} 个已合并 PR", 'class="muted" style="font-size:17px"'),
               txt(12, 234, "最近 90 天 · 合并时间线", 'font-size="17"'),
               '<path d="M18 296H302" class="line"/>']
    for day, count in sorted(days.items()):
        if first <= day <= now.date():
            x = 18 + (day - first).days / 89 * 284
            for level in range(min(count, 5)):
                mobile.append(f'<circle cx="{x:.1f}" cy="{286 - level * 8}" r="3.5" fill="#8663bf"/>')
            if count > 5:
                mobile.append(txt(f"{x:.1f}", 242, count, 'font-size="14" text-anchor="middle"'))
    mobile += [txt(12, 321, first.strftime("%m-%d"), 'class="muted mono" style="font-size:15px"'),
               txt(308, 321, now.strftime("%m-%d"), 'class="muted mono" text-anchor="end" style="font-size:15px"'),
               txt(12, 356, "上游仓库", 'font-size="20" font-weight="600"')]
    for index, repo in enumerate(ordered):
        y = 370 + index * 112
        owner, name = repo.split("/", 1)
        mobile += [f'<rect x="12" y="{y}" width="296" height="100" rx="8" fill="#faf9fc" stroke="#eeedf2"/>',
                   txt(24, y + 23, owner, 'class="muted mono" style="font-size:16px"'),
                   txt(24, y + 52, name, 'class="mono" font-size="19" font-weight="600"'),
                   txt(24, y + 82, f"已合并 {counts[repo]} · 待合并 {pending[repo]}", 'font-size="16"'),
                   txt(296, y + 82, "☆ " + star_count(repos[repo]["stars"]), 'class="mono" font-size="16" text-anchor="end" style="fill:#8061bb"')]
    mobile += [txt(12, mobile_footer + 28, "每小时检查 · 变化时更新", 'class="muted" style="font-size:17px"'),
               txt(12, mobile_footer + 59, now.strftime("%Y-%m-%d %H:%M") + " (UTC+8)", 'class="muted mono" style="font-size:15px"'), "</svg>"]
    (assets / "contributions-mobile.svg").write_text("\n".join(mobile), encoding="utf-8")
    lines = ["<!-- Generated by scripts/generate_stats.py. Public GitHub data only. -->",
             '<picture>',
             '  <source media="(max-width: 600px)" srcset="assets/hero-mobile.svg">',
             f'  <img src="assets/hero.svg" alt="{USER} · AI Agent 与开源贡献" width="100%">',
             '</picture>', "",
             f'<a href="https://github.com/search?q=is%3Apr+is%3Amerged+author%3A{USER}&amp;type=pullrequests">',
             '<picture>',
             '  <source media="(max-width: 600px)" srcset="assets/contributions-mobile.svg">',
             f'  <img src="assets/contributions.svg" alt="已合并 {len(merged)} 个 PR · 待合并 {len(opened)} 个 PR" width="100%">',
             '</picture>', '</a>',
             "", "### 开源贡献", "", "待合并 PR 尚未被上游合并；状态与链接随公开数据更新。", ""]
    descriptions = {
        "https://github.com/opensandbox-group/OpenSandbox/pull/2474": "修复服务端主机路径白名单对 POSIX 根路径的判断",
        "https://github.com/opensandbox-group/OpenSandbox/pull/2483": "修复 Python SDK 空闲池重插入后的 FIFO 顺序",
        "https://github.com/bytedance/deer-flow/pull/7715": "防止数据分析导出文件覆盖输入文件",
        "https://github.com/modelscope/ms-agent/pull/1036": "异步淘汰会话后重新检查准入条件",
        "https://github.com/agentscope-ai/agentscope/pull/3593": "尝试次数耗尽时先收束状态，再发出步骤结束事件",
        "https://github.com/langgenius/dify-official-plugins/pull/4150": "按匹配索引删除 JSON 数组元素",
    }
    for p in sorted(pulls, key=lambda p: (not bool(p["pull_request"].get("merged_at")), p["html_url"])):
        repo = p["repository_url"].split("/repos/")[1]
        status = "已合并" if p["pull_request"].get("merged_at") else ("待合并" if p["state"] == "open" else "已关闭，未合并")
        title = escape(descriptions.get(p["html_url"], p["title"])).replace("\n", " ")
        lines += [f"#### {status} · [{repo.split('/')[-1]} #{p['number']}]({p['html_url']})", "",
                  title, "", f"仓库：[{repo}](https://github.com/{repo})", ""]
    lines += ["", "<sub>统计范围：本人提交至他人公开仓库的 Pull Request；已合并与待合并分别计数。Star 数随上游变化。</sub>", ""]
    (ROOT / "README.md").write_text("\n".join(lines), encoding="utf-8")
    (ROOT / "data").mkdir(exist_ok=True)
    # Store only the public fields required for the profile, not the full API response.
    snapshot = {"updated_at": data["updated_at"], **public_data(data)}
    (ROOT / "data" / "stats.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    refresh()
