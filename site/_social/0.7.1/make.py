"""The 0.7.1 graphic: writes graphic.html and renders it to graphic.png (1080 x 1350), the post's hero and the
LinkedIn graphic (site/assets/doorplate-0-7-1.png). Every figure is in the constants below, with its source.

    uv venv /tmp/pw && uv pip install -p /tmp/pw/bin/python playwright
    /tmp/pw/bin/python make.py [path/to/chrome]
"""

import pathlib
import shutil
import sys

HERE = pathlib.Path(__file__).resolve().parent
ASSETS = HERE.parent.parent / "assets"

# Parser Score by release (95% interval), parser showdown releases appendix
# (address-parser-showdown runs/doorplate-releases/releases.md); usaddress and libpostal from the pinned run of 2026-11-16.
RELEASES = ["0.1.0", "0.2.0", "0.3.1", "0.4.1", "0.5.1", "0.6.2", "0.7.0", "0.7.1"]
SCORE = [87.3, 87.3, 87.6, 88.7, 89.4, 90.9, 91.8, 91.8]
USADDRESS, LIBPOSTAL = 84.7, 80.8
# Puerto Rico flagged share, 0.6.2 -> 0.7.0, pooled sample (issue #833).
PR_FLAG = (45.4, 38.2)
# Time per parse, pinned profile_loop, one alternating session (CHANGELOG 0.7.1): 0.6.2, 0.7.0, 0.7.1, microseconds.
US = (6.06, 6.39, 5.76)

INK, INK2, MUTED, RULE, SURFACE = "#0b0b0b", "#52514e", "#8a8984", "#e3e2de", "#ffffff"
BLUE, GREY = "#2a78d6", "#a9b8cc"
FONT = '"DejaVu Sans","Helvetica Neue",Arial,sans-serif'


def chart():
    w, h, xl, top, bot = 960, 430, 56, 20, 46
    lo, hi = 78.0, 94.0
    pw, ph = w - xl - 270, h - top - bot

    def x(i):
        return xl + 40 + pw * i / (len(RELEASES) - 1)

    def y(v):
        return top + ph * (hi - v) / (hi - lo)

    s = [f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">']
    for g in (80, 84, 88, 92):
        s.append(f'<line x1="{xl}" x2="{w}" y1="{y(g):.1f}" y2="{y(g):.1f}" stroke="{RULE}" stroke-width="1"/>')
        s.append(f'<text x="{xl - 10}" y="{y(g) + 7:.1f}" text-anchor="end" font-size="20" fill="{MUTED}">{g}</text>')
    for name, v in (("usaddress", USADDRESS), ("libpostal", LIBPOSTAL)):
        s.append(
            f'<line x1="{xl}" x2="{xl + pw + 60}" y1="{y(v):.1f}" y2="{y(v):.1f}" stroke="{GREY}" stroke-width="3" stroke-dasharray="8 6"/>'
        )
        s.append(
            f'<text x="{xl + pw + 70}" y="{y(v) + 7:.1f}" font-size="22" fill="{INK2}">{name} {v}</text>'
        )
    pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(SCORE))
    s.append(f'<polyline points="{pts}" fill="none" stroke="{BLUE}" stroke-width="4"/>')
    for i, (r, v) in enumerate(zip(RELEASES, SCORE)):
        last = i == len(RELEASES) - 1
        s.append(f'<circle cx="{x(i):.1f}" cy="{y(v):.1f}" r="{9 if last else 7}" fill="{BLUE}" stroke="{SURFACE}" stroke-width="2"/>')
        if i != 6:  # 0.7.0 and 0.7.1 are the same point: label once
            s.append(
                f'<text x="{x(i):.1f}" y="{y(v) - 18:.1f}" text-anchor="middle" font-size="23" font-weight="{800 if last else 700}" fill="{BLUE if last else INK}">{v}</text>'
            )
        s.append(
            f'<text x="{x(i):.1f}" y="{h - 14}" text-anchor="middle" font-size="21" font-weight="{800 if last else 400}" fill="{BLUE if last else INK2}">{r}</text>'
        )
    s.append("</svg>")
    return "\n".join(s)


