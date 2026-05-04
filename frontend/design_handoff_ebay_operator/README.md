# eBay Operator — Hero Animation Handoff

A 17-second narrative hero animation showing the full flow:
**upload photo → describe items → AI detects → items explode into listings → posted to eBay**.

## Files

| File | Purpose |
|---|---|
| `index.html` | Main page; mounts the animation, owns the Tweaks panel and EditMode defaults. Drop the markup inside `<div class="page" id="root">` into your hero section. |
| `hero-animation.jsx` | The animation scene itself. All component logic, timing, and SVG/foreignObject rendering. |
| `items-data.jsx` | Subject + item definitions (illustration scenes + the real-photo scene with bounding rects). Defines `window.SUBJECTS`. |
| `animations.jsx` | Stage / Sprite / Easing / interpolate / useTime primitives. Generic — reusable across other animations. |
| `tweaks-panel.jsx` | Tweaks UI shell + form-control helpers (`TweaksPanel`, `useTweaks`, `TweakSlider`, `TweakRadio`, etc). Optional — only needed if you keep the Tweaks panel. |
| `assets/desk-photo.jpg` | The real photo used for the default `realDesk` subject. Replace this + update rects in `items-data.jsx` to use a different photo. |

## How it's wired

1. **React + Babel + JSX in the browser.** `index.html` loads `react@18.3.1`, `react-dom@18.3.1`, `@babel/standalone@7.29.0` (pinned with integrity hashes), then `animations.jsx` → `tweaks-panel.jsx` → `items-data.jsx` → `hero-animation.jsx` as `<script type="text/babel">`.
2. **Each script attaches its exports to `window`** so the next script can find them. `items-data.jsx` does `window.SUBJECTS = {...}` etc; `hero-animation.jsx` references `window.SUBJECTS[subjectKey]`.
3. **The `<Stage>`** (from `animations.jsx`) owns the timeline. Its children read the current time via `useTime()`. The Stage auto-scales to fit its parent at the original 1280×720 aspect ratio.
4. **The `EDITMODE-BEGIN/END` block** in `index.html` is for the in-page Tweaks panel. Strip it (and the panel) when shipping to production.

## Timing map (total 17s)

| Window | Phase |
|---|---|
| 0.0 – 1.6s | Upload card — photo file uploads, progress bar fills, green check |
| 1.6 – 7.0s | Description prompt — user types item list (≈3.8s with comma/period pauses, then read beat) |
| 7.0 – 8.4s | Photo arrives in viewport (camera-shutter feel) |
| 8.4 – 10.6s | AI detection — scan line + amber bounding boxes lock onto items + labels |
| 10.6 – 12.4s | Explode — items lift out, dust particles, fly to listing slots |
| 12.4 – 13.0s | Listings build — cards render with slot-machine price ticker |
| 13.0 – 14.2s | "Drafting listings" beat |
| 14.2 – 16.6s | Posting — items get LIVE stamps with stagger, counter ticks up |
| 15.2 – 16.8s | Cursor flyover — animated arrow rides to featured card with payout tooltip |
| 16.6 – 17.0s | End-frame summary banner slides up — Total potential / Ready to ship |

All these times shift if you change `INTRO_DURATION` (`hero-animation.jsx` line ~12) or the Stage `duration` prop in `index.html`.

## Integration into your codebase

Pick the path that matches your stack:

### Option A — drop-in iframe / standalone HTML
Easiest if your site is plain HTML or your framework can't host JSX-via-Babel comfortably. Host the entire folder as a static asset bundle and `<iframe>` it:

```html
<iframe src="/hero-animation/index.html" width="100%" height="600"
        style="border:0; aspect-ratio: 16/9;" loading="lazy"></iframe>
```

Pros: zero integration work, isolates the Babel pipeline. Con: iframe sandbox.

### Option B — React component (recommended for React apps)
1. Convert `animations.jsx`, `items-data.jsx`, `hero-animation.jsx`, `tweaks-panel.jsx` from globals-on-window into proper ES modules with `import/export`.
2. Replace `<script type="text/babel">` with your build pipeline (Vite, Next.js, CRA — all transpile JSX).
3. Keep the photo at `/public/desk-photo.jpg` (or wherever your bundler serves static assets) and update the `REAL_DESK_PHOTO` constant in `items-data.jsx`.
4. Render `<HeroScene subjectKey="realDesk" layoutMode="single" explodeStyle="arc" dark={false} />` inside a `<Stage width={1280} height={720} duration={17}>`.

Conversion tips:
- `window.PALETTE` → `export const PALETTE`
- `window.SUBJECTS` → `export const SUBJECTS`
- `window.HeroScene` → `export function HeroScene`
- All `Easing`, `Stage`, `useTime`, `interpolate` are already namespaced in `animations.jsx` — just export them.

### Option C — Web Component
Wrap `HeroScene` in a custom element so it works in any framework. Skim `animations.jsx`'s Stage code; the same pattern (RAF loop + state) ports cleanly to a class-based custom element.

## Customization checklist

- **Different photo?** Replace `assets/desk-photo.jpg`, update `REAL_DESK_PHOTO` in `items-data.jsx`, and re-measure each item's `rect: [x, y, w, h]` (normalized 0–1, in the original photo orientation — set `rotated: true` if your photo is upside-down).
- **Different items / prices / titles?** Edit the `items` array of the `realDesk` subject in `items-data.jsx`. Each item needs `{ id, name, price, condition, category, rect, [pad] }`. The `pad` prop adds breathing room around an off-center item.
- **Different total length?** Bump `Stage duration` in `index.html` and adjust `INTRO_DURATION` + the time constants in `hero-animation.jsx`. The verbal timing map above is your guide.
- **Different brand colors?** `PALETTE` at the top of `hero-animation.jsx`. The detection box accent is `detectAccent` (currently amber `#d97706`).
- **Strip Tweaks?** Delete the Tweaks panel mount + `<script type="text/babel" src="tweaks-panel.jsx">` line + the `EDITMODE-BEGIN/END` block. Pass tweak values directly as props to `HeroScene`.

## Things to know

- **Speaker notes / `data-screen-label` / Origin DS bits** are not used in this artifact — it's a self-contained hero, not a deck.
- **Photo loads via SVG `<image>`** for the photo frame, and via Canvas-cropped data URLs for the listing thumbnails (each item's tile is pre-cropped from the source photo at mount time, then rotated 180° to match the intended orientation). This keeps each thumbnail crisp and properly proportioned.
- **The Stage uses `requestAnimationFrame`** which gets throttled when the iframe is offscreen. If you embed via iframe and the user scrolls past, RAF will pause and resume — expected behavior.
- **No external network calls.** The Babel transform is the only runtime cost; everything else is static.

## Re-verify after porting

Eye-test these in order:
1. Upload card progress bar fills cleanly to a green checkmark
2. Prompt typewriter pauses on commas, settles before fading
3. Photo arrives with subtle slide + capture flash
4. Amber detection boxes draw left-to-right with confidence labels
5. Items lift, dust puffs, arc into listing slots
6. Listing card prices wobble before settling
7. LIVE stamps land with a slight stagger
8. Cursor flies to the featured card and a dark tooltip reveals payout math
9. Total-potential summary slides up at the bottom
