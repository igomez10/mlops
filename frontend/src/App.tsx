import { PostList } from './components/PostList'
import './App.css'

function App() {
  return (
    <div className="app">
      <header className="header">
        <div className="header-card">
          <div className="header-card-icon" aria-hidden="true">
            <svg viewBox="0 0 32 32" width="32" height="32" focusable="false">
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
          <div className="header-text">
            <p className="header-eyebrow">eBay consignment, done for you</p>
            <h1 className="header-title">eBay Operator</h1>
            <p className="header-tagline">
              Photograph your items here—we list and run your eBay sales on your behalf.
            </p>
          </div>
        </div>
      </header>
      <main className="app-main">
        <div className="app-panel">
          <PostList />
        </div>
      </main>
    </div>
  )
}

export default App
