// @ts-nocheck
// hero-scene.tsx — ES-module port of design_handoff_ebay_operator/hero-animation.jsx
// Changes from source:
//   - React imports converted to ES module imports
//   - window.SUBJECTS → SUBJECTS (imported)
//   - url("assets/desk-photo.jpg") → url("${REAL_DESK_PHOTO}") (imported)
//   - window.HeroScene / window.HeroAnimation assignments removed
//   - export { HeroScene, HeroAnimation } added at bottom

import React, { useState, useEffect, useRef, useMemo } from 'react'
import { Stage, useTime, Easing, clamp } from './animations'
import { SUBJECTS, REAL_DESK_PHOTO } from './items-data'

// hero-animation.jsx
// 17-second narrative animation for eBay Operator hero.
// Acts:
//   0.0–1.6s   Upload zone — photo file uploads with progress bar
//   1.6–7.0s   Description prompt — user types item description (≈3.8s typing + read beat)
//   7.0–8.4s   Photo arrives in viewport (camera shutter feel)
//   8.4–10.6s  AI detection: scan line + bounding boxes lock onto items + labels
//   10.6–12.4s Explode: items lift out of photo, scatter into target slots
//   12.4–14.2s Posting: green LIVE stamp on each, counter ticks up
//   14.2–17.0s Final settle

const INTRO_DURATION = 7.0;
//
// Hover/click to replay handled by Stage's built-in scrubber + a wrapper.

// Stage canvas: 1280×720 (16:9). All coords below are in this space.

const CANVAS_W = 1280;
const CANVAS_H = 720;

// ── Color palette (neutral / minimal hero, single accent) ───────────────────
const PALETTE = {
  light: {
    bg: "#fcfaf7",
    surface: "#ffffff",
    text: "#141413",
    textSubdued: "#73716d",
    border: "#dedbd5",
    borderStrong: "#8d8a86",
    accent: "#141413",          // primary accent = strong black
    success: "#005c54",         // green for LIVE
    successFill: "#dff5ee",
    detectStroke: "#f59e0b",     // amber for AI bounding boxes
    detectFill: "rgba(245,158,11,0.06)",
    detectAccent: "#92400e",     // darker amber for label tag bg
    photoFrame: "#141413",
    shadow: "rgba(20,20,19,0.10)",
  },
  dark: {
    bg: "#141413",
    surface: "#1f1e1c",
    text: "#fcfaf7",
    textSubdued: "#a3a09a",
    border: "#2e2c29",
    borderStrong: "#5a5854",
    accent: "#fcfaf7",
    success: "#3ac7a1",
    successFill: "rgba(58,199,161,0.14)",
    detectStroke: "#fbbf24",     // amber for AI bounding boxes (slightly brighter for dark bg)
    detectFill: "rgba(251,191,36,0.08)",
    detectAccent: "#fbbf24",
    photoFrame: "#fcfaf7",
    shadow: "rgba(0,0,0,0.5)",
  },
};

// ── Layout positions ────────────────────────────────────────────────────────
// Photo lives left-of-center; listings dock right-of-center.

const PHOTO_BOX = { x: 80, y: 110, w: 540, h: 500 };

// Photo aspect (width/height) for real-photo subjects. Used to compute
// letterbox offsets so item rects line up with what's actually visible.
const PHOTO_ASPECT = 16 / 9;

// Inner area of the photo frame (excludes the bottom filename strip).
function photoInnerBox() {
  return {
    x: PHOTO_BOX.x + 14,
    y: PHOTO_BOX.y + 14,
    w: PHOTO_BOX.w - 28,
    h: PHOTO_BOX.h - 60,
  };
}

// For a real-photo subject (background-size: contain, centered), compute the
// actual on-screen rectangle of the photo within the frame.
function photoVisibleBox(subject) {
  const inner = photoInnerBox();
  if (!subject || !subject.photo) return inner;
  const aspect = subject.aspect || PHOTO_ASPECT;
  const innerAspect = inner.w / inner.h;
  if (aspect > innerAspect) {
    // photo is wider than frame — letterbox top/bottom
    const w = inner.w;
    const h = inner.w / aspect;
    return { x: inner.x, y: inner.y + (inner.h - h) / 2, w, h };
  } else {
    // photo is taller — pillarbox left/right
    const h = inner.h;
    const w = inner.h * aspect;
    return { x: inner.x + (inner.w - w) / 2, y: inner.y, w, h };
  }
}

// Convert a normalized [x,y,w,h] rect (in 0..1 photo coords) to canvas coords.
// `rect` is in ORIGINAL-photo coords; if subject.rotate is 180, we flip to
// match the visually-rotated display.
function rectInPhoto(subject, rect) {
  const box = subject && subject.photo ? photoVisibleBox(subject) : photoInnerBox();
  let [rx, ry, rw, rh] = rect;
  if (subject && subject.rotate === 180) {
    rx = 1 - rx - rw;
    ry = 1 - ry - rh;
  }
  return {
    x: box.x + rx * box.w,
    y: box.y + ry * box.h,
    w: rw * box.w,
    h: rh * box.h,
  };
}

// Compute target slots for listings based on layout mode + count.
function getListingTargets(mode, count) {
  // Right pane: x in [660 .. 1230], y in [80 .. 660]
  const PANE = { x: 660, y: 80, w: 580, h: 580 };

  if (mode === "grid") {
    const cols = 4, rows = Math.ceil(count / cols);
    const pad = 12;
    const cw = (PANE.w - pad * (cols - 1)) / cols;
    const ch = Math.min(180, (PANE.h - pad * (rows - 1)) / rows);
    return Array.from({ length: count }, (_, i) => {
      const col = i % cols, row = Math.floor(i / cols);
      return {
        x: PANE.x + col * (cw + pad),
        y: PANE.y + row * (ch + pad),
        w: cw, h: ch,
        kind: "card-mini",
      };
    });
  }

  if (mode === "stack") {
    // Slightly fanned vertical stack (cards overlap)
    const cw = 460, ch = 96;
    const yStep = (PANE.h - ch) / Math.max(count - 1, 1);
    return Array.from({ length: count }, (_, i) => ({
      x: PANE.x + 60,
      y: PANE.y + i * yStep,
      w: cw, h: ch,
      kind: "card-row",
    }));
  }

  if (mode === "single") {
    // One big featured card; rest tile under as small chips
    const featuredCount = 1;
    const arr = [];
    arr.push({ x: PANE.x, y: PANE.y, w: PANE.w, h: 360, kind: "card-feature" });
    const remaining = count - featuredCount;
    const cols = Math.min(4, remaining);
    const cw = (PANE.w - 12 * (cols - 1)) / cols;
    const ch = 96;
    for (let i = 0; i < remaining; i++) {
      const col = i % cols, row = Math.floor(i / cols);
      arr.push({
        x: PANE.x + col * (cw + 12),
        y: PANE.y + 376 + row * (ch + 12),
        w: cw, h: ch,
        kind: "card-chip",
      });
    }
    return arr;
  }

  // default: grid
  return getListingTargets("grid", count);
}

