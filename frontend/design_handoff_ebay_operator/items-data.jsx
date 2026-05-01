// items-data.jsx
// Three "subject" scenes (desk / garage / closet). Each item has:
//   - id, name, price, condition, category
//   - source rect within the photo (x, y, w, h in 0..1 photo coords)
//   - an SVG illustration component
//
// Item SVGs are intentionally clean line-art on a solid tile so they read at any size.

// ── Drawing helpers ─────────────────────────────────────────────────────────
const ItemTile = ({ bg, children }) => (
  <svg viewBox="0 0 100 100" preserveAspectRatio="xMidYMid meet" style={{ width: "100%", height: "100%", display: "block" }}>
    <rect width="100" height="100" fill={bg} />
    {children}
  </svg>
);

// ── Desk items (electronics, books, knick-knacks) ───────────────────────────
const Headphones = () => (
  <ItemTile bg="#f0ece4">
    <g stroke="#141413" strokeWidth="2.2" fill="none" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 56 Q 22 26 50 26 Q 78 26 78 56" />
      <rect x="14" y="52" width="14" height="26" rx="5" fill="#1a1a1a" />
      <rect x="72" y="52" width="14" height="26" rx="5" fill="#1a1a1a" />
    </g>
  </ItemTile>
);

const Camera = () => (
  <ItemTile bg="#e8e2d4">
    <g stroke="#141413" strokeWidth="2" fill="#2a2a2a" strokeLinejoin="round">
      <rect x="14" y="34" width="72" height="44" rx="5" />
      <rect x="40" y="26" width="20" height="10" fill="#2a2a2a" />
      <circle cx="50" cy="56" r="14" fill="#0a0a0a" stroke="#141413" />
      <circle cx="50" cy="56" r="8" fill="#1a1a1a" />
      <circle cx="50" cy="56" r="3" fill="#3a3a3a" stroke="none" />
      <circle cx="74" cy="42" r="2" fill="#cd0037" stroke="none" />
    </g>
  </ItemTile>
);

const Book = () => (
  <ItemTile bg="#efe7d7">
    <g stroke="#141413" strokeWidth="1.8" strokeLinejoin="round">
      <rect x="22" y="18" width="56" height="64" fill="#714cb6" />
      <rect x="22" y="18" width="6" height="64" fill="#3f256f" />
      <line x1="34" y1="32" x2="70" y2="32" stroke="#fff" strokeWidth="2" />
      <line x1="34" y1="40" x2="62" y2="40" stroke="#fff" strokeWidth="2" />
      <line x1="34" y1="64" x2="58" y2="64" stroke="#fff" strokeWidth="1.5" opacity="0.6" />
    </g>
  </ItemTile>
);

const Mug = () => (
  <ItemTile bg="#ede5d2">
    <g stroke="#141413" strokeWidth="2" fill="#fcfaf7" strokeLinejoin="round">
      <rect x="26" y="28" width="38" height="48" rx="3" />
      <path d="M64 38 Q 78 38 78 52 Q 78 66 64 66" fill="none" />
      <rect x="26" y="28" width="38" height="6" fill="#cd0037" stroke="none" />
    </g>
  </ItemTile>
);

const Watch = () => (
  <ItemTile bg="#f2ecdd">
    <g stroke="#141413" strokeWidth="2" fill="none" strokeLinejoin="round">
      <rect x="36" y="14" width="28" height="14" fill="#5a4a3a" />
      <rect x="36" y="72" width="28" height="14" fill="#5a4a3a" />
      <rect x="30" y="28" width="40" height="44" rx="6" fill="#1a1a1a" />
      <circle cx="50" cy="50" r="13" fill="#fcfaf7" />
      <line x1="50" y1="50" x2="50" y2="42" strokeWidth="1.5" />
      <line x1="50" y1="50" x2="56" y2="50" strokeWidth="1.5" />
    </g>
  </ItemTile>
);

