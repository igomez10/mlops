import { PostList } from '../components/PostList'

export default function AppPage() {
  return (
    <div className="app">
      <main className="app-main">
        <div className="app-panel">
          <PostList />
        </div>
      </main>
    </div>
  )
}