// ── Components ──────────────────────────────────────────────────────────────

// The "photo" — a fake snapshot frame holding the cluttered scene.
function PhotoFrame({ subject, items, t, palette, detectProgress, captureFlash }) {
  // detectProgress: 0..1 controls scan line + box draw-on
  // captureFlash: 0..1 brief overlay flash at the start

  const scanY = PHOTO_BOX.y + 30 + detectProgress * (PHOTO_BOX.h - 60);
  const showScan = detectProgress > 0.02 && detectProgress < 0.95;

  return (
    <g>
      {/* Frame shadow */}
      <rect x={PHOTO_BOX.x + 6} y={PHOTO_BOX.y + 8} width={PHOTO_BOX.w} height={PHOTO_BOX.h}
        fill={palette.shadow} rx="14" />

      {/* Frame card */}
      <rect x={PHOTO_BOX.x} y={PHOTO_BOX.y} width={PHOTO_BOX.w} height={PHOTO_BOX.h}
        fill={palette.surface} stroke={palette.border} strokeWidth="1" rx="14" />

      {/* Photo content (clipped) */}
      <defs>
        <clipPath id="photoClip">
          <rect x={PHOTO_BOX.x + 14} y={PHOTO_BOX.y + 14}
            width={PHOTO_BOX.w - 28} height={PHOTO_BOX.h - 60} rx="6" />
        </clipPath>
      </defs>
      <g clipPath="url(#photoClip)">
        {/* Photo background (desk surface) */}
        <rect x={PHOTO_BOX.x + 14} y={PHOTO_BOX.y + 14}
          width={PHOTO_BOX.w - 28} height={PHOTO_BOX.h - 60}
          fill={subject.bg} />
        {/* "Floor" gradient hint (only for illustration scenes; suppressed for real photos) */}
        {!subject.photo && (
          <rect x={PHOTO_BOX.x + 14} y={PHOTO_BOX.y + 14 + (PHOTO_BOX.h - 60) * 0.6}
            width={PHOTO_BOX.w - 28} height={(PHOTO_BOX.h - 60) * 0.4}
            fill={subject.floor} opacity="0.6" />
        )}

        {/* Real-photo mode: render the full photo as the background of the frame.
            As items lift out, the photo fades to a ghost — you can still see what was there. */}
        {subject.photo ? (
          <foreignObject
            x={PHOTO_BOX.x + 14} y={PHOTO_BOX.y + 14}
            width={PHOTO_BOX.w - 28} height={PHOTO_BOX.h - 60}>
            <div xmlns="http://www.w3.org/1999/xhtml" style={{
              width: "100%", height: "100%",
              backgroundImage: `url("${subject.photo}")`,
              backgroundSize: "contain",
              backgroundPosition: "center",
              backgroundRepeat: "no-repeat",
              backgroundColor: subject.bg,
              transform: subject.rotate ? `rotate(${subject.rotate}deg)` : undefined,
              filter: items.some(it => it.photoDim && it.photoDim < 1)
                ? `brightness(${Math.min(...items.map(it => it.photoDim ?? 1))}) saturate(${Math.min(...items.map(it => it.photoDim ?? 1)) > 0.5 ? 1 : 0.4})`
                : undefined,
              transition: "filter 0.6s ease",
            }} />
          </foreignObject>
        ) : (
          // Illustration mode: render each item's SVG component at its rect.
          items.map((item) => {
            if (item.lifted) return null;
            const r = rectInPhoto(subject, item.rect);
            return (
              <foreignObject key={item.id} x={r.x} y={r.y} width={r.w} height={r.h}>
                <div xmlns="http://www.w3.org/1999/xhtml"
                  style={{ width: "100%", height: "100%", filter: item.photoDim ? `brightness(${item.photoDim})` : undefined, transition: "filter 0.2s" }}>
                  <item.Comp />
                </div>
              </foreignObject>
            );
          })
        )}

        {/* Scan line */}
        {showScan && (
          <g>
            <line x1={PHOTO_BOX.x + 14} y1={scanY} x2={PHOTO_BOX.x + PHOTO_BOX.w - 14} y2={scanY}
              stroke={palette.detectStroke} strokeWidth="1.5" opacity="0.7" />
            <rect x={PHOTO_BOX.x + 14} y={scanY - 30}
              width={PHOTO_BOX.w - 28} height="30"
              fill={palette.detectStroke} opacity="0.06" />
          </g>
        )}

        {/* Capture flash */}
        {captureFlash > 0.01 && (
          <rect x={PHOTO_BOX.x + 14} y={PHOTO_BOX.y + 14}
            width={PHOTO_BOX.w - 28} height={PHOTO_BOX.h - 60}
            fill="white" opacity={captureFlash * 0.85} />
        )}
      </g>

      {/* Bottom "filename" strip */}
      <rect x={PHOTO_BOX.x} y={PHOTO_BOX.y + PHOTO_BOX.h - 46} width={PHOTO_BOX.w} height="46"
        fill={palette.surface} />
      <line x1={PHOTO_BOX.x} y1={PHOTO_BOX.y + PHOTO_BOX.h - 46}
        x2={PHOTO_BOX.x + PHOTO_BOX.w} y2={PHOTO_BOX.y + PHOTO_BOX.h - 46}
        stroke={palette.border} />
      <foreignObject x={PHOTO_BOX.x + 18} y={PHOTO_BOX.y + PHOTO_BOX.h - 38}
        width={PHOTO_BOX.w - 36} height="32">
        <div xmlns="http://www.w3.org/1999/xhtml" style={{
          display: "flex", alignItems: "center", justifyContent: "space-between",
          fontFamily: "'Super Sans VF', sans-serif", fontSize: 13, color: palette.textSubdued,
          fontWeight: 540,
        }}>
          <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{
              width: 14, height: 14, borderRadius: 3, background: palette.accent,
              display: "inline-flex", alignItems: "center", justifyContent: "center",
            }}>
              <span style={{ width: 6, height: 6, borderRadius: "50%", background: palette.surface }} />
            </span>
            PXL_20260426_065952443.jpg
          </span>
          <span>{subject.label}</span>
        </div>
      </foreignObject>
    </g>
  );
}

