import { useEffect, useState } from 'react'
import { fetchPosts } from '../api/client'
import type { Post } from '../types/post'

const dateFmt = new Intl.DateTimeFormat(undefined, {
  dateStyle: 'medium',
  timeStyle: 'short',
})

function formatWhen(iso: string): string {
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? iso : dateFmt.format(d)
}

function shortId(id: string): string {
  return id.length <= 12 ? id : `${id.slice(0, 8)}…`
}

export function PostList() {
  const [posts, setPosts] = useState<Post[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setError(null)
    fetchPosts()
      .then((data) => {
        if (!cancelled) setPosts(data)
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          setPosts(null)
          setError(e instanceof Error ? e.message : 'Failed to load posts')
        }
      })
    return () => {
      cancelled = true
    }
  }, [])

  if (error) {
    return (
      <div
        className="banner error"
        role="alert"
        data-testid="posts-error"
      >
        {error}
      </div>
    )
  }

  if (posts === null) {
    return (
      <p className="muted" data-testid="posts-loading">
        Loading posts…
      </p>
    )
  }

  if (posts.length === 0) {
    return (
      <p className="empty" data-testid="posts-empty">
        No posts yet.
      </p>
    )
  }

  return (
    <div className="table-wrap">
      <table data-testid="posts-table">
        <caption className="sr-only">Posts</caption>
        <thead>
          <tr>
            <th scope="col">ID</th>
            <th scope="col">Name</th>
            <th scope="col">Created</th>
            <th scope="col">Updated</th>
            <th scope="col">Status</th>
          </tr>
        </thead>
        <tbody>
          {posts.map((p) => (
            <tr key={p.id} data-testid="post-row">
              <td>
                <code title={p.id}>{shortId(p.id)}</code>
              </td>
              <td data-testid="post-name">{p.name}</td>
              <td data-testid="post-created">{formatWhen(p.created_at)}</td>
              <td data-testid="post-updated">{formatWhen(p.updated_at)}</td>
              <td data-testid="post-status">
                {p.deleted_at ? (
                  <span className="badge deleted" title={p.deleted_at}>
                    Deleted
                  </span>
                ) : (
                  <span className="badge active">Active</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
