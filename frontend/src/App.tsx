import { PostList } from './components/PostList'
import './App.css'

function App() {
  return (
    <div className="app">
      <header className="header">
        <h1>Posts</h1>
        <p className="muted">Active posts from the API (GET /posts).</p>
      </header>
      <main>
        <PostList />
      </main>
    </div>
  )
}

export default App