// Detection bounding box with label
function DetectionBox({ item, drawProgress, labelProgress, palette, subject }) {
  if (drawProgress <= 0) return null;
  const r = rectInPhoto(subject, item.rect);
  const px = r.x, py = r.y, pw = r.w, ph = r.h;

  const perimeter = (pw + ph) * 2;
  const drawn = perimeter * drawProgress;

  return (
    <g>
      <rect x={px - 2} y={py - 2} width={pw + 4} height={ph + 4}
        fill="none" stroke={palette.detectStroke} strokeWidth="1.5"
        strokeDasharray={`${drawn} ${perimeter}`} rx="3" />
      {/* Corner ticks */}
      {drawProgress > 0.6 && (
        <g stroke={palette.detectStroke} strokeWidth="2" fill="none">
          <path d={`M${px-4} ${py+8} L${px-4} ${py-4} L${px+8} ${py-4}`} />
          <path d={`M${px+pw-8} ${py-4} L${px+pw+4} ${py-4} L${px+pw+4} ${py+8}`} />
          <path d={`M${px-4} ${py+ph-8} L${px-4} ${py+ph+4} L${px+8} ${py+ph+4}`} />
          <path d={`M${px+pw-8} ${py+ph+4} L${px+pw+4} ${py+ph+4} L${px+pw+4} ${py+ph-8}`} />
        </g>
      )}
      {/* Label tag */}
      {labelProgress > 0 && (
        <foreignObject x={px} y={py - 26 - 4 * (1 - labelProgress)} width={pw + 8} height="26"
          style={{ opacity: labelProgress }}>
          <div xmlns="http://www.w3.org/1999/xhtml" style={{
            display: "inline-flex", alignItems: "center", gap: 6,
            background: palette.detectStroke, color: "#1a1208",
            fontFamily: "'Super Sans VF', sans-serif", fontSize: 11, fontWeight: 700,
            padding: "3px 8px", borderRadius: 4, lineHeight: 1.2,
            maxWidth: pw + 4, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
          }}>
            <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#1a1208" }} />
            {item.shortLabel}
            <span style={{ opacity: 0.6, marginLeft: 2 }}>{Math.round(85 + (item.id.length * 7) % 12)}%</span>
          </div>
        </foreignObject>
      )}
    </g>
  );
}

// A flying item during the explode phase + listing card after
function ItemSprite({ item, target, t, palette, posted, postedAt, layoutMode, subject }) {
  // Phase logic:
  //   t < detectEnd: rendered inside photo (handled by PhotoFrame)
  //   detectEnd <= t < explodeEnd: animate from photo pos -> target pos
  //   t >= explodeEnd: docked at target as a listing card

  const detectEnd = item.timing.detectEnd;
  const explodeStart = item.timing.explodeStart;
  const explodeEnd = item.timing.explodeEnd;
  const cardBuildEnd = item.timing.cardBuildEnd;

  // Photo source rect (in canvas coords)
  const sr = rectInPhoto(subject, item.rect);
  const sx = sr.x, sy = sr.y, sw = sr.w, sh = sr.h;

  // Hide before explode begins
  if (t < explodeStart) return null;

  // Dust particles when item lifts off (first 0.4s of explode)
  const dustT = clamp((t - explodeStart) / 0.45, 0, 1);
  const showDust = dustT > 0 && dustT < 1;

  // Compute interpolated position
  let x, y, w, h;
  let rotation = 0;
  let cardReveal = 0;

  if (t < explodeEnd) {
    // Explode in flight
    const p = clamp((t - explodeStart) / (explodeEnd - explodeStart), 0, 1);
    const eased = Easing.easeInOutCubic(p);

    // Arc trajectory: lift up slightly then settle
    const arc = Math.sin(p * Math.PI) * item.physics.arcHeight;

    x = sx + (target.x - sx) * eased;
    y = sy + (target.y - sy) * eased - arc;
    w = sw + (target.w - sw) * eased;
    h = sh + (target.h - sh) * eased;
    rotation = item.physics.spin * (1 - eased);
    cardReveal = 0;
  } else {
    // Docked. Card builds in over cardBuildEnd window.
    x = target.x; y = target.y; w = target.w; h = target.h;
    rotation = 0;
    cardReveal = clamp((t - explodeEnd) / (cardBuildEnd - explodeEnd), 0, 1);
  }

  const shouldShowAsCard = t >= explodeEnd;
  const cx = x + w / 2;
  const cy = y + h / 2;

  // Card content: image area + meta
  const isMini = target.kind === "card-mini";
  const isRow = target.kind === "card-row";
  const isFeature = target.kind === "card-feature";
  const isChip = target.kind === "card-chip";

  // Dust particles — small puffs at the photo source position when item lifts off
  const dustParticles = showDust ? (() => {
    const seed = (item.id || 0) * 17 + 13;
    const out = [];
    for (let k = 0; k < 5; k++) {
      const ang = ((seed * (k + 1) * 37) % 360) * (Math.PI / 180);
      const dist = 8 + ((seed * (k + 2) * 11) % 14);
      const dx = Math.cos(ang) * dist * dustT;
      const dy = Math.sin(ang) * dist * dustT - dustT * 6;
      const dr = 1.5 + ((seed * (k + 3) * 7) % 3) * 0.7;
      const op = (1 - dustT) * 0.55;
      out.push(
        <circle key={k} cx={sx + sw / 2 + dx} cy={sy + sh / 2 + dy} r={dr * (1 + dustT * 0.6)}
          fill={palette.textSubdued} opacity={op} />
      );
    }
    return out;
  })() : null;

  return (
    <g>
      {dustParticles}
      <g transform={`rotate(${rotation} ${cx} ${cy})`}>
        {!shouldShowAsCard ? (
          // Flight: just the item illustration, no card chrome
          <g>
            <rect x={x} y={y} width={w} height={h} rx="6"
              fill={palette.surface}
              stroke={palette.border} strokeWidth="1"
              style={{ filter: `drop-shadow(0 ${4 + 12 * Math.sin(((t - explodeStart) / (explodeEnd - explodeStart)) * Math.PI)}px ${8 + 16 * Math.sin(((t - explodeStart) / (explodeEnd - explodeStart)) * Math.PI)}px ${palette.shadow})` }}
            />
            <foreignObject x={x + 4} y={y + 4} width={w - 8} height={h - 8}>
              <div xmlns="http://www.w3.org/1999/xhtml" style={{ width: "100%", height: "100%" }}>
                <item.Comp />
              </div>
            </foreignObject>
          </g>
        ) : (
          // Docked card
          <ListingCard item={item} x={x} y={y} w={w} h={h} kind={target.kind}
            reveal={cardReveal} palette={palette} posted={posted} postedAt={postedAt} t={t} />
        )}
      </g>
    </g>
  );
}

