"""
Redraws Latent Space's artwork: Kartik's avatar (docs/kartik.svg), the app icon
(docs/icon.svg + PNGs) and the Android launcher layers.
Needs:  pip install resvg-py        Run from the repository root:  python tools/make_art.py
"""
import math, os, random
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs")
random.seed(7)

# ── palette sampled from his photo ───────────────────────────────────────────
SKIN_HI, SKIN, SKIN_MID, SKIN_SH = "#F6CDB6", "#EDB59C", "#DE9F86", "#C48268"
HAIR_HI, HAIR, HAIR_DK = "#5B4741", "#2C2120", "#171112"
FRAME, FRAME_HI = "#56625D", "#8A9792"
SHIRT_HI, SHIRT, SHIRT_DK = "#2F5747", "#22443A", "#16302A"
TIP_ORANGE, TIP_WHITE = "#B9793F", "#EDEDE4"

def strands(n, x0, x1, y0, y1, flow, palette, length=(4.5, 8.0), width=1.15):
    """Short hair strokes for beard/moustache texture; `flow` gives each stroke's angle from its position."""
    out = []
    for _ in range(n):
        x, y = random.uniform(x0, x1), random.uniform(y0, y1)
        a = flow(x, y) + random.uniform(-0.35, 0.35)
        L = random.uniform(*length)
        c = random.choices(palette, weights=[w for _, w in palette] if isinstance(palette[0], tuple) else None)[0]
        col = c[0] if isinstance(c, tuple) else c
        out.append(f'<path d="M{x:.1f} {y:.1f}l{L*math.cos(a):.1f} {L*math.sin(a):.1f}" stroke="{col}" stroke-width="{width}" stroke-linecap="round"/>')
    return "".join(out)

BEARD_PAL = [("#0F0B0A", 48), ("#241B19", 34), ("#3B302D", 12), ("#6E635E", 4), ("#9A908A", 1.2)]
beard_flow = lambda x, y: math.pi / 2 + (x - 220) / 160.0          # strands fall downwards, fanning out from the chin
mous_flow = lambda x, y: math.pi / 2 + (x - 220) / 45.0           # moustache sweeps out to the sides

stars = "".join(f'<circle class="tw" style="animation-delay:{random.uniform(0,4):.1f}s" cx="{random.uniform(30,410):.0f}" cy="{random.uniform(30,410):.0f}" '
                f'r="{random.choice([0.7,1,1.2,1.6])}" fill="{random.choice(["#FFFFFF","#FFFFFF","#CFE8FF","#FFD9F4"])}"/>' for _ in range(46))

def network(cx, cy, flip=1):
    layers = [[(-34, -40), (-34, 0), (-34, 40)], [(0, -56), (0, -18), (0, 20), (0, 58)], [(34, -24), (34, 24)]]
    pts = [[(cx + flip * x, cy + y) for x, y in L] for L in layers]
    lines = "".join(f'<path d="M{a[0]:.0f} {a[1]:.0f}L{b[0]:.0f} {b[1]:.0f}" class="edge" style="animation-delay:{random.uniform(0,3):.1f}s"/>'
                    for i in range(len(pts) - 1) for a in pts[i] for b in pts[i + 1])
    nodes = "".join(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="3.6" fill="{c}" class="node" style="animation-delay:{random.uniform(0,3):.1f}s"/>'
                    for L, c in zip(pts, ["#22E4FF", "#FF7AD9", "#B6FF3B"]) for x, y in L)
    return f'<g opacity=".75">{lines}{nodes}</g>'

EQS = [("p(θ|D) ∝ p(D|θ)p(θ)", 30, 120, -28), ("softmax(QKᵀ/√d)V", 36, 336, 10), ("iħ∂ψ/∂t = Ĥψ", 318, 304, -6), ("E = mc²", 196, 44, 0),
       ("∇·E = ρ/ε₀", 330, 176, 14)]
eqs = "".join(f'<text x="{x}" y="{y}" transform="rotate({r} {x} {y})" class="eq" font-family="Menlo, Consolas, DejaVu Sans Mono, monospace" font-size="11" fill="#E9E3FF">{t}</text>'
              for t, x, y, r in EQS)

