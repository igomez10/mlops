import { PostList } from './components/PostList'
import './App.css'

function App() {
  return (
    <div className="app">
      <header className="hero">
        <div className="hero-inner">
          <nav className="hero-nav">
            <div className="hero-nav-brand" aria-label="eBay Operator">
              <svg viewBox="0 0 32 32" width="22" height="22" focusable="false" aria-hidden="true">
                <path
                  d="M6 9h3l1.2-1.5h8.6L20 9h3a2.5 2.5 0 012.5 2.5V22A2.5 2.5 0 0123 24.5H6A2.5 2.5 0 013.5 22V11.5A2.5 2.5 0 016 9z"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.7"
                  strokeLinejoin="round"
                />
                <circle cx="14.5" cy="16.5" r="4.5" fill="none" stroke="currentColor" strokeWidth="1.7" />
              </svg>
              <span>eBay Operator</span>
            </div>
            <button className="hero-nav-signin" type="button">Sign in</button>
          </nav>
          <div className="hero-body">
          <div className="hero-text">
            <p className="hero-eyebrow">AI-powered bulk listing</p>
            <h1 className="hero-title">
              One photo.<br />
              <span className="hero-accent">Dozens</span> of listings.
            </h1>
            <p className="hero-subtitle">
              Moving house? Clearing a garage? Snap everything in one shot —
              our AI finds each item, writes the listing, and puts it on eBay.
              You don't lift another finger.
            </p>
            <div className="how-it-works">
              <div className="how-step">
                <span className="how-step-number" aria-hidden="true">1</span>
                <div className="how-step-text">
                  <strong>One photo</strong>
                  <span>Lay items on any surface and photograph them together</span>
                </div>
              </div>
              <div className="how-step">
                <span className="how-step-number" aria-hidden="true">2</span>
                <div className="how-step-text">
                  <strong>AI detects each item</strong>
                  <span>We isolate, identify, and describe every object we find</span>
                </div>
              </div>
              <div className="how-step">
                <span className="how-step-number" aria-hidden="true">3</span>
                <div className="how-step-text">
                  <strong>Listings go live</strong>
                  <span>Separate, optimised eBay listings — ready in under a minute</span>
                </div>
              </div>
            </div>
          </div>
          <div className="hero-icon" aria-hidden="true">
            <svg viewBox="0 0 32 32" width="52" height="52" focusable="false">
              <path
                d="M6 9h3l1.2-1.5h8.6L20 9h3a2.5 2.5 0 012.5 2.5V22A2.5 2.5 0 0123 24.5H6A2.5 2.5 0 013.5 22V11.5A2.5 2.5 0 016 9z"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.6"
                strokeLinejoin="round"
              />
              <circle
                cx="14.5"
                cy="16.5"
                r="4.5"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.6"
              />
              <path
                d="M22 8v1.2h2.3c.2 0 .3.1.3.2l.1.2v.5"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.2"
                strokeLinecap="round"
              />
            </svg>
          </div>
          </div>{/* hero-body */}
        </div>{/* hero-inner */}
      </header>

      <div className="page-content">
      {/* Stats strip */}
      <div className="stats-strip">
        <div className="stat-item">
          <span className="stat-number">20+</span>
          <span className="stat-label">items detected per photo</span>
        </div>
        <div className="stat-divider" aria-hidden="true" />
        <div className="stat-item">
          <span className="stat-number">&lt; 60s</span>
          <span className="stat-label">from upload to listings</span>
        </div>
        <div className="stat-divider" aria-hidden="true" />
        <div className="stat-item">
          <span className="stat-number">3 hrs</span>
          <span className="stat-label">saved vs. listing manually</span>
        </div>
      </div>

      {/* Demo visual section */}
      <section className="demo-section">
        <div className="demo-header">
          <p className="demo-eyebrow">See it in action</p>
          <h2 className="demo-title">One scan. Many listings.</h2>
          <p className="demo-desc">
            A seller clearing a spare room snapped one photo of their shelves.
            Our AI detected 5 items and generated draft listings in 48 seconds.
          </p>
        </div>
        <div className="demo-flow">
          {/* Left: single photo with AI detection boxes overlaid */}
          <div className="demo-photo-side">
            <p className="demo-side-label">
              <span className="demo-side-badge">Your photo</span>
              1 image uploaded
            </p>
            <div className="demo-photo" role="img" aria-label="One photo containing multiple items with AI detection boxes">
              <div className="demo-item demo-item-1">
                <span className="demo-item-tag" aria-hidden="true">1</span>
                <span className="demo-item-name">Vintage Clock</span>
              </div>
              <div className="demo-item demo-item-2">
                <span className="demo-item-tag" aria-hidden="true">2</span>
                <span className="demo-item-name">Ceramic Figurine</span>
              </div>
              <div className="demo-item demo-item-3">
                <span className="demo-item-tag" aria-hidden="true">3</span>
                <span className="demo-item-name">Bronze Statue</span>
              </div>
              <div className="demo-item demo-item-4">
                <span className="demo-item-tag" aria-hidden="true">4</span>
                <span className="demo-item-name">Decorative Trinkets</span>
              </div>
              <div className="demo-item demo-item-5">
                <span className="demo-item-tag" aria-hidden="true">5</span>
                <span className="demo-item-name">Antique Vase</span>
              </div>
            </div>
          </div>

          {/* Center arrow */}
          <div className="demo-arrow" aria-hidden="true">
            <svg viewBox="0 0 40 24" width="40" height="24" fill="none">
              <path d="M0 12 H34 M26 4 L34 12 L26 20" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            <span>AI detects</span>
          </div>

          {/* Right: generated listing cards — thumbnails cropped from the same photo */}
          <div className="demo-cards-side">
            <p className="demo-side-label">
              <span className="demo-side-badge demo-side-badge--green">Listings generated</span>
              5 draft listings created
            </p>
            <div className="demo-cards">
              <div className="demo-card">
                <img className="demo-card-img" style={{ objectPosition: '15% 20%' }} src="https://images.unsplash.com/photo-1560697043-f880bb028f1e?auto=format&fit=crop&w=120&q=80" alt="Vintage Clock" />
                <div className="demo-card-body">
                  <span className="demo-card-badge">Draft</span>
                  <p className="demo-card-name">Vintage Clock</p>
                  <p className="demo-card-price">Est. $55–80</p>
                </div>
              </div>
              <div className="demo-card">
                <img className="demo-card-img" style={{ objectPosition: '70% 25%' }} src="https://images.unsplash.com/photo-1560697043-f880bb028f1e?auto=format&fit=crop&w=120&q=80" alt="Ceramic Figurine" />
                <div className="demo-card-body">
                  <span className="demo-card-badge">Draft</span>
                  <p className="demo-card-name">Ceramic Figurine</p>
                  <p className="demo-card-price">Est. $30–45</p>
                </div>
              </div>
              <div className="demo-card">
                <img className="demo-card-img" style={{ objectPosition: '40% 70%' }} src="https://images.unsplash.com/photo-1560697043-f880bb028f1e?auto=format&fit=crop&w=120&q=80" alt="Bronze Statue" />
                <div className="demo-card-body">
                  <span className="demo-card-badge">Draft</span>
                  <p className="demo-card-name">Bronze Statue</p>
                  <p className="demo-card-price">Est. $40–60</p>
                </div>
              </div>
              <div className="demo-card">
                <img className="demo-card-img" style={{ objectPosition: '80% 65%' }} src="https://images.unsplash.com/photo-1560697043-f880bb028f1e?auto=format&fit=crop&w=120&q=80" alt="Decorative Trinkets" />
                <div className="demo-card-body">
                  <span className="demo-card-badge">Draft</span>
                  <p className="demo-card-name">Decorative Trinkets</p>
                  <p className="demo-card-price">Est. $18–28</p>
                </div>
              </div>
              <div className="demo-card demo-card--more">
                <p className="demo-card-more-num">+1</p>
                <p className="demo-card-more-text">more listing</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Use cases */}
      <section className="use-cases-section">
        <p className="demo-eyebrow use-cases-eyebrow">Built for sellers who need speed</p>
        <div className="use-cases-grid">
          <div className="use-case-card">
            <div className="use-case-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>
                <polyline points="3.27 6.96 12 12.01 20.73 6.96"/>
                <line x1="12" y1="22.08" x2="12" y2="12"/>
              </svg>
            </div>
            <h3 className="use-case-title">Cross-country move</h3>
            <p className="use-case-body">
              Can't fit everything in the truck? Walk room to room, snap each shelf or pile,
              and sell everything you're leaving behind — without burning a whole weekend on listings.
            </p>
            <p className="use-case-example">"I listed 60 items from 4 photos before the movers arrived."</p>
          </div>
          <div className="use-case-card">
            <div className="use-case-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
                <line x1="3" y1="9" x2="21" y2="9"/>
                <line x1="9" y1="21" x2="9" y2="9"/>
              </svg>
            </div>
            <h3 className="use-case-title">Garage cleanout</h3>
            <p className="use-case-body">
              Spread everything across the driveway, take three photos, and we'll turn
              your pile of stuff into a row of live eBay listings. Most sellers are done
              before lunch.
            </p>
            <p className="use-case-example">"20+ listings from one photo of my workbench alone."</p>
          </div>
          <div className="use-case-card">
            <div className="use-case-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
                <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
                <polyline points="9 22 9 12 15 12 15 22"/>
              </svg>
            </div>
            <h3 className="use-case-title">Estate &amp; inheritance</h3>
            <p className="use-case-body">
              Clearing a relative's home is already hard. Let us handle the eBay side —
              photograph rooms in bulk and we'll generate listings for every sellable item
              we find, with descriptions written for you.
            </p>
            <p className="use-case-example">"Cleared an entire attic in two sessions."</p>
          </div>
        </div>
      </section>

      <main className="app-main">
        <div className="app-panel">
          <PostList />
        </div>
      </main>
      </div>{/* page-content */}
    </div>
  )
}

export default App