// Slot-machine price ticker — wobbles through values, settles on item.price
function PriceTicker({ price, reveal, posted }) {
  // reveal: 0..1 (card build progress)
  // While reveal < 0.85, show wobbling values; then settle to final.
  if (reveal <= 0) return <span>${price}</span>;
  if (reveal >= 0.85 || posted) return <span>${price}</span>;
  // Pseudo-random wobble: deterministic based on reveal (so it doesn't change per render)
  const seed = Math.floor(reveal * 60);
  const variance = price * 0.35 * (1 - reveal); // narrows as reveal approaches 1
  const wobble = ((seed * 9301 + 49297) % 233280) / 233280; // 0..1
  const shown = Math.max(1, Math.round(price - variance + wobble * variance * 2));
  return <span style={{ opacity: 0.85 }}>${shown}</span>;
}

function ListingCard({ item, x, y, w, h, kind, reveal, palette, posted, postedAt, t }) {
  const isMini = kind === "card-mini";
  const isRow = kind === "card-row";
  const isFeature = kind === "card-feature";
  const isChip = kind === "card-chip";

  // Reveal animation: card scales/fades in
  const cardOpacity = clamp(reveal * 1.5, 0, 1);
  const scale = 0.92 + 0.08 * Easing.easeOutBack(reveal);
  const cx = x + w / 2;
  const cy = y + h / 2;

  // LIVE stamp animation
  const livePulse = posted ? Easing.easeOutBack(clamp((t - postedAt) / 0.5, 0, 1)) : 0;

  return (
    <g transform={`translate(${cx} ${cy}) scale(${scale}) translate(${-cx} ${-cy})`} opacity={cardOpacity}>
      {/* Shadow */}
      <rect x={x + 1} y={y + 3} width={w} height={h} rx={isMini || isChip ? 6 : 10}
        fill={palette.shadow} opacity="0.5" />
      {/* Card body */}
      <rect x={x} y={y} width={w} height={h} rx={isMini || isChip ? 6 : 10}
        fill={palette.surface} stroke={palette.border} strokeWidth="1" />

      {isMini && <MiniCardContent item={item} x={x} y={y} w={w} h={h} reveal={reveal} palette={palette} posted={posted} />}
      {isRow && <RowCardContent item={item} x={x} y={y} w={w} h={h} reveal={reveal} palette={palette} posted={posted} />}
      {isFeature && <FeatureCardContent item={item} x={x} y={y} w={w} h={h} reveal={reveal} palette={palette} posted={posted} />}
      {isChip && <ChipCardContent item={item} x={x} y={y} w={w} h={h} reveal={reveal} palette={palette} posted={posted} />}

      {/* LIVE stamp */}
      {posted && livePulse > 0 && (
        <g transform={`translate(${x + w - 6}, ${y + 6}) scale(${livePulse}) translate(${-(x + w - 6)}, ${-(y + 6)})`}>
          <foreignObject x={x + w - 64} y={y + 6} width="58" height="22">
            <div xmlns="http://www.w3.org/1999/xhtml" style={{
              background: palette.success, color: "#ffffff",
              fontFamily: "'Super Sans VF', sans-serif", fontSize: 10, fontWeight: 700,
              letterSpacing: 0.5,
              padding: "3px 7px", borderRadius: 3, textAlign: "center",
              display: "flex", alignItems: "center", justifyContent: "center", gap: 4,
              boxShadow: `0 2px 6px ${palette.shadow}`,
            }}>
              <span style={{ width: 5, height: 5, borderRadius: "50%", background: "#fff",
                animation: "ebop-pulse 1.2s infinite" }} />
              LIVE
            </div>
          </foreignObject>
        </g>
      )}
    </g>
  );
}

function MiniCardContent({ item, x, y, w, h, reveal, palette, posted }) {
  const imgH = h * 0.55;
  return (
    <>
      {/* Image area */}
      <foreignObject x={x + 1} y={y + 1} width={w - 2} height={imgH}>
        <div xmlns="http://www.w3.org/1999/xhtml" style={{
          width: "100%", height: "100%", overflow: "hidden",
          borderRadius: "5px 5px 0 0",
        }}>
          <item.Comp />
        </div>
      </foreignObject>
      {/* Meta */}
      <foreignObject x={x + 8} y={y + imgH + 4} width={w - 16} height={h - imgH - 8}>
        <div xmlns="http://www.w3.org/1999/xhtml" style={{
          fontFamily: "'Super Sans VF', sans-serif", color: palette.text,
          opacity: clamp((reveal - 0.3) * 2, 0, 1),
        }}>
          <div style={{
            fontSize: 10, fontWeight: 600, lineHeight: 1.2,
            display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical",
            overflow: "hidden",
          }}>{item.name}</div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginTop: 2 }}>
            <span style={{ fontSize: 11, fontWeight: 700 }}><PriceTicker price={item.price} reveal={reveal} posted={posted} /></span>
            <span style={{ fontSize: 9, color: palette.textSubdued, fontWeight: 540 }}>{item.condition.split("–")[0].trim()}</span>
          </div>
        </div>
      </foreignObject>
    </>
  );
}

function RowCardContent({ item, x, y, w, h, reveal, palette, posted }) {
  const imgSize = h - 16;
  return (
    <>
      <foreignObject x={x + 8} y={y + 8} width={imgSize} height={imgSize}>
        <div xmlns="http://www.w3.org/1999/xhtml" style={{ width: "100%", height: "100%", borderRadius: 4, overflow: "hidden" }}>
          <item.Comp />
        </div>
      </foreignObject>
      <foreignObject x={x + 16 + imgSize} y={y + 12} width={w - 24 - imgSize} height={h - 24}>
        <div xmlns="http://www.w3.org/1999/xhtml" style={{
          fontFamily: "'Super Sans VF', sans-serif", color: palette.text,
          opacity: clamp((reveal - 0.3) * 2, 0, 1),
          display: "flex", flexDirection: "column", justifyContent: "center", height: "100%",
        }}>
          <div style={{ fontSize: 11, color: palette.textSubdued, fontWeight: 540, textTransform: "uppercase", letterSpacing: 0.5 }}>{item.category}</div>
          <div style={{ fontSize: 14, fontWeight: 600, lineHeight: 1.25, marginTop: 2,
            display: "-webkit-box", WebkitLineClamp: 1, WebkitBoxOrient: "vertical", overflow: "hidden" }}>{item.name}</div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginTop: 6 }}>
            <span style={{ fontSize: 18, fontWeight: 700 }}><PriceTicker price={item.price} reveal={reveal} posted={posted} /></span>
            <span style={{ fontSize: 11, color: palette.textSubdued, fontWeight: 540 }}>{item.condition}</span>
          </div>
        </div>
      </foreignObject>
    </>
  );
}

