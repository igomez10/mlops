import { useEffect } from 'react'
import { HeroAnimation } from '../hero/hero-scene'

export default function WelcomePage() {
  useEffect(() => {
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) { e.target.classList.add('in-view'); io.unobserve(e.target) }
        })
      },
      { threshold: 0.1 }
    )
    document.querySelectorAll('.reveal').forEach((el) => io.observe(el))
    return () => io.disconnect()
  }, [])

  return (
    <div className="app">
      <header className="hero">
        <div className="hero-inner">
          {/* ambient glow blobs — inside sticky inner so they stay visible on scroll */}
          <div className="hero-glow-1" aria-hidden="true" />
          <div className="hero-glow-2" aria-hidden="true" />
          <nav className="hero-nav">
            <div className="hero-nav-brand" aria-label="eBay Operator">
              <div className="hero-nav-brand-icon">
                <svg viewBox="0 0 32 32" width="26" height="26" focusable="false" aria-hidden="true">
                  <path
                    d="M6 9h3l1.2-1.5h8.6L20 9h3a2.5 2.5 0 012.5 2.5V22A2.5 2.5 0 0123 24.5H6A2.5 2.5 0 013.5 22V11.5A2.5 2.5 0 016 9z"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.6"
                    strokeLinejoin="round"
                  />
                  <circle cx="14.5" cy="16.5" r="4.5" fill="none" stroke="currentColor" strokeWidth="1.6" />
                </svg>
              </div>
              <span className="hero-nav-brand-text">eBay Operator</span>
            </div>
            <button className="hero-nav-signin" type="button">Sign in</button>
          </nav>

          <div className="hero-body">
            <div className="hero-text">
              <div className="hero-badge" aria-label="AI-powered">
                <span className="hero-badge-dot" aria-hidden="true" />
                AI-powered bulk listing
              </div>
              <h1 className="hero-title">
                One photo.<br />
                <span className="hero-accent">Dozens</span> of listings.
              </h1>
              <p className="hero-subtitle">
                Moving house? Clearing a garage? Snap everything in one shot.
                Our AI finds each item, writes the listing, and puts it on eBay.
                You don't lift another finger.
              </p>
              <div className="hero-cta">
                <button className="hero-cta-primary" type="button">
                  Start scanning
                  <svg viewBox="0 0 16 16" width="14" height="14" fill="none" aria-hidden="true">
                    <path d="M3 8h10M9 4l4 4-4 4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                </button>
                <button className="hero-cta-secondary" type="button">
                  Watch the demo
                </button>
              </div>
              <div className="hero-stats" aria-label="Key statistics">
                <div className="hero-stat">
                  <span className="hero-stat-num">20+</span>
                  <span className="hero-stat-label">items per photo</span>
                </div>
                <div className="hero-stat-divider" aria-hidden="true" />
                <div className="hero-stat">
                  <span className="hero-stat-num">&lt;60s</span>
                  <span className="hero-stat-label">upload to listings</span>
                </div>
                <div className="hero-stat-divider" aria-hidden="true" />
                <div className="hero-stat">
                  <span className="hero-stat-num">3 hrs</span>
                  <span className="hero-stat-label">saved vs. manual</span>
                </div>
              </div>
            </div>

            <div className="hero-visual" aria-hidden="true">
              <div className="hero-ui-mock">
                <div className="hum-titlebar">
                  <span className="hum-dot" /><span className="hum-dot" /><span className="hum-dot" />
                  <span className="hum-app-name">eBay Operator</span>
                  <span className="hum-post-btn">Post all →</span>
                </div>
                <div className="hum-scan-banner">
                  <svg viewBox="0 0 12 12" width="11" height="11" fill="none"><circle cx="6" cy="6" r="5" stroke="currentColor" strokeWidth="1.5"/><path d="M3.5 6l1.8 1.8 3-3.6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
                  5 items detected · ready to post
                </div>
                <div className="hum-listings">
                  {[
                    { name: 'Patagonia Down Jacket, M',      price: '$110', cond: 'Used – Like New', delay: '0.5s' },
                    { name: 'Air Jordan 1 Retro High OG',    price: '$175', cond: 'Used – Good',     delay: '0.65s' },
                    { name: 'Le Creuset Dutch Oven, 5.5 qt', price: '$145', cond: 'Used – Good',     delay: '0.8s' },
                    { name: 'Vintage Levi\'s 501, W28 L30',  price: '$58',  cond: 'Used – Good',     delay: '0.95s' },
                    { name: 'KitchenAid Stand Mixer',        price: '$120', cond: 'Used – Like New', delay: '1.1s' },
                  ].map((item, i) => (
                    <div key={i} className="hum-item" style={{ animationDelay: item.delay }}>
                      <div className="hum-item-thumb" />
                      <div className="hum-item-meta">
                        <span className="hum-item-name">{item.name}</span>
                        <span className="hum-item-cond">{item.cond}</span>
                      </div>
                      <span className="hum-item-price">{item.price}</span>
                      <span className="hum-item-badge">Draft</span>
                    </div>
                  ))}
                </div>
              </div>
              <div className="hero-float-card hero-float-card-1">
                <span className="hero-float-card-badge">✓ Posted to eBay</span>
                <span className="hero-float-card-name">Air Jordan 1 Retro</span>
                <span className="hero-float-card-price">$175 · 6 watchers</span>
              </div>
              <div className="hero-float-card hero-float-card-2">
                <span className="hero-float-card-badge">Total potential</span>
                <span className="hero-float-card-name" style={{ fontSize: '1.1rem', fontWeight: 700 }}>$608</span>
                <span className="hero-float-card-price">from 1 photo · 5 items</span>
              </div>
            </div>
          </div>
        </div>{/* hero-inner */}
      </header>

      <div className="page-content">
      {/* Demo animation */}
      <section className="demo-video-section reveal">
        <p className="demo-eyebrow">See it in action</p>
        <h2 className="demo-video-title">Watch a desk get listed in under a minute</h2>
        <p className="demo-video-desc">One photo. Five items. Live on eBay before the coffee's done.</p>
        <div style={{ position: 'relative', width: '100%', aspectRatio: '1280 / 720' }}>
          <HeroAnimation dark={true} />
        </div>
      </section>

      {/* Use cases */}
      <section className="use-cases-section reveal">
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
              and sell everything you're leaving behind, without burning a whole weekend on listings.
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
              Clearing a relative's home is already hard. Let us handle the eBay side:
              photograph rooms in bulk and we'll generate listings for every sellable item
              we find, with descriptions written for you.
            </p>
            <p className="use-case-example">"Cleared an entire attic in two sessions."</p>
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="how-section reveal">
        <p className="demo-eyebrow">How it works</p>
        <h2 className="how-title">From photo to live listing in four steps</h2>
        <div className="how-steps">
          <div className="how-step">
            <div className="how-step-num">1</div>
            <h3 className="how-step-title">Snap a photo</h3>
            <p className="how-step-body">Lay out everything you want to sell and take one photo. No studio setup, no individual shots. A single image of a desk, shelf, or pile is all it takes.</p>
          </div>
          <div className="how-connector" aria-hidden="true">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none"><path d="M5 12h14M13 6l6 6-6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
          </div>
          <div className="how-step">
            <div className="how-step-num">2</div>
            <h3 className="how-step-title">AI scans the scene</h3>
            <p className="how-step-body">Our model identifies every sellable item, draws a bounding box around each one, and reads make, model, and condition automatically.</p>
          </div>
          <div className="how-connector" aria-hidden="true">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none"><path d="M5 12h14M13 6l6 6-6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
          </div>
          <div className="how-step">
            <div className="how-step-num">3</div>
            <h3 className="how-step-title">Listings are drafted</h3>
            <p className="how-step-body">Title, description, category, and an estimated price range, all written for each detected item based on recent eBay sold data.</p>
          </div>
          <div className="how-connector" aria-hidden="true">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none"><path d="M5 12h14M13 6l6 6-6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
          </div>
          <div className="how-step">
            <div className="how-step-num">4</div>
            <h3 className="how-step-title">Post to eBay</h3>
            <p className="how-step-body">Review the drafts, tweak anything you like, and publish. Everything goes live in one tap. No copy-pasting across tabs.</p>
          </div>
        </div>
      </section>

      {/* Photo tips */}
      <section className="tips-section reveal">
        <p className="demo-eyebrow">Get the best results</p>
        <h2 className="tips-title">How to take a great listing photo</h2>
        <p className="tips-subtitle">Our AI is robust, but a few simple habits consistently produce more detections and sharper price estimates.</p>
        <div className="tips-grid">
          <div className="tip-card">
            <div className="tip-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/>
                <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
                <line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/>
                <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
              </svg>
            </div>
            <h3 className="tip-title">Use natural light</h3>
            <p className="tip-body">Shoot near a window. Avoid flash, which washes out the surface details the AI uses to identify items and read condition.</p>
          </div>
          <div className="tip-card">
            <div className="tip-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/>
                <rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>
              </svg>
            </div>
            <h3 className="tip-title">Spread items out</h3>
            <p className="tip-body">Don't stack or overlap things. Each item needs clear, visible edges so the model can trace outlines and separate one item from another.</p>
          </div>
          <div className="tip-card">
            <div className="tip-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
                <path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/>
              </svg>
            </div>
            <h3 className="tip-title">Fill the frame</h3>
            <p className="tip-body">Get close enough that items take up most of the shot. Large areas of empty floor or background reduce detection confidence.</p>
          </div>
          <div className="tip-card">
            <div className="tip-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
                <rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/>
              </svg>
            </div>
            <h3 className="tip-title">One shot, many items</h3>
            <p className="tip-body">No need to photograph items individually. A single desk or shelf photo routinely yields 10-20 separate listings with less work and the same result.</p>
          </div>
        </div>
        <div className="tips-callout">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true">
            <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
          </svg>
          Blurry or dark photo? We'll flag it before processing. You're never charged for a failed scan.
        </div>
      </section>

      {/* FAQ */}
      <section className="faq-section reveal">
        <p className="demo-eyebrow">Common questions</p>
        <h2 className="faq-title">Frequently asked</h2>
        <div className="faq-grid">
          <div className="faq-item">
            <p className="faq-q">What if the AI misses an item?</p>
            <p className="faq-a">You can manually add any item the model missed before posting. Detection accuracy improves continuously as the model learns from corrections.</p>
          </div>
          <div className="faq-item">
            <p className="faq-q">How accurate are the price estimates?</p>
            <p className="faq-a">Estimates are anchored to recent eBay sold listings for that exact item. They're a solid starting point. You always set the final price.</p>
          </div>
          <div className="faq-item">
            <p className="faq-q">Do I need to edit the listings before posting?</p>
            <p className="faq-a">No. Most listings are post-ready out of the box. We recommend a quick review for high-value items to confirm the condition grade.</p>
          </div>
          <div className="faq-item">
            <p className="faq-q">Which categories does it support?</p>
            <p className="faq-a">Electronics, clothing, books, collectibles, sporting goods, furniture, tools, and most household categories. Niche collectibles may need a manual title tweak.</p>
          </div>
          <div className="faq-item">
            <p className="faq-q">What happens to my photos?</p>
            <p className="faq-a">Photos are processed on our servers and automatically deleted within 24 hours. We never sell or share your data with third parties.</p>
          </div>
          <div className="faq-item">
            <p className="faq-q">Is there a limit on items per scan?</p>
            <p className="faq-a">The free tier supports up to 10 detected items per photo. Paid plans remove the cap entirely, which is useful for large garage or estate sales.</p>
          </div>
        </div>
      </section>

      </div>{/* page-content */}
    </div>
  )
}
