import type { EbayDraft, Post } from '../types/post'

function apiBase(): string {
  const raw = import.meta.env.VITE_API_BASE_URL
  // production Docker / same host: VITE is empty (same origin)
  if (raw === undefined || raw === null) {
    return ''
  }
  if (typeof raw !== 'string') {
    throw new Error('VITE_API_BASE_URL must be a string if set')
  }
  return raw.replace(/\/$/, '')
}

async function readError(res: Response): Promise<string> {
  const text = await res.text()
  try {
    const j = JSON.parse(text) as { detail?: string | unknown }
    if (typeof j.detail === 'string') return j.detail
  } catch {
    /* use raw */
  }
  return text.slice(0, 200) || res.statusText
}

export async function fetchPosts(): Promise<Post[]> {
  const res = await fetch(`${apiBase()}/posts`, {
    headers: { Accept: 'application/json' },
  })
  if (!res.ok) {
    throw new Error(
      `Failed to load posts (${res.status}): ${await readError(res)}`,
    )
  }
  return res.json() as Promise<Post[]>
}

/** Create via JSON (e.g. tests): server assigns listings/images only when using multipart with files. */
export async function createPost(
  name: string,
  options: { description?: string } = {},
): Promise<Post> {
  const { description = '' } = options
  const res = await fetch(`${apiBase()}/posts`, {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ name, description }),
  })
  if (!res.ok) {
    throw new Error(`Create failed (${res.status}): ${await readError(res)}`)
  }
  return res.json() as Promise<Post>
}

/**
 * Create with description + image: backend uploads to the bucket first, then writes the post.
 */
export async function createPostWithImage(
  description: string,
  image: File,
  options: { userId?: string } = {},
): Promise<Post> {
  if (!image || image.size === 0) {
    throw new Error('Choose an image')
  }
  const form = new FormData()
  form.append('description', description.trim())
  if (options.userId?.trim()) {
    form.append('user_id', options.userId.trim())
  }
  form.append('files', image)
  const res = await fetch(`${apiBase()}/posts`, {
    method: 'POST',
    body: form,
  })
  if (!res.ok) {
    throw new Error(`Create failed (${res.status}): ${await readError(res)}`)
  }
  return res.json() as Promise<Post>
}

export async function updatePost(
  id: string,
  body: { name?: string; description?: string },
): Promise<Post> {
  const res = await fetch(`${apiBase()}/posts/${encodeURIComponent(id)}`, {
    method: 'PUT',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    throw new Error(`Update failed (${res.status}): ${await readError(res)}`)
  }
  return res.json() as Promise<Post>
}

export async function updateEbayDraft(
  postId: string,
  changes: Partial<Omit<EbayDraft, 'user_id' | 'category_id'>>,
): Promise<Post> {
  const res = await fetch(
    `${apiBase()}/posts/${encodeURIComponent(postId)}/ebay-draft`,
    {
      method: 'PUT',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(changes),
    },
  )
  if (!res.ok) {
    throw new Error(`Save draft failed (${res.status}): ${await readError(res)}`)
  }
  return res.json() as Promise<Post>
}

export async function publishEbayListing(postId: string): Promise<Post> {
  const res = await fetch(
    `${apiBase()}/posts/${encodeURIComponent(postId)}/ebay/publish`,
    {
      method: 'POST',
      headers: { Accept: 'application/json' },
    },
  )
  if (!res.ok) {
    throw new Error(`Publish failed (${res.status}): ${await readError(res)}`)
  }
  return res.json() as Promise<Post>
}

export async function deletePost(id: string): Promise<Post> {
  const res = await fetch(`${apiBase()}/posts/${encodeURIComponent(id)}`, {
    method: 'DELETE',
    headers: {
      Accept: 'application/json',
    },
  })
  if (!res.ok) {
    throw new Error(`Delete failed (${res.status}): ${await readError(res)}`)
  }
  return res.json() as Promise<Post>
}