function FeatureCardContent({ item, x, y, w, h, reveal, palette, posted }) {
  const imgW = w * 0.55;
  return (
    <>
      <foreignObject x={x + 1} y={y + 1} width={imgW} height={h - 2}>
        <div xmlns="http://www.w3.org/1999/xhtml" style={{ width: "100%", height: "100%", overflow: "hidden", borderRadius: "9px 0 0 9px" }}>
          <item.Comp fit="contain" />
        </div>
      </foreignObject>
      <foreignObject x={x + imgW + 24} y={y + 32} width={w - imgW - 48} height={h - 64}>
        <div xmlns="http://www.w3.org/1999/xhtml" style={{
          fontFamily: "'Super Sans VF', sans-serif", color: palette.text,
          opacity: clamp((reveal - 0.3) * 2, 0, 1),
          display: "flex", flexDirection: "column", height: "100%",
        }}>
          <div style={{ fontSize: 11, color: palette.textSubdued, fontWeight: 540, textTransform: "uppercase", letterSpacing: 0.5 }}>{item.category}</div>
          <div style={{ fontSize: 22, fontWeight: 600, lineHeight: 1.2, marginTop: 8,
            fontFamily: "'Super Sans VF', sans-serif" }}>{item.name}</div>
          <div style={{ fontSize: 13, color: palette.textSubdued, fontWeight: 540, marginTop: 8 }}>{item.condition}</div>
          <div style={{ marginTop: "auto", display: "flex", alignItems: "baseline", justifyContent: "space-between" }}>
            <span style={{ fontSize: 32, fontWeight: 700 }}><PriceTicker price={item.price} reveal={reveal} posted={posted} /><span style={{ fontSize: 14, color: palette.textSubdued, fontWeight: 540, marginLeft: 6 }}>or Best Offer</span></span>
          </div>
        </div>
      </foreignObject>
    </>
  );
}