const Keyboard = () => (
  <ItemTile bg="#ebe3d2">
    <g stroke="#141413" strokeWidth="1.5" fill="#1a1a1a">
      <rect x="10" y="36" width="80" height="28" rx="3" />
      <g fill="#3a3a3a" stroke="none">
        {[14, 22, 30, 38, 46, 54, 62, 70, 78].map((x, i) => (
          <rect key={i} x={x} y={40} width="6" height="6" rx="1" />
        ))}
        {[14, 22, 30, 38, 46, 54, 62, 70, 78].map((x, i) => (
          <rect key={"b"+i} x={x} y={48} width="6" height="6" rx="1" />
        ))}
        <rect x="22" y="56" width="56" height="5" rx="1" />
      </g>
    </g>
  </ItemTile>
);

const Lamp = () => (
  <ItemTile bg="#efe7d4">
    <g stroke="#141413" strokeWidth="2" fill="#2a2a2a" strokeLinejoin="round">
      <path d="M30 30 L 70 30 L 60 50 L 40 50 Z" fill="#ffbf47" />
      <line x1="50" y1="50" x2="50" y2="78" strokeWidth="2.5" />
      <ellipse cx="50" cy="82" rx="18" ry="4" fill="#2a2a2a" />
    </g>
  </ItemTile>
);

const Plant = () => (
  <ItemTile bg="#e8e7d8">
    <g stroke="#141413" strokeWidth="2" strokeLinejoin="round">
      <path d="M50 60 Q 30 40 26 22 Q 38 26 46 40 Q 50 24 50 14 Q 56 26 54 44 Q 64 34 74 24 Q 70 46 54 58" fill="#005c54" />
      <path d="M30 60 L 70 60 L 64 84 L 36 84 Z" fill="#bd5200" />
    </g>
  </ItemTile>
);

// ── Garage items ────────────────────────────────────────────────────────────
const Drill = () => (
  <ItemTile bg="#e6dec8">
    <g stroke="#141413" strokeWidth="2" strokeLinejoin="round">
      <rect x="14" y="36" width="46" height="22" rx="4" fill="#ffbf47" />
      <rect x="56" y="42" width="28" height="10" fill="#1a1a1a" />
      <rect x="80" y="40" width="6" height="14" fill="#8d8a86" />
      <rect x="22" y="58" width="22" height="22" rx="3" fill="#1a1a1a" />
    </g>
  </ItemTile>
);

const Helmet = () => (
  <ItemTile bg="#ebe3cf">
    <g stroke="#141413" strokeWidth="2" strokeLinejoin="round">
      <path d="M22 64 Q 22 26 50 22 Q 78 26 78 64 Z" fill="#cd0037" />
      <path d="M22 64 L 78 64 L 78 70 L 22 70 Z" fill="#1a1a1a" />
      <line x1="34" y1="36" x2="66" y2="36" />
      <line x1="30" y1="48" x2="70" y2="48" />
    </g>
  </ItemTile>
);

const ToolBox = () => (
  <ItemTile bg="#e6dfca">
    <g stroke="#141413" strokeWidth="2" strokeLinejoin="round">
      <rect x="16" y="34" width="68" height="42" fill="#cd0037" />
      <rect x="16" y="34" width="68" height="8" fill="#9f182d" />
      <path d="M36 34 Q 36 22 50 22 Q 64 22 64 34" fill="none" />
      <rect x="44" y="52" width="12" height="8" fill="#1a1a1a" />
    </g>
  </ItemTile>
);

const Bike = () => (
  <ItemTile bg="#e8e1cb">
    <g stroke="#141413" strokeWidth="2" fill="none" strokeLinejoin="round">
      <circle cx="26" cy="62" r="14" fill="#1a1a1a" />
      <circle cx="74" cy="62" r="14" fill="#1a1a1a" />
      <circle cx="26" cy="62" r="5" fill="#fcfaf7" />
      <circle cx="74" cy="62" r="5" fill="#fcfaf7" />
      <path d="M26 62 L 50 38 L 74 62 L 50 62 Z" stroke="#005c54" strokeWidth="3" />
      <line x1="50" y1="38" x2="58" y2="26" strokeWidth="2.5" />
      <path d="M54 26 L 66 26" strokeWidth="2.5" />
    </g>
  </ItemTile>
);