# beard and moustache outlines (shared by the fill, the texture clip and the soft edge)
BEARD = ("M141 204C140 240 148 276 168 304C186 328 204 342 220 342C236 342 254 328 272 304C292 276 300 240 299 204"
         "L291 206C292 228 288 246 276 256C266 263 256 265 250 263L249 270C243 281 232 288 220 288C208 288 197 281 191 270L190 263"
         "C184 265 174 263 164 256C152 246 148 228 149 206Z")
MOUS = ("M186 268C193 257 208 253 220 257C232 253 247 257 254 268C248 272 240 273 232 271C227 270 223 269 220 269"
        "C217 269 213 270 208 271C200 273 192 272 186 268Z")

avatar = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 440 440" role="img" aria-labelledby="t d">
<title id="t">Kartik Khurana</title>
<desc id="d">Illustrated 3D-style portrait of Kartik: thick tousled dark hair, very thick brows, big squarish grey-green glasses, a full dark beard with a few grey flecks, a gentle smile, and a bottle-green knit polo with orange-and-white tipped collar, in a deep-space nebula with a neural-network constellation, a ringed planet, a galaxy, floating equations and a glowing Gaussian-process plot.</desc>
<style>
.tw{{animation:tw 3.2s ease-in-out infinite}} @keyframes tw{{0%,100%{{opacity:.2}}50%{{opacity:1}}}}
.edge{{stroke:#9CC9FF;stroke-width:1;opacity:.45;stroke-dasharray:4 6;animation:flow 3s linear infinite}} @keyframes flow{{to{{stroke-dashoffset:-20}}}}
.node{{animation:pulse 2.4s ease-in-out infinite}} @keyframes pulse{{0%,100%{{opacity:.55}}50%{{opacity:1}}}}
.eq{{opacity:.55}}
.orbit{{transform-origin:220px 220px;animation:spin 40s linear infinite}} @keyframes spin{{to{{transform:rotate(360deg)}}}}
.ring{{animation:hue 14s linear infinite}} @keyframes hue{{to{{filter:hue-rotate(360deg)}}}}
.gp{{animation:bob 4.5s ease-in-out infinite}} @keyframes bob{{0%,100%{{transform:translateY(0)}}50%{{transform:translateY(-6px)}}}}
.eyes{{transform-box:fill-box;transform-origin:center;animation:blink 6s infinite}} @keyframes blink{{0%,94%,100%{{transform:scaleY(1)}}96.5%{{transform:scaleY(.1)}}}}
.head{{transform-origin:220px 360px;animation:tilt 8s ease-in-out infinite}} @keyframes tilt{{0%,100%{{transform:rotate(0)}}50%{{transform:rotate(1.4deg)}}}}
.sp{{animation:tw 2.6s ease-in-out infinite}}
@media (prefers-reduced-motion: reduce){{*{{animation:none!important}}}}
</style>
<defs>
  <radialGradient id="space" cx="50%" cy="40%" r="65%"><stop offset="0" stop-color="#33268A"/><stop offset=".5" stop-color="#1C1253"/><stop offset="1" stop-color="#0B0724"/></radialGradient>
  <radialGradient id="neb1" cx="22%" cy="30%" r="42%"><stop offset="0" stop-color="#FF4FD8" stop-opacity=".5"/><stop offset="1" stop-color="#FF4FD8" stop-opacity="0"/></radialGradient>
  <radialGradient id="neb2" cx="80%" cy="66%" r="46%"><stop offset="0" stop-color="#22E4FF" stop-opacity=".42"/><stop offset="1" stop-color="#22E4FF" stop-opacity="0"/></radialGradient>
  <radialGradient id="neb3" cx="70%" cy="18%" r="35%"><stop offset="0" stop-color="#FFB84F" stop-opacity=".35"/><stop offset="1" stop-color="#FFB84F" stop-opacity="0"/></radialGradient>
  <linearGradient id="rim" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#22E4FF"/><stop offset=".35" stop-color="#8B5CFF"/><stop offset=".7" stop-color="#FF4FD8"/><stop offset="1" stop-color="#FFC83D"/></linearGradient>
  <radialGradient id="skin" cx="42%" cy="32%" r="78%"><stop offset="0" stop-color="{SKIN_HI}"/><stop offset=".45" stop-color="{SKIN}"/><stop offset=".8" stop-color="{SKIN_MID}"/><stop offset="1" stop-color="{SKIN_SH}"/></radialGradient>
  <radialGradient id="ear" cx="40%" cy="40%" r="70%"><stop offset="0" stop-color="{SKIN}"/><stop offset="1" stop-color="{SKIN_SH}"/></radialGradient>
  <linearGradient id="hair" x1="0" y1="0" x2=".4" y2="1"><stop offset="0" stop-color="{HAIR_HI}"/><stop offset=".35" stop-color="{HAIR}"/><stop offset="1" stop-color="{HAIR_DK}"/></linearGradient>
  <linearGradient id="beard" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2E2321"/><stop offset="1" stop-color="#171111"/></linearGradient>
  <radialGradient id="iris" cx="45%" cy="38%" r="65%"><stop offset="0" stop-color="#6B4430"/><stop offset=".6" stop-color="#3A2318"/><stop offset="1" stop-color="#1B0F0A"/></radialGradient>
  <linearGradient id="shirt" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{SHIRT_HI}"/><stop offset=".55" stop-color="{SHIRT}"/><stop offset="1" stop-color="{SHIRT_DK}"/></linearGradient>
  <pattern id="knit" width="6" height="4" patternUnits="userSpaceOnUse"><rect width="6" height="4" fill="none"/><path d="M0 3.2H6" stroke="#FFFFFF" stroke-opacity=".07" stroke-width="1"/><path d="M3 0V4" stroke="#000000" stroke-opacity=".08" stroke-width=".8"/></pattern>
  <linearGradient id="lens" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#FFFFFF" stop-opacity=".22"/><stop offset=".5" stop-color="#DDF2FF" stop-opacity=".04"/><stop offset="1" stop-color="#FFFFFF" stop-opacity=".14"/></linearGradient>
  <clipPath id="hairClip"><path d="M118 214C110 150 126 56 220 50C318 56 332 150 324 214C312 180 296 160 280 150C262 141 242 137 222 137C200 137 180 141 164 150C148 162 132 186 118 214Z"/></clipPath>
  <clipPath id="beardClip"><path d="{BEARD}"/></clipPath>
  <clipPath id="mousClip"><path d="{MOUS}"/></clipPath>
  <clipPath id="eyeL"><path d="M168 213C173 204.5 190 203.5 196 212C190 218.5 175 219.5 168 213Z"/></clipPath>
  <clipPath id="eyeR"><path d="M272 213C267 204.5 250 203.5 244 212C250 218.5 265 219.5 272 213Z"/></clipPath>
  <filter id="soft" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="5" stdDeviation="5" flood-color="#05030F" flood-opacity=".55"/></filter>
  <filter id="blur2" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="2.2"/></filter>
  <filter id="blur1" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="1.1"/></filter>
  <filter id="glow" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="5"/></filter>
  <clipPath id="disc"><circle cx="220" cy="220" r="200"/></clipPath>
</defs>

<circle cx="220" cy="220" r="214" fill="none" stroke="url(#rim)" stroke-width="12" opacity=".7" filter="url(#glow)" class="ring"/>
<circle cx="220" cy="220" r="206" fill="none" stroke="url(#rim)" stroke-width="6" class="ring"/>
<circle cx="220" cy="220" r="200" fill="url(#space)"/>
<g clip-path="url(#disc)">
  <circle cx="220" cy="220" r="200" fill="url(#neb1)"/><circle cx="220" cy="220" r="200" fill="url(#neb2)"/><circle cx="220" cy="220" r="200" fill="url(#neb3)"/>
  {stars}
  <!-- spiral galaxy -->
  <g transform="translate(84 100) rotate(-25)" opacity=".85"><ellipse rx="26" ry="10" fill="#C9B8FF" opacity=".25" filter="url(#blur2)"/>
    <path d="M0 0C10-8 24-4 26 4M0 0C-10 8-24 4-26-4M0 0C6 6 18 8 22 4M0 0C-6-6-18-8-22-4" stroke="#E9DDFF" stroke-width="1.6" fill="none" opacity=".8"/><circle r="3.5" fill="#FFFFFF"/></g>
  {network(70, 236)}{network(370, 236, -1)}
  {eqs}
  <!-- a ringed planet on a slow orbit -->
  <g class="orbit"><g transform="translate(372 104)"><circle r="15" fill="#FF9F43"/><circle cx="-4" cy="-5" r="5" fill="#FFFFFF" opacity=".35"/>
    <ellipse rx="27" ry="7" fill="none" stroke="#FFE27A" stroke-width="3" transform="rotate(-20)"/></g></g>
  <circle cx="58" cy="300" r="7" fill="#D8D2E8"/><circle cx="56" cy="298" r="2" fill="#B8B0CC"/>

  <!-- bottle-green knit polo with tipped collar -->
  <g filter="url(#soft)">
    <path d="M56 440C60 392 96 364 146 352C170 346 184 341 193 336L220 372L247 336C256 341 270 346 294 352C344 364 380 392 384 440Z" fill="url(#shirt)"/>
    <path d="M56 440C60 392 96 364 146 352C170 346 184 341 193 336L220 372L247 336C256 341 270 346 294 352C344 364 380 392 384 440Z" fill="url(#knit)"/>
    <path d="M220 372V440" stroke="#14281F" stroke-width="16"/>
    <path d="M212 376V440M228 376V440" stroke="{TIP_ORANGE}" stroke-width="2.2"/><path d="M215 376V440M225 376V440" stroke="{TIP_WHITE}" stroke-width="1.3"/>
    <circle cx="220" cy="396" r="3.4" fill="#8C9893"/><circle cx="220" cy="422" r="3.4" fill="#8C9893"/>
    <path d="M193 334L162 349L184 386L214 365Z" fill="{SHIRT}" stroke="#10241C" stroke-width="1"/>
    <path d="M247 334L278 349L256 386L226 365Z" fill="{SHIRT}" stroke="#10241C" stroke-width="1"/>
    <path d="M165 351L185 383L211 365" fill="none" stroke="{TIP_ORANGE}" stroke-width="2.6" stroke-linejoin="round"/>
    <path d="M169 352L186 379L208 364" fill="none" stroke="{TIP_WHITE}" stroke-width="1.4" stroke-linejoin="round"/>
    <path d="M275 351L255 383L229 365" fill="none" stroke="{TIP_ORANGE}" stroke-width="2.6" stroke-linejoin="round"/>
    <path d="M271 352L254 379L232 364" fill="none" stroke="{TIP_WHITE}" stroke-width="1.4" stroke-linejoin="round"/>
  </g>
</g>

<g class="head" filter="url(#soft)">
  <!-- neck, ears, face -->
  <path d="M188 318C190 334 188 344 186 350H254C252 344 250 334 252 318Z" fill="#C88A6E"/>
  <path d="M142 212C130 206 125 222 127 236C129 250 135 258 144 256Z" fill="url(#ear)"/><path d="M138 220C134 228 135 240 140 246" stroke="#B57460" stroke-width="1.6" fill="none"/>
  <path d="M298 212C310 206 315 222 313 236C311 250 305 258 296 256Z" fill="url(#ear)"/><path d="M302 220C306 228 305 240 300 246" stroke="#B57460" stroke-width="1.6" fill="none"/>
  <path d="M140 208C140 150 176 120 220 120C264 120 300 150 300 208C300 262 286 300 262 320C250 330 236 336 220 336C204 336 190 330 178 320C154 300 140 262 140 208Z" fill="url(#skin)"/>
  <ellipse cx="214" cy="160" rx="34" ry="12" fill="#FFFFFF" opacity=".14" filter="url(#blur2)"/>
  <ellipse cx="172" cy="244" rx="16" ry="9" fill="#F0907E" opacity=".22" filter="url(#blur2)"/><ellipse cx="268" cy="244" rx="16" ry="9" fill="#F0907E" opacity=".22" filter="url(#blur2)"/>
  <!-- full beard: soft base, then strand texture, salt-and-pepper flecks -->
  <path d="{BEARD}" fill="url(#beard)" filter="url(#blur1)"/>
  <g clip-path="url(#beardClip)">{strands(1700, 138, 302, 200, 344, beard_flow, BEARD_PAL, length=(3.5, 6.5), width=1.0)}</g>
  <path d="M150 214C152 236 158 250 168 258M290 214C288 236 282 250 272 258" stroke="#3A2D2A" stroke-width="3" fill="none" opacity=".45" filter="url(#blur1)"/>
  <!-- lower lip and gentle smile -->
  <path d="M203 272C210 281 230 281 237 272C230 275 210 275 203 272Z" fill="#C98C80"/>
  <path d="M200 271Q220 277 240 271" stroke="#5E2E2A" stroke-width="1.8" fill="none" stroke-linecap="round"/>
  <ellipse cx="220" cy="277" rx="7" ry="1.6" fill="#FFFFFF" opacity=".25"/>
  <!-- moustache -->
  <path d="{MOUS}" fill="#1E1615"/>
  <g clip-path="url(#mousClip)">{strands(220, 184, 256, 252, 274, mous_flow, BEARD_PAL, length=(3.5, 6.0), width=1.05)}</g>
  <!-- broad nose with a rounded tip -->
  <path d="M226 214C228 226 230 236 233 244" stroke="#B9785E" stroke-width="3.4" fill="none" opacity=".3" stroke-linecap="round" filter="url(#blur2)"/>
  <ellipse cx="220" cy="246" rx="13" ry="9" fill="#E9A58A" opacity=".55"/>
  <ellipse cx="217" cy="242" rx="5" ry="3.4" fill="#FFFFFF" opacity=".32"/>
  <path d="M203 251C207 258 214 260 220 259C226 260 233 258 237 251" stroke="#9C5E48" stroke-width="2" fill="none" stroke-linecap="round"/>
  <ellipse cx="211" cy="253.5" rx="4" ry="2.2" fill="#7A4434" opacity=".45"/><ellipse cx="229" cy="253.5" rx="4" ry="2.2" fill="#7A4434" opacity=".45"/>
  <!-- eyes -->
  <g class="eyes">
    <path d="M168 213C173 204.5 190 203.5 196 212C190 218.5 175 219.5 168 213Z" fill="#FBF6F2"/>
    <path d="M272 213C267 204.5 250 203.5 244 212C250 218.5 265 219.5 272 213Z" fill="#FBF6F2"/>
    <g clip-path="url(#eyeL)"><circle cx="182.5" cy="211.5" r="6.3" fill="url(#iris)"/><circle cx="182.5" cy="211.5" r="2.9" fill="#0B0605"/></g>
    <g clip-path="url(#eyeR)"><circle cx="257.5" cy="211.5" r="6.3" fill="url(#iris)"/><circle cx="257.5" cy="211.5" r="2.9" fill="#0B0605"/></g>
    <circle cx="184.6" cy="209.3" r="1.9" fill="#FFFFFF"/><circle cx="259.6" cy="209.3" r="1.9" fill="#FFFFFF"/>
    <path d="M167 213C172 202.5 191 201.5 197 211.5M273 213C268 202.5 249 201.5 243 211.5" stroke="#1A100D" stroke-width="2.4" fill="none" stroke-linecap="round"/>
    <path d="M171 217C178 220.5 189 220 194 215.5M269 217C262 220.5 251 220 246 215.5" stroke="#B57A63" stroke-width="1.2" fill="none" opacity=".6" stroke-linecap="round"/>
  </g>
  <!-- very thick, straight brows -->
  <path d="M148 192C158 181 184 177 207 183C208 189 206 192 202 192C184 188 166 190 151 199Z" fill="#1E1615"/>
  <path d="M292 192C282 181 256 177 233 183C232 189 234 192 238 192C256 188 274 190 289 199Z" fill="#1E1615"/>
  <path d="M152 190C166 184 186 182 204 185M288 190C274 184 254 182 236 185" stroke="#4A3B36" stroke-width="1" fill="none" opacity=".7"/>
  <!-- big squarish grey-green glasses -->
  <path d="M139 206L128 211M301 206L312 211" stroke="{FRAME}" stroke-width="4.5" stroke-linecap="round"/>
  <rect x="138" y="194" width="70" height="53" rx="16" fill="url(#lens)" stroke="{FRAME}" stroke-width="5.2"/>
  <rect x="232" y="194" width="70" height="53" rx="16" fill="url(#lens)" stroke="{FRAME}" stroke-width="5.2"/>
  <path d="M208 206C214 200 226 200 232 206" stroke="{FRAME}" stroke-width="5" fill="none"/>
  <path d="M146 195.5H200M240 195.5H294" stroke="{FRAME}" stroke-width="3" stroke-linecap="round"/>
  <rect x="142" y="198" width="62" height="45" rx="13" fill="none" stroke="{FRAME_HI}" stroke-width="1" opacity=".5"/>
  <rect x="236" y="198" width="62" height="45" rx="13" fill="none" stroke="{FRAME_HI}" stroke-width="1" opacity=".5"/>
  <path d="M146 238L168 200M154 241L172 210M242 238L264 200M250 241L268 210" stroke="#FFFFFF" stroke-width="2" opacity=".22" stroke-linecap="round"/>
  <!-- thick, fluffy, tousled hair, swept up and to the side -->
  <g clip-path="url(#hairClip)">
    <path d="M137 200C130 158 140 118 170 96C192 80 226 74 256 80C290 88 312 118 306 160C305 178 303 190 302 200C298 184 291 170 281 160C270 148 254 141 236 138C214 135 196 137 181 144C164 152 152 168 146 186C143 192 140 196 137 200Z" fill="url(#hair)"/>
    <circle cx="160" cy="112" r="25" fill="url(#hair)"/><circle cx="188" cy="95" r="27" fill="url(#hair)"/><circle cx="221" cy="88" r="28" fill="url(#hair)"/>
    <circle cx="254" cy="92" r="27" fill="url(#hair)"/><circle cx="282" cy="105" r="25" fill="url(#hair)"/><circle cx="297" cy="124" r="15" fill="url(#hair)"/>
    <circle cx="152" cy="128" r="14" fill="url(#hair)"/>
    {strands(1100, 126, 318, 56, 158, lambda x, y: -math.pi / 2 + 0.55 + (x - 220) / 210.0, [("#55433D", 20), ("#33282A", 42), ("#191112", 38)], length=(6, 12), width=1.3)}
  </g>
  <path d="M170 112C184 96 204 88 224 88M232 82C250 78 270 84 284 96M154 132C160 120 170 110 182 104M258 104C274 104 290 114 298 128" stroke="#6A564F" stroke-width="2.2" fill="none" opacity=".55" stroke-linecap="round"/>
  <path d="M204 62C208 56 215 54 221 55M242 60C247 54 255 53 262 55M280 72C287 68 295 69 300 74M150 96C147 90 149 84 154 80M314 116C319 114 324 116 326 121M226 60C229 52 236 48 243 49" stroke="#241A19" stroke-width="1.6" fill="none" stroke-linecap="round"/>
  <path d="M190 142C204 136 222 134 240 137C252 139 262 143 270 148" stroke="#3A2C29" stroke-width="5" fill="none" opacity=".35" filter="url(#blur2)"/>
</g>

<!-- his Gaussian process, floating -->
<g class="gp"><g transform="translate(300 322)">
  <rect width="96" height="64" rx="12" fill="#FFFFFF" fill-opacity=".1" stroke="#22E4FF" stroke-opacity=".7" stroke-width="1.4"/>
  <path d="M8 40C20 22 30 18 42 26C54 34 62 46 74 38C82 33 86 26 90 22L90 34C86 40 80 50 72 54C60 60 52 48 42 42C32 36 22 40 8 54Z" fill="#22E4FF" opacity=".28"/>
  <path d="M8 47C20 31 30 28 42 34C54 41 62 54 74 46C82 41 86 33 90 28" stroke="#FFFFFF" stroke-width="1.8" fill="none"/>
  <circle cx="18" cy="38" r="2.4" fill="#FF7AD9"/><circle cx="34" cy="31" r="2.4" fill="#FF7AD9"/><circle cx="58" cy="47" r="2.4" fill="#FF7AD9"/><circle cx="80" cy="40" r="2.4" fill="#FF7AD9"/>
  <text x="8" y="14" font-family="Menlo, Consolas, DejaVu Sans Mono, monospace" font-size="8.5" fill="#BFF6FF">GP posterior ±2σ</text>
</g></g>
<path class="sp" d="M66 140l2 5 5 2-5 2-2 5-2-5-5-2 5-2z" fill="#FFFFFF"/>
<path class="sp" style="animation-delay:1.1s" d="M384 268l2 5 5 2-5 2-2 5-2-5-5-2 5-2z" fill="#FFE27A"/>
<path class="sp" style="animation-delay:2s" d="M122 352l1.5 4 4 1.5-4 1.5-1.5 4-1.5-4-4-1.5 4-1.5z" fill="#B6FF3B"/>
</svg>'''
open(os.path.join(OUT, "kartik.svg"), "w").write(avatar)

# ── app icon: a ringed planet whose ring is a little neural network ─────────
def icon_svg(rounded=True):
    bg = ('<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#1C1253"/>'
          '<stop offset=".55" stop-color="#5B2FD6"/><stop offset="1" stop-color="#22B8E0"/></linearGradient></defs>')
    rect = '<rect width="512" height="512" rx="116" fill="url(#g)"/>' if rounded else '<rect width="512" height="512" fill="url(#g)"/>'
    s = 512 / 108
    f = lambda v: f"{v*s:.1f}"
    ring = [(54 + 34 * math.cos(math.radians(a)), 56 + 11 * math.sin(math.radians(a))) for a in (200, 250, 300, 350, 20)]
    nodes = "".join(f'<circle cx="{f(x)}" cy="{f(y)}" r="{f(3.4)}" fill="{c}"/>' for (x, y), c in zip(ring, ["#22E4FF", "#FF7AD9", "#B6FF3B", "#FFE27A", "#22E4FF"]))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">{bg}{rect}'
            f'<ellipse cx="{f(54)}" cy="{f(56)}" rx="{f(34)}" ry="{f(11)}" fill="none" stroke="#FFFFFF" stroke-opacity=".55" stroke-width="{f(2.6)}"/>'
            f'<circle cx="{f(54)}" cy="{f(54)}" r="{f(20)}" fill="#FFB84F"/><circle cx="{f(47)}" cy="{f(47)}" r="{f(7)}" fill="#FFFFFF" opacity=".35"/>'
            f'<path d="M{f(20)} {f(56)}A{f(34)} {f(11)} 0 0 0 {f(88)} {f(56)}" fill="none" stroke="#FFFFFF" stroke-width="{f(2.6)}"/>{nodes}'
            f'<path d="M{f(80)} {f(20)}l{f(1.6)} {f(4)} {f(4)} {f(1.6)} {f(-4)} {f(1.6)} {f(-1.6)} {f(4)} {f(-1.6)} {f(-4)} {f(-4)} {f(-1.6)} {f(4)} {f(-1.6)}z" fill="#FFFFFF"/></svg>')
icon = icon_svg(True); mask = icon_svg(False)
open(os.path.join(OUT, "icon.svg"), "w").write(icon)

import resvg_py
def png(svg, size, path):
    open(path, "wb").write(bytes(resvg_py.svg_to_bytes(svg_string=svg, width=size, height=size)))
png(icon, 192, f"{OUT}/icon-192.png"); png(icon, 512, f"{OUT}/icon-512.png")
png(mask, 512, f"{OUT}/icon-maskable-512.png"); png(mask, 180, f"{OUT}/apple-touch-icon.png")
if os.environ.get("PREVIEW"):
    png(avatar, 880, os.environ["PREVIEW"])

def cpath(cx, cy, r):
    return f"M{cx-r:.2f},{cy:.2f}a{r:.2f},{r:.2f} 0 1,0 {2*r:.2f},0a{r:.2f},{r:.2f} 0 1,0 {-2*r:.2f},0"
def vector(mono):
    w = "#FFFFFF"
    p = ['<?xml version="1.0" encoding="utf-8"?>',
         '<vector xmlns:android="http://schemas.android.com/apk/res/android" android:width="108dp" android:height="108dp" android:viewportWidth="108" android:viewportHeight="108">',
         f'  <path android:fillColor="{w if mono else "#FFB84F"}" android:pathData="{cpath(54, 54, 20)}"/>',
         f'  <path android:strokeColor="{w}" android:strokeWidth="2.6" android:fillColor="#00000000" android:pathData="M20,56A34,11 0 0,0 88,56"/>']
    for (a, c) in zip((200, 250, 300, 350, 20), ["#22E4FF", "#FF7AD9", "#B6FF3B", "#FFE27A", "#22E4FF"]):
        x, y = 54 + 34 * math.cos(math.radians(a)), 56 + 11 * math.sin(math.radians(a))
        p.append(f'  <path android:fillColor="{w if mono else c}" android:pathData="{cpath(x, y, 3.4)}"/>')
    p.append('  <path android:fillColor="#FFFFFF" android:pathData="M80,20l1.6,4 4,1.6 -4,1.6 -1.6,4 -1.6,-4 -4,-1.6 4,-1.6z"/>')
    p.append('</vector>')
    return "\n".join(p) + "\n"
res = os.path.join(ROOT, "android", "app", "src", "main", "res", "drawable")
os.makedirs(res, exist_ok=True)
open(os.path.join(res, "ic_launcher_foreground.xml"), "w").write(vector(False))
open(os.path.join(res, "ic_launcher_monochrome.xml"), "w").write(vector(True))
print("art written")