function ChipCardContent({ item, x, y, w, h, reveal, palette, posted }) {
  return (
    <foreignObject x={x + 8} y={y + 8} width={w - 16} height={h - 16}>
      <div xmlns="http://www.w3.org/1999/xhtml" style={{
        display: "flex", alignItems: "center", gap: 8, height: "100%",
        opacity: clamp((reveal - 0.3) * 2, 0, 1),
      }}>
        <div style={{ width: 56, height: 56, borderRadius: 4, overflow: "hidden", flex: "0 0 auto" }}>
          <item.Comp />
        </div>
        <div style={{ fontFamily: "'Super Sans VF', sans-serif", color: palette.text, minWidth: 0, flex: 1 }}>
          <div style={{ fontSize: 11, fontWeight: 600, lineHeight: 1.2,
            display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden" }}>{item.name}</div>
          <div style={{ fontSize: 13, fontWeight: 700, marginTop: 4 }}><PriceTicker price={item.price} reveal={reveal} posted={posted} /></div>
        </div>
      </div>
    </foreignObject>
  );
}

// Counter that ticks up to N
function PostedCounter({ count, t, postedStart, palette }) {
  const p = clamp((t - postedStart) / 1.6, 0, 1);
  const shown = Math.round(p * count);
  const visible = t >= postedStart;
  if (!visible) return null;
  // Fade out as the end-frame summary takes over
  const summaryStart = postedStart + 2.2;
  const fadeOut = clamp(1 - (t - summaryStart) / 0.5, 0, 1);
  return (
    <foreignObject x={660} y={20} width="600" height="50">
      <div xmlns="http://www.w3.org/1999/xhtml" style={{
        fontFamily: "'Super Sans VF', sans-serif",
        display: "flex", alignItems: "center", gap: 12,
        opacity: Easing.easeOutQuad(clamp(p * 2, 0, 1)) * fadeOut,
      }}>
        <div style={{
          display: "inline-flex", alignItems: "center", gap: 6,
          background: palette.successFill, color: palette.success,
          padding: "4px 10px", borderRadius: 100, fontSize: 12, fontWeight: 700,
          letterSpacing: 0.3,
        }}>
          <span style={{ width: 6, height: 6, borderRadius: "50%", background: palette.success,
            animation: "ebop-pulse 1.2s infinite" }} />
          POSTED TO EBAY
        </div>
        <div style={{ fontSize: 22, fontWeight: 600, color: palette.text }}>
          {shown} <span style={{ color: palette.textSubdued, fontWeight: 540, fontSize: 16 }}>listings live</span>
        </div>
      </div>
    </foreignObject>
  );
}

// Status overlay above the photo (changes per phase)
function PhotoStatus({ t, palette, items }) {
  let label = "";
  let dot = palette.textSubdued;
  if (t < INTRO_DURATION + 0.1) {
    label = "Ready to upload";
    dot = palette.textSubdued;
  } else if (t < INTRO_DURATION + 1.4) {
    label = "Photo received · PXL_20260426.jpg";
    dot = palette.textSubdued;
  } else if (t < INTRO_DURATION + 3.6) {
    const detected = items.filter(it => t >= it.timing.detectStart + 0.4).length;
    label = `Detecting items · ${detected} found`;
    dot = "#bd5200";
  } else if (t < INTRO_DURATION + 5.4) {
    label = "Extracting & writing listings…";
    dot = "#1173a8";
  } else if (t < INTRO_DURATION + 7.2) {
    label = "Generating titles, prices, conditions…";
    dot = "#1173a8";
  } else {
    label = "Posted to eBay";
    dot = "#005c54";
  }
  return (
    <foreignObject x={PHOTO_BOX.x} y={PHOTO_BOX.y - 38} width={PHOTO_BOX.w} height="30">
      <div xmlns="http://www.w3.org/1999/xhtml" style={{
        fontFamily: "'Super Sans VF', sans-serif", fontSize: 13, fontWeight: 540,
        color: palette.textSubdued, display: "flex", alignItems: "center", gap: 8,
      }}>
        <span style={{ width: 8, height: 8, borderRadius: "50%", background: dot,
          animation: t < INTRO_DURATION + 7.2 ? "ebop-pulse 1.2s infinite" : "none" }} />
        {label}
      </div>
    </foreignObject>
  );
}

// ── Intro overlay: upload + prompt ───────────────────────────────────────

const PROMPT_TEXT = "Moleskine notebook, MacBook Pro, Galaxy watch, Apple trackpad, and a custom 75% mechanical keyboard with orange & green keycaps.";

// Upload progress UI: 0–1.4s
// Prompt UI: 1.4–3.0s
function IntroOverlay({ t, palette }) {
  if (t >= INTRO_DURATION) return null;

  // Phase 1: file uploads (0 → 1.2), then settles (1.2 → 1.6)
  const uploadProgress = clamp(t / 1.2, 0, 1);
  const uploadEased = Easing.easeOutCubic(uploadProgress);

  // Phase 2: prompt slides in at 1.4s
  const promptT = t - 1.4;
  const promptIn = clamp(promptT / 0.4, 0, 1);
  const promptInEased = Easing.easeOutCubic(promptIn);

  // Typing animation: starts at 1.6s, fully typed by 5.4s with natural rhythm
  const TYPE_START = 1.6;
  const TYPE_END = 5.4;
  // Build per-character delay schedule: longer pause after punctuation
  const charDelays = React.useMemo(() => {
    const arr = [];
    let acc = 0;
    for (let i = 0; i < PROMPT_TEXT.length; i++) {
      arr.push(acc);
      const ch = PROMPT_TEXT[i];
      // base char weight
      let w = 1;
      if (ch === ',') w = 1.5;
      else if (ch === '.') w = 3;
      // space stays at 1 — same as regular chars to avoid stutter
      acc += w;
    }
    // normalize to [0..1]
    const total = acc;
    return arr.map(v => v / total);
  }, []);
  const typeT = clamp((t - TYPE_START) / (TYPE_END - TYPE_START), 0, 1);
  // Find how many chars have "fired" by typeT
  let charsTyped = 0;
  for (let i = 0; i < charDelays.length; i++) {
    if (charDelays[i] <= typeT) charsTyped = i + 1;
    else break;
  }
  const typedText = PROMPT_TEXT.slice(0, charsTyped);
  const showCaret = t < 6.4 && Math.floor(t * 2) % 2 === 0;

  // Button highlight: pulses once typing finishes
  const buttonReady = t >= TYPE_END;

  // Whole overlay fades out 6.3 → 7.0 (full beat to read finished prompt + button highlight)
  const fadeOut = clamp((t - 6.3) / 0.7, 0, 1);
  const opacity = 1 - fadeOut;

  // Card position — centered in the photo zone area roughly
  const cardX = 80;
  const cardY = 90;
  const cardW = 540;
  const cardH = 540;

  return (
    <foreignObject x={cardX} y={cardY} width={cardW} height={cardH} opacity={opacity}>
      <div xmlns="http://www.w3.org/1999/xhtml" style={{
        width: "100%", height: "100%",
        fontFamily: "'Super Sans VF', sans-serif",
        color: palette.text,
        display: "flex", flexDirection: "column",
        gap: 14,
      }}>
        {/* Upload card */}
        <div style={{
          background: palette.surface,
          border: `1px solid ${palette.border}`,
          borderRadius: 14,
          padding: 18,
          transform: `translateY(${(1 - Easing.easeOutCubic(clamp(t / 0.4, 0, 1))) * 8}px)`,
          opacity: clamp(t / 0.3, 0, 1),
        }}>
          <div style={{
            fontSize: 11, fontWeight: 600, letterSpacing: 0.6,
            textTransform: "uppercase", color: palette.textSubdued,
            marginBottom: 12,
          }}>
            1 · Upload photo
          </div>

          {/* Drop zone with file inside */}
          <div style={{
            border: `1.5px dashed ${uploadProgress >= 1 ? palette.accent : palette.border}`,
            borderRadius: 10,
            padding: "16px 14px",
            display: "flex", alignItems: "center", gap: 12,
            background: uploadProgress >= 1 ? `${palette.accent}10` : "transparent",
            transition: "all 0.3s",
          }}>
            {/* File icon */}
            <div style={{
              width: 40, height: 48, borderRadius: 4,
              background: palette.bg,
              border: `1px solid ${palette.border}`,
              display: "flex", flexDirection: "column",
              alignItems: "center", justifyContent: "center",
              flexShrink: 0,
              position: "relative",
              overflow: "hidden",
            }}>
              <div style={{
                position: "absolute",
                inset: 0,
                backgroundImage: `url("${REAL_DESK_PHOTO}")`,
                backgroundSize: "cover",
                backgroundPosition: "center",
                transform: "rotate(180deg)",
                opacity: uploadEased,
              }} />
              <div style={{
                position: "absolute",
                bottom: 3, left: 3,
                fontSize: 7, fontWeight: 700,
                color: "white",
                background: "#000",
                padding: "1px 3px",
                borderRadius: 2,
                letterSpacing: 0.4,
              }}>JPG</div>
            </div>

            {/* File details + progress */}
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{
                fontSize: 13, fontWeight: 540,
                whiteSpace: "nowrap", overflow: "hidden",
                textOverflow: "ellipsis",
                marginBottom: 4,
              }}>
                PXL_20260426_065952443.jpg
              </div>
              <div style={{
                fontSize: 11, color: palette.textSubdued,
                marginBottom: 8,
              }}>
                {uploadProgress < 1
                  ? `${(uploadEased * 2.4).toFixed(1)} MB of 2.4 MB · ${Math.round(uploadEased * 100)}%`
                  : "2.4 MB · Ready"}
              </div>
              {/* Progress bar */}
              <div style={{
                height: 4, borderRadius: 2,
                background: palette.border,
                overflow: "hidden",
              }}>
                <div style={{
                  height: "100%",
                  width: `${uploadEased * 100}%`,
                  background: uploadProgress >= 1 ? "#16a34a" : palette.accent,
                  transition: "background 0.3s",
                }} />
              </div>
            </div>

            {/* Check icon when done */}
            {uploadProgress >= 1 && (
              <div style={{
                width: 22, height: 22, borderRadius: 11,
                background: "#16a34a",
                display: "flex", alignItems: "center", justifyContent: "center",
                color: "white", fontSize: 13, fontWeight: 700,
                flexShrink: 0,
                transform: `scale(${Easing.easeOutBack(clamp((t - 0.9) / 0.3, 0, 1))})`,
              }}>✓</div>
            )}
          </div>
        </div>

        {/* Prompt card — slides in at 1.4s */}
        <div style={{
          background: palette.surface,
          border: `1px solid ${palette.border}`,
          borderRadius: 14,
          padding: 18,
          opacity: promptInEased,
          transform: `translateY(${(1 - promptInEased) * 16}px)`,
          flex: 1,
          display: "flex", flexDirection: "column",
        }}>
          <div style={{
            fontSize: 11, fontWeight: 600, letterSpacing: 0.6,
            textTransform: "uppercase", color: palette.textSubdued,
            marginBottom: 12,
            display: "flex", justifyContent: "space-between", alignItems: "center",
          }}>
            <span>2 · Anything else we should know? <span style={{ textTransform: "none", letterSpacing: 0, color: palette.textSubdued, fontWeight: 400 }}>(optional)</span></span>
          </div>

          {/* Textarea */}
          <div style={{
            border: `1px solid ${palette.border}`,
            borderRadius: 10,
            padding: "16px 16px",
            fontSize: 18, lineHeight: 1.5,
            color: palette.text,
            background: palette.bg,
            flex: 1,
            minHeight: 110,
            position: "relative",
          }}>
            {typedText}
            {showCaret && (
              <span style={{
                display: "inline-block",
                width: 2, height: 20,
                background: palette.accent,
                verticalAlign: "text-bottom",
                marginLeft: 1,
              }} />
            )}
            {!typedText && !showCaret && (
              <span style={{ color: palette.textSubdued, opacity: 0.6 }}>e.g. "Vintage camera, two lenses…"</span>
            )}
          </div>

          {/* Button */}
          <div style={{
            marginTop: 14,
            display: "flex", justifyContent: "flex-end",
          }}>
            <div style={{
              padding: "10px 18px",
              borderRadius: 10,
              fontSize: 13, fontWeight: 600,
              background: buttonReady ? palette.text : palette.border,
              color: buttonReady ? palette.bg : palette.textSubdued,
              transition: "all 0.3s",
              display: "flex", alignItems: "center", gap: 8,
              boxShadow: buttonReady
                ? `0 0 0 ${4 + Math.sin(t * 8) * 2}px ${palette.accent}30`
                : "none",
            }}>
              <span>Generate listings</span>
              <span style={{ fontSize: 14 }}>→</span>
            </div>
          </div>
        </div>
      </div>
    </foreignObject>
  );
}

// ── Main scene ──────────────────────────────────────────────────────────────

// Animated cursor + tooltip — flies to the featured listing near the end
function CursorTooltip({ t, items, palette, postedStart }) {
  const cursorStart = postedStart + 1.0;
  const cursorEnd = cursorStart + 1.6;
  if (t < cursorStart) return null;

  const featured = items.reduce((best, it) =>
    (it && (!best || (it.price > best.price))) ? it : best, null);
  if (!featured) return null;

  const tg = featured.target;
  const cx = tg.x + tg.w / 2;
  const cy = tg.y + tg.h / 2;

  const startX = 1240, startY = 700;
  const endX = cx - 12, endY = cy - 12;
  const tProg = clamp((t - cursorStart) / (cursorEnd - cursorStart), 0, 1);
  const eased = Easing.easeOutCubic(tProg);
  const ctrlX = (startX + endX) / 2 + 60;
  const ctrlY = (startY + endY) / 2 - 40;
  const oneMinus = 1 - eased;
  const px = oneMinus * oneMinus * startX + 2 * oneMinus * eased * ctrlX + eased * eased * endX;
  const py = oneMinus * oneMinus * startY + 2 * oneMinus * eased * ctrlY + eased * eased * endY;

  const settleT = clamp((t - cursorStart - 1.0) / 0.4, 0, 1);
  const tooltipOpacity = Easing.easeOutQuad(settleT);

  const fees = Math.round(featured.price * 0.13);
  const net = featured.price - fees;

  const wantsLeft = endX > 1000;
  const ttX = wantsLeft ? endX - 230 : endX + 18;
  const ttY = endY - 70;

  return (
    <g style={{ pointerEvents: "none" }}>
      {settleT > 0 && (
        <circle cx={px + 11} cy={py + 11} r={20 + settleT * 6}
          fill="none" stroke={palette.accent} strokeWidth="1.5"
          opacity={(1 - settleT) * 0.6} />
      )}
      <g transform={`translate(${px} ${py})`}>
        <path d="M0 0 L0 18 L4.5 13.5 L7.5 19.5 L10 18.5 L7 12.5 L13 12.5 Z"
          fill="#0b0b0c" stroke="#ffffff" strokeWidth="1.2" strokeLinejoin="round" />
      </g>
      {tooltipOpacity > 0 && (
        <foreignObject x={ttX} y={ttY} width="220" height="80" opacity={tooltipOpacity}>
          <div xmlns="http://www.w3.org/1999/xhtml" style={{
            fontFamily: "'Super Sans VF', sans-serif",
            background: "#0b0b0c", color: "#ffffff",
            borderRadius: 8, padding: "10px 12px",
            boxShadow: `0 12px 28px rgba(0,0,0,0.28)`,
            transform: `translateY(${(1 - tooltipOpacity) * 6}px)`,
          }}>
            <div style={{ fontSize: 10, letterSpacing: 0.6, textTransform: "uppercase",
              color: "rgba(255,255,255,0.55)", fontWeight: 600 }}>
              Estimated payout
            </div>
            <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginTop: 4 }}>
              <span style={{ fontSize: 22, fontWeight: 700, letterSpacing: -0.3 }}>${net}</span>
              <span style={{ fontSize: 11, color: "rgba(255,255,255,0.55)", fontWeight: 540 }}>
                after ${fees} fees
              </span>
            </div>
            <div style={{ fontSize: 11, color: "rgba(255,255,255,0.7)", marginTop: 4, fontWeight: 540,
              textOverflow: "ellipsis", overflow: "hidden", whiteSpace: "nowrap" }}>
              {featured.shortLabel || featured.name.split(",")[0]}
            </div>
          </div>
        </foreignObject>
      )}
    </g>
  );
}