const Boots = () => (
  <ItemTile bg="#ede5d0">
    <g stroke="#141413" strokeWidth="2" fill="#5a3a1a" strokeLinejoin="round">
      <path d="M22 30 L 36 30 L 36 64 L 58 64 L 58 76 L 22 76 Z" />
      <rect x="22" y="72" width="40" height="6" fill="#1a1a1a" />
      <line x1="28" y1="38" x2="32" y2="38" stroke="#fcfaf7" strokeWidth="1.5" />
      <line x1="28" y1="46" x2="32" y2="46" stroke="#fcfaf7" strokeWidth="1.5" />
      <line x1="28" y1="54" x2="32" y2="54" stroke="#fcfaf7" strokeWidth="1.5" />
    </g>
  </ItemTile>
);

const PaintCan = () => (
  <ItemTile bg="#e6dfc8">
    <g stroke="#141413" strokeWidth="2" strokeLinejoin="round">
      <rect x="28" y="30" width="44" height="48" fill="#fcfaf7" />
      <ellipse cx="50" cy="30" rx="22" ry="4" fill="#dedbd5" />
      <path d="M28 38 Q 50 28 72 38" fill="none" />
      <rect x="38" y="48" width="24" height="14" fill="#714cb6" />
    </g>
  </ItemTile>
);

const Wrench = () => (
  <ItemTile bg="#e9e1ca">
    <g stroke="#141413" strokeWidth="2" fill="#8d8a86" strokeLinejoin="round">
      <path d="M22 30 L 32 20 L 38 26 L 30 34 L 36 40 L 70 74 L 78 66 L 84 72 L 74 82 Z" />
      <circle cx="30" cy="28" r="4" fill="#e9e1ca" />
    </g>
  </ItemTile>
);

const Skateboard = () => (
  <ItemTile bg="#e9e1ca">
    <g stroke="#141413" strokeWidth="2" strokeLinejoin="round">
      <ellipse cx="50" cy="50" rx="38" ry="9" fill="#714cb6" />
      <circle cx="22" cy="60" r="5" fill="#1a1a1a" />
      <circle cx="78" cy="60" r="5" fill="#1a1a1a" />
      <line x1="20" y1="50" x2="80" y2="50" stroke="#fcfaf7" strokeWidth="1.5" opacity="0.5" />
    </g>
  </ItemTile>
);

// ── Closet items ────────────────────────────────────────────────────────────
const Jacket = () => (
  <ItemTile bg="#ece4d0">
    <g stroke="#141413" strokeWidth="2" strokeLinejoin="round">
      <path d="M30 22 L 50 16 L 70 22 L 80 32 L 76 44 L 70 40 L 70 82 L 30 82 L 30 40 L 24 44 L 20 32 Z" fill="#1b0d6f" />
      <line x1="50" y1="20" x2="50" y2="80" stroke="#fcfaf7" strokeWidth="1.5" />
      <circle cx="50" cy="40" r="1.5" fill="#fcfaf7" stroke="none" />
      <circle cx="50" cy="55" r="1.5" fill="#fcfaf7" stroke="none" />
      <circle cx="50" cy="70" r="1.5" fill="#fcfaf7" stroke="none" />
    </g>
  </ItemTile>
);

const Sneakers = () => (
  <ItemTile bg="#ede5d2">
    <g stroke="#141413" strokeWidth="2" strokeLinejoin="round">
      <path d="M14 60 Q 14 50 28 50 L 50 46 L 70 54 Q 86 56 86 64 L 86 72 L 14 72 Z" fill="#fcfaf7" />
      <path d="M28 50 L 36 56 L 50 46" fill="none" />
      <rect x="14" y="68" width="72" height="6" fill="#cd0037" stroke="none" />
    </g>
  </ItemTile>
);

