import type { Post } from '../types/post'

function apiBase(): string {
  const base = import.meta.env.VITE_API_BASE_URL
  if (!base || typeof base !== 'string') {
    throw new Error(
      'VITE_API_BASE_URL is not set. Copy .env.example to .env and set the API URL.',
    )
  }
  return base.replace(/\/$/, '')
}

export async function fetchPosts(): Promise<Post[]> {
  const res = await fetch(`${apiBase()}/posts`, {
    headers: { Accept: 'application/json' },
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(
      `Failed to load posts (${res.status}): ${text.slice(0, 200)}`,
    )
  }
  return res.json() as Promise<Post[]>
}