// End-frame summary — full-width banner at the very bottom of the canvas
function EndFrameSummary({ t, items, palette, postedStart }) {
  const start = postedStart + 2.4;
  const end = start + 0.6;
  if (t < start) return null;
  const p = clamp((t - start) / (end - start), 0, 1);
  const eased = Easing.easeOutCubic(p);
  const total = items.reduce((s, it) => s + it.price, 0);
  return (
    <g opacity={eased} transform={`translate(0 ${(1 - eased) * 24})`}>
      <foreignObject x={660} y={648} width="580" height="60">
        <div xmlns="http://www.w3.org/1999/xhtml" style={{
          fontFamily: "'Super Sans VF', sans-serif",
          background: palette.text, color: palette.bg,
          borderRadius: 10, padding: "12px 18px",
          display: "flex", alignItems: "center", justifyContent: "space-between",
          boxShadow: `0 14px 32px ${palette.shadow}`,
        }}>
          <div>
            <div style={{ fontSize: 10, letterSpacing: 0.6, textTransform: "uppercase",
              opacity: 0.55, fontWeight: 600 }}>Total potential</div>
            <div style={{ fontSize: 26, fontWeight: 700, letterSpacing: -0.4, marginTop: 2 }}>
              ${total.toLocaleString()}
            </div>
          </div>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: 11, opacity: 0.6, fontWeight: 540 }}>
              {items.length} listings · 1 photo · 12 seconds
            </div>
            <div style={{ fontSize: 12, opacity: 0.95, fontWeight: 600, marginTop: 4 }}>
              Ready to ship →
            </div>
          </div>
        </div>
      </foreignObject>
    </g>
  );
}