const Dress = () => (
  <ItemTile bg="#ece4d0">
    <g stroke="#141413" strokeWidth="2" strokeLinejoin="round">
      <path d="M36 18 L 64 18 L 70 28 L 60 32 L 60 46 L 78 84 L 22 84 L 40 46 L 40 32 L 30 28 Z" fill="#cd0037" />
      <path d="M40 32 L 60 32" fill="none" />
    </g>
  </ItemTile>
);

const Hat = () => (
  <ItemTile bg="#ece4d0">
    <g stroke="#141413" strokeWidth="2" strokeLinejoin="round">
      <ellipse cx="50" cy="62" rx="36" ry="6" fill="#5a3a1a" />
      <path d="M28 62 Q 28 30 50 30 Q 72 30 72 62" fill="#5a3a1a" />
      <rect x="28" y="56" width="44" height="6" fill="#1a1a1a" />
    </g>
  </ItemTile>
);

const Bag = () => (
  <ItemTile bg="#ede5d2">
    <g stroke="#141413" strokeWidth="2" strokeLinejoin="round">
      <path d="M30 36 Q 30 22 50 22 Q 70 22 70 36" fill="none" />
      <rect x="20" y="36" width="60" height="48" rx="3" fill="#5a3a1a" />
      <rect x="44" y="50" width="12" height="8" fill="#ffbf47" stroke="none" />
    </g>
  </ItemTile>
);

const Sunglasses = () => (
  <ItemTile bg="#ece4d0">
    <g stroke="#141413" strokeWidth="2" strokeLinejoin="round">
      <ellipse cx="32" cy="50" rx="14" ry="11" fill="#1a1a1a" />
      <ellipse cx="68" cy="50" rx="14" ry="11" fill="#1a1a1a" />
      <line x1="46" y1="50" x2="54" y2="50" />
    </g>
  </ItemTile>
);

const Scarf = () => (
  <ItemTile bg="#ece4d0">
    <g stroke="#141413" strokeWidth="2" strokeLinejoin="round">
      <path d="M20 30 L 80 30 L 70 76 L 50 70 L 30 76 Z" fill="#714cb6" />
      <line x1="30" y1="42" x2="70" y2="42" stroke="#fcfaf7" strokeWidth="1.5" />
      <line x1="32" y1="54" x2="68" y2="54" stroke="#fcfaf7" strokeWidth="1.5" />
    </g>
  </ItemTile>
);

const Belt = () => (
  <ItemTile bg="#ece4d0">
    <g stroke="#141413" strokeWidth="2" strokeLinejoin="round">
      <rect x="14" y="42" width="60" height="14" fill="#3a2a1a" />
      <rect x="74" y="38" width="14" height="22" fill="#ffbf47" />
      <rect x="78" y="44" width="6" height="10" fill="#3a2a1a" />
    </g>
  </ItemTile>
);

// ── Photo-tile component ────────────────────────────────────────────────────
// Renders a cropped region of a real photo as a tile with cover-style sizing
// (preserves aspect, fills the tile, slight crop on the longer axis if needed).
//
// Implementation: at mount, draw the rect from the photo onto an offscreen
// canvas at its natural pixel aspect ratio, export to a data URL, and use it
// as a normal `background-size: cover, center` image. This avoids the
// background-position trickery that was distorting aspect ratios.

const _cropCache = new Map();
function cropKey(photo, rect, rotate) {
  return photo + "|" + rect.join(",") + "|" + (rotate || 0);
}