def page():
    pr_drop = (1 - PR_FLAG[1] / PR_FLAG[0]) * 100
    less_070 = (1 - US[2] / US[1]) * 100
    less_062 = (1 - US[2] / US[0]) * 100
    css = f"""
  :root{{--ink:{INK};--ink2:{INK2};--doorplate:{BLUE}}}
  *{{box-sizing:border-box;margin:0;padding:0}}
  html,body{{background:{SURFACE}}}
  body{{width:1080px;height:1350px;font-family:{FONT};color:var(--ink);overflow:hidden;padding:48px 60px 44px;display:flex;flex-direction:column;gap:18px}}
  text{{font-family:{FONT}}}
  .top{{display:flex;align-items:center;gap:16px}}
  .brand{{font-size:40px;font-weight:700;letter-spacing:-.5px}}
  .pill{{font-size:28px;font-weight:700;color:var(--doorplate);border:3px solid var(--doorplate);border-radius:999px;padding:2px 16px}}
  h1{{font-size:64px;line-height:1.05;font-weight:800;letter-spacing:-2px}}
  h1 em{{font-style:normal;color:var(--doorplate)}}
  .sub{{font-size:32px;font-weight:700;color:var(--ink2);margin-top:-6px;line-height:1.2}}
  .chart h2{{font-size:32px;font-weight:700}}
  .chart .u{{font-size:24px;color:var(--ink2);margin:2px 0 6px}}
  .tiles{{display:flex;gap:18px}}
  .tile{{flex:1;border-top:4px solid var(--ink);padding-top:10px}}
  .tile .n{{font-size:56px;font-weight:800;letter-spacing:-2px;line-height:1}}
  .tile .l{{font-size:26px;font-weight:700;margin-top:6px}}
  .tile .s{{font-size:23px;color:var(--ink2);margin-top:4px;line-height:1.25}}
  .foot{{font-size:22px;line-height:1.3;color:var(--ink2);margin-top:auto}}
"""
    body = f"""  <div class="top"><div class="brand">doorplate</div><div class="pill">0.7.1</div></div>
  <h1>The first beta: <em>more accurate</em>, faster, and better in Puerto Rico</h1>
  <div class="sub">The API, command-line options and warning codes are now stable</div>
  <section class="chart"><h2>Parser Score, every release</h2>
    <div class="u">parser showdown: a hand-labeled golden set and four outside sets</div>
{chart()}
  </section>
  <section class="tiles">
    <div class="tile"><div class="n">{PR_FLAG[1]}%</div><div class="l">Puerto Rico rows flagged</div><div class="s">down from {PR_FLAG[0]}% in 0.6.2 ({pr_drop:.0f}% fewer)</div></div>
    <div class="tile"><div class="n">{US[2]} &micro;s</div><div class="l">per parse</div><div class="s">{less_070:.0f}% less than 0.7.0, {less_062:.0f}% less than 0.6.2</div></div>
    <div class="tile"><div class="n">0</div><div class="l">parse changes in 0.7.1</div><div class="s">same output as 0.7.0, byte for byte</div></div>
  </section>
  <div class="foot">Scores: the showdown&rsquo;s releases appendix (95% intervals overlap between neighbouring releases; 0.7.1 scores the same as 0.7.0). Puerto Rico: flagged share on a fixed sample of real rows, 0.6.2 vs 0.7.0, pooled over the sources (issue #833). Speed: one pinned CPU, one alternating session. doorplate&rsquo;s author built the showdown. doorplate parses and formats; it does not validate that an address exists.</div>"""
    return f'<!doctype html>\n<html lang="en"><head><meta charset="utf-8">\n<title>doorplate 0.7.1 (hero and LinkedIn graphic, 1080 x 1350)</title>\n<style>\n  /* Generated by make.py; edit the data there, not here. */{css}</style></head>\n<body>\n{body}\n</body></html>\n'


def main():
    from playwright.sync_api import sync_playwright

    chrome = (
        sys.argv[1]
        if len(sys.argv) > 1
        else str(pathlib.Path.home() / ".cache/ms-playwright/chromium-1243/chrome-linux64/chrome")
    )
    (HERE / "graphic.html").write_text(page())
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=chrome)
        pg = b.new_page(viewport={"width": 1080, "height": 1350}, device_scale_factor=1)
        pg.goto((HERE / "graphic.html").as_uri())
        print("content height", pg.evaluate("document.documentElement.scrollHeight"), "of 1350")
        pg.screenshot(path=str(HERE / "graphic.png"))
        b.close()
    shutil.copyfile(HERE / "graphic.png", ASSETS / "doorplate-0-7-1.png")


if __name__ == "__main__":
    main()