function HeroScene({ subjectKey, layoutMode, explodeStyle, dark }) {
  const t = useTime();
  const palette = dark ? PALETTE.dark : PALETTE.light;
  const subject = SUBJECTS[subjectKey];

  // Build per-item timing & physics
  const items = useMemo(() => {
    const targets = getListingTargets(layoutMode, subject.items.length);
    // For "single" featured layout, hoist a specific item into the feature slot.
    // Real-desk subject features the keyboard; others default to first item.
    const featuredId = subjectKey === "realDesk" ? "keyboard" : null;
    let assignedTargets = targets;
    if (layoutMode === "single" && featuredId) {
      const featuredIdx = subject.items.findIndex(it => it.id === featuredId);
      if (featuredIdx > 0) {
        // Build target list where targets[featuredIdx] = original featured slot,
        // and the original [1..] chip targets fill the remaining items in order.
        const featureSlot = targets[0];
        const chipSlots = targets.slice(1);
        let chipCursor = 0;
        assignedTargets = subject.items.map((it, i) => {
          if (i === featuredIdx) return featureSlot;
          return chipSlots[chipCursor++] || targets[0];
        });
      }
    }
    return subject.items.map((item, i) => {
      const detectStart = INTRO_DURATION + 1.6 + i * 0.18;          // staggered detection
      const detectEnd = detectStart + 0.8;
      const explodeStart = INTRO_DURATION + 3.7 + i * 0.05;
      const explodeEnd = explodeStart + 1.7;
      const cardBuildEnd = explodeEnd + 0.5;
      const postedAt = INTRO_DURATION + 7.4 + i * 0.07;

      // Physics per explodeStyle
      let physics;
      if (explodeStyle === "scatter") {
        physics = {
          arcHeight: 60 + ((i * 37) % 80),
          spin: ((i * 53) % 30) - 15,
        };
      } else if (explodeStyle === "grid") {
        physics = { arcHeight: 0, spin: 0 };
      } else { // particle: low arc, slight spin
        physics = { arcHeight: 30, spin: ((i * 71) % 18) - 9 };
      }

      return {
        ...item,
        shortLabel: item.name.split(",")[0].split(" ").slice(0, 2).join(" "),
        timing: { detectStart, detectEnd, explodeStart, explodeEnd, cardBuildEnd, postedAt },
        physics,
        target: assignedTargets[i] || assignedTargets[0],
      };
    });
  }, [subjectKey, layoutMode, explodeStyle]);

  // Capture flash (when photo arrives, post-intro)
  const photoT = t - INTRO_DURATION;
  const captureFlash = clamp(1 - photoT / 0.6, 0, 1) * (photoT > 0 && photoT < 0.6 ? 1 : 0);

  // Detection scan progress (0..1) across detection phase
  const detectProgress = clamp((t - INTRO_DURATION - 1.4) / 2.2, 0, 1);

  // Posted phase start
  const postedStart = INTRO_DURATION + 7.2;
  const isPosted = (item) => t >= item.timing.postedAt;

  return (
    <svg viewBox={`0 0 ${CANVAS_W} ${CANVAS_H}`} width={CANVAS_W} height={CANVAS_H}
      style={{ position: "absolute", inset: 0, display: "block" }}
      xmlns="http://www.w3.org/2000/svg">
      {/* Page background */}
      <rect width={CANVAS_W} height={CANVAS_H} fill={palette.bg} />

      {/* Intro: upload + prompt UI (0–3s) */}
      <IntroOverlay t={t} palette={palette} />

      {/* Photo arrival animation (post-intro): slight slide-in + fade */}
      {t >= INTRO_DURATION && (() => {
        const photoT = t - INTRO_DURATION;
        const arrive = Easing.easeOutCubic(clamp(photoT / 0.7, 0, 1));
        const dy = (1 - arrive) * 24;
        const opacity = arrive;
        return (
          <g transform={`translate(0 ${dy})`} opacity={opacity}>
            <PhotoStatus t={t} palette={palette} items={items} />
            <PhotoFrame
              subject={subject}
              items={items.map(it => ({
                ...it,
                lifted: t >= it.timing.explodeStart,
                photoDim: t >= INTRO_DURATION + 3.4 ? 0.7 : 1,
              }))}
              t={t}
              palette={palette}
              detectProgress={detectProgress}
              captureFlash={captureFlash}
            />
            {/* Detection boxes */}
            {items.map((item, i) => {
              if (t < item.timing.detectStart) return null;
              if (t >= item.timing.explodeStart) return null;
              const drawProgress = clamp((t - item.timing.detectStart) / 0.5, 0, 1);
              const labelProgress = clamp((t - item.timing.detectStart - 0.3) / 0.3, 0, 1);
              return (
                <DetectionBox key={item.id} item={item}
                  drawProgress={drawProgress} labelProgress={labelProgress} palette={palette} subject={subject} />
              );
            })}
          </g>
        );
      })()}

      {/* Right pane label (appears as items start arriving) */}
      {t > INTRO_DURATION + 4.0 && (
        <foreignObject x={660} y={56} width="600" height="30" opacity={Easing.easeOutQuad(clamp((t - INTRO_DURATION - 4.0) / 0.6, 0, 1))}>
          <div xmlns="http://www.w3.org/1999/xhtml" style={{
            fontFamily: "'Super Sans VF', sans-serif", fontSize: 13, fontWeight: 540,
            color: palette.textSubdued, letterSpacing: 0.3, textTransform: "uppercase",
          }}>
            {t < postedStart ? "Drafting listings" : "Live on eBay"}
          </div>
        </foreignObject>
      )}

      {/* Flying / docked items */}
      {items.map((item) => (
        <ItemSprite key={item.id} item={item} target={item.target} t={t}
          palette={palette}
          posted={isPosted(item)} postedAt={item.timing.postedAt}
          layoutMode={layoutMode} subject={subject} />
      ))}

      {/* Posted counter (appears at end) */}
      <PostedCounter count={items.length} t={t} postedStart={postedStart} palette={palette} />

      {/* Cursor flyover with tooltip — featured listing close-up */}
      <CursorTooltip t={t} items={items} palette={palette} postedStart={postedStart} />

      {/* End-frame summary card — bottom of right pane */}
      <EndFrameSummary t={t} items={items} palette={palette} postedStart={postedStart} />
    </svg>
  );
}

// HeroAnimation — self-contained wrapper that owns the Stage and guarantees
// every mount starts the timeline at t=0 (avoids Stage's localStorage resume).
function HeroAnimation({
  subjectKey = "realDesk",
  layoutMode = "single",
  explodeStyle = "arc",
  dark = false,
  replayKey = 0,
  duration = 17,
  width = 1280,
  height = 720,
}) {
  const persistKey = React.useMemo(
    () => `ebop-hero-${Date.now()}-${Math.random().toString(36).slice(2)}`,
    [replayKey, subjectKey, layoutMode, explodeStyle, dark]
  );
  return (
    <Stage
      key={persistKey}
      width={width}
      height={height}
      duration={duration}
      loop={false}
      autoplay={true}
      persistKey={persistKey}
      background={dark ? "#141413" : "#fcfaf7"}
    >
      <HeroScene
        subjectKey={subjectKey}
        layoutMode={layoutMode}
        explodeStyle={explodeStyle}
        dark={dark}
      />
    </Stage>
  );
}

export { HeroScene, HeroAnimation }