const PhotoTile = ({ photo, rect, bg, rotate = 180, fit = "cover", pad = null }) => {
  const [src, setSrc] = React.useState(() => _cropCache.get(cropKey(photo, rect, rotate) + "|" + JSON.stringify(pad || {})) || null);

  React.useEffect(() => {
    const padKey = JSON.stringify(pad || {});
    const key = cropKey(photo, rect, rotate) + "|" + padKey;
    if (_cropCache.has(key)) { setSrc(_cropCache.get(key)); return; }
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => {
      const [rx, ry, rw, rh] = rect;
      const sx = rx * img.naturalWidth;
      const sy = ry * img.naturalHeight;
      const sw = rw * img.naturalWidth;
      const sh = rh * img.naturalHeight;
      // Padding: bg-colored borders added to one or more sides of the crop
      // (to visually re-center an item that's against the photo edge).
      // Padding values are fractions of the source rect's dimensions.
      const p = pad || {};
      const padL = (p.left || 0) * sw;
      const padR = (p.right || 0) * sw;
      const padT = (p.top || 0) * sh;
      const padB = (p.bottom || 0) * sh;
      const totalW = sw + padL + padR;
      const totalH = sh + padT + padB;
      const maxDim = 600;
      const scale = Math.min(1, maxDim / Math.max(totalW, totalH));
      const cw = Math.max(1, Math.round(totalW * scale));
      const ch = Math.max(1, Math.round(totalH * scale));
      const canvas = document.createElement("canvas");
      canvas.width = cw; canvas.height = ch;
      const ctx = canvas.getContext("2d");
      // Fill with bg color first (so padding shows the desk surface)
      ctx.fillStyle = bg || "#d9d0bb";
      ctx.fillRect(0, 0, cw, ch);
      if (rotate === 180) {
        ctx.translate(cw, ch);
        ctx.rotate(Math.PI);
        // After rotation, padded-left becomes padded-right visually, etc.
        // Draw the photo crop into the rect-sized region, offset by the
        // pre-rotation padL/padT (in original orientation).
        ctx.drawImage(img, sx, sy, sw, sh, padL * scale, padT * scale, sw * scale, sh * scale);
      } else {
        ctx.drawImage(img, sx, sy, sw, sh, padL * scale, padT * scale, sw * scale, sh * scale);
      }
      try {
        const url = canvas.toDataURL("image/jpeg", 0.85);
        _cropCache.set(key, url);
        setSrc(url);
      } catch (e) {
        _cropCache.set(key, photo);
        setSrc(photo);
      }
    };
    img.onerror = () => setSrc(null);
    img.src = photo;
  }, [photo, rect[0], rect[1], rect[2], rect[3], rotate, JSON.stringify(pad || {})]);

  return (
    <div style={{
      width: "100%", height: "100%",
      backgroundColor: bg || "#d9d0bb",
      backgroundImage: src ? `url("${src}")` : undefined,
      backgroundSize: fit,
      backgroundPosition: "center",
      backgroundRepeat: "no-repeat",
    }} />
  );
};

window.PhotoTile = PhotoTile;

// ── Subject definitions ─────────────────────────────────────────────────────
// Coordinates are normalized to the photo (0..1, x then y, then w then h).
// Items overlap & vary in size to feel like a real cluttered scene.

// Helper: build a Comp from a photo + rect for items in a real-photo subject.
// Optional `fit` overrides cover/contain. Returns a component that accepts
// per-render props (so callers can override fit per usage).
const photoComp = (photo, rect, bg, pad) => (props = {}) =>
  <PhotoTile photo={photo} rect={rect} bg={bg} pad={pad} {...props} />;

const REAL_DESK_PHOTO = "assets/desk-photo.jpg";
const REAL_DESK_BG = "#d9d3c6"; // desk surface color sampled from photo

const SUBJECTS = {
  realDesk: {
    label: "My desk",
    bg: REAL_DESK_BG,
    floor: REAL_DESK_BG,
    photo: REAL_DESK_PHOTO,
    rotate: 180,
    aspect: 16 / 9,
    items: [
      // Rects are in ORIGINAL photo coordinates (top-left of file). Photo is
      // displayed rotated 180° so items appear right-side-up; the rendering
      // code (rectInPhoto) flips coords for detection-box positions.
      { id: "notebook",
        name: "Moleskine Classic Hardcover Notebook, Large",
        price: 18, condition: "Used – Like New", category: "Stationery",
        rect: [0.085, 0.030, 0.205, 0.585],
        get Comp() { return photoComp(REAL_DESK_PHOTO, this.rect, REAL_DESK_BG); } },
      { id: "macbook",
        name: "Apple MacBook Pro 14\" M3, Silver, 16GB / 512GB",
        price: 1450, condition: "Used – Excellent", category: "Computers",
        rect: [0.325, 0.000, 0.445, 0.605],
        get Comp() { return photoComp(REAL_DESK_PHOTO, this.rect, REAL_DESK_BG); } },
      { id: "watch",
        name: "Samsung Galaxy Watch, Black Sport Band, 44mm",
        price: 165, condition: "Used – Good", category: "Watches",
        rect: [0.850, 0.040, 0.150, 0.770],
        // Watch is at the right edge of the photo; pad the un-rotated left
        // (= visible right after 180° rotation) with bg so the watch
        // appears centered in its tile.
        pad: { left: 0.4 },
        get Comp() { return photoComp(REAL_DESK_PHOTO, this.rect, REAL_DESK_BG, this.pad); } },
      { id: "trackpad",
        name: "Apple Magic Trackpad 2, Silver, Wireless",
        price: 78, condition: "Used – Good", category: "Computer Accessories",
        rect: [0.060, 0.640, 0.235, 0.295],
        get Comp() { return photoComp(REAL_DESK_PHOTO, this.rect, REAL_DESK_BG); } },
      { id: "keyboard",
        name: "Custom 75% Mechanical Keyboard, Orange & Green Keycaps",
        price: 220, condition: "Used – Good", category: "Computer Accessories",
        rect: [0.305, 0.625, 0.570, 0.370],
        get Comp() { return photoComp(REAL_DESK_PHOTO, this.rect, REAL_DESK_BG); } },
    ],
  },
  desk: {
    label: "Cluttered desk",
    bg: "#d9d0bb",   // warm wood/desk surface
    floor: "#c4b89c",
    items: [
      { id: "headphones", name: "Sony WH-1000XM4 Wireless Headphones", price: 149, condition: "Used – Excellent", category: "Electronics", rect: [0.05, 0.18, 0.22, 0.30], Comp: Headphones },
      { id: "camera",     name: "Canon EOS M50 Mirrorless Camera",     price: 389, condition: "Used – Good",      category: "Cameras",     rect: [0.30, 0.10, 0.22, 0.26], Comp: Camera },
      { id: "book",       name: "Hardcover Atlas Shrugged 1st Edition",price: 24,  condition: "Used – Acceptable",category: "Books",       rect: [0.55, 0.14, 0.13, 0.32], Comp: Book },
      { id: "mug",        name: "Vintage Ceramic Mug, Red Stripe",     price: 12,  condition: "Used – Good",      category: "Home",        rect: [0.72, 0.20, 0.16, 0.22], Comp: Mug },
      { id: "watch",      name: "Casio Vintage Wristwatch",            price: 38,  condition: "Pre-owned",        category: "Watches",     rect: [0.06, 0.55, 0.16, 0.22], Comp: Watch },
      { id: "keyboard",   name: "Mechanical Keyboard, Cherry MX Brown",price: 78,  condition: "Used – Good",      category: "Computers",   rect: [0.26, 0.55, 0.32, 0.18], Comp: Keyboard },
      { id: "lamp",       name: "Mid-Century Brass Desk Lamp",         price: 45,  condition: "Used – Good",      category: "Home",        rect: [0.62, 0.50, 0.16, 0.34], Comp: Lamp },
      { id: "plant",      name: "Terracotta Succulent Planter",        price: 18,  condition: "New",              category: "Garden",      rect: [0.81, 0.50, 0.15, 0.32], Comp: Plant },
    ],
  },
  garage: {
    label: "Garage shelf",
    bg: "#cabd9b",
    floor: "#b3a583",
    items: [
      { id: "drill",      name: "DEWALT 20V Cordless Drill",         price: 89,  condition: "Used – Good",      category: "Tools",     rect: [0.04, 0.12, 0.24, 0.26], Comp: Drill },
      { id: "helmet",     name: "Bell Bicycle Helmet, Adult Medium", price: 28,  condition: "Used – Like New",  category: "Sports",    rect: [0.32, 0.10, 0.20, 0.26], Comp: Helmet },
      { id: "toolbox",    name: "Stanley 19-inch Toolbox",           price: 32,  condition: "Used – Good",      category: "Tools",     rect: [0.56, 0.10, 0.22, 0.30], Comp: ToolBox },
      { id: "wrench",     name: "Crescent 10\" Adjustable Wrench",   price: 14,  condition: "Used – Acceptable",category: "Tools",     rect: [0.80, 0.16, 0.18, 0.18], Comp: Wrench },
      { id: "bike",       name: "Trek Mountain Bike Frame, 26\"",    price: 240, condition: "Used – Good",      category: "Sports",    rect: [0.04, 0.50, 0.28, 0.30], Comp: Bike },
      { id: "boots",      name: "Red Wing Work Boots, Size 11",      price: 95,  condition: "Used – Good",      category: "Apparel",   rect: [0.34, 0.55, 0.20, 0.28], Comp: Boots },
      { id: "paint",      name: "Behr Premium Plus, 1 Gallon",       price: 18,  condition: "New",              category: "Home",      rect: [0.58, 0.52, 0.16, 0.30], Comp: PaintCan },
      { id: "skateboard", name: "Vintage Penny Skateboard",          price: 44,  condition: "Used – Good",      category: "Sports",    rect: [0.76, 0.58, 0.22, 0.20], Comp: Skateboard },
    ],
  },
  closet: {
    label: "Closet & wardrobe",
    bg: "#d6cbb3",
    floor: "#bfb295",
    items: [
      { id: "jacket",     name: "Patagonia Down Jacket, Men's M",    price: 120, condition: "Used – Like New",  category: "Apparel",   rect: [0.04, 0.08, 0.22, 0.38], Comp: Jacket },
      { id: "dress",      name: "Vintage Red Cocktail Dress, Sz 6",  price: 58,  condition: "Used – Good",      category: "Apparel",   rect: [0.30, 0.08, 0.22, 0.40], Comp: Dress },
      { id: "hat",        name: "Stetson Felt Cowboy Hat, Brown",    price: 64,  condition: "Used – Good",      category: "Apparel",   rect: [0.56, 0.10, 0.22, 0.22], Comp: Hat },
      { id: "scarf",      name: "Cashmere Scarf, Hand-Woven",        price: 36,  condition: "Used – Good",      category: "Apparel",   rect: [0.80, 0.12, 0.16, 0.30], Comp: Scarf },
      { id: "sneakers",   name: "Nike Air Max 90, Size 10",          price: 78,  condition: "Used – Good",      category: "Apparel",   rect: [0.04, 0.55, 0.24, 0.22], Comp: Sneakers },
      { id: "bag",        name: "Leather Messenger Bag, Cognac",     price: 92,  condition: "Used – Good",      category: "Bags",      rect: [0.32, 0.50, 0.20, 0.32], Comp: Bag },
      { id: "sunglasses", name: "Ray-Ban Wayfarer, Classic Black",   price: 68,  condition: "Pre-owned",        category: "Apparel",   rect: [0.56, 0.56, 0.20, 0.18], Comp: Sunglasses },
      { id: "belt",       name: "Italian Leather Belt, Sz 36",       price: 24,  condition: "Used – Good",      category: "Apparel",   rect: [0.78, 0.58, 0.20, 0.16], Comp: Belt },
    ],
  },
};

window.SUBJECTS = SUBJECTS;
